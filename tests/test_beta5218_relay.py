"""Native relay remains mounted; fallback retries staged work without creating a job."""
import shutil
from pathlib import Path
import pytest
from test_native_plugin import installation, _mock_fork, _create_public_selection, FakeWanSession
API='/casting-studio/api'
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

def test_hidden_relay_native_callback(installation):
    c,p,root,_=installation
    _mock_fork(root);session=FakeWanSession()
    ui=p.create_ui(session)
    config=ui.config
    components=config['components']
    relay=next(x for x in components if x['props'].get('elem_id')=='casting_native_queue_button')
    group=next(x for x in components if x['props'].get('elem_id')=='casting_native_queue_controls')
    assert relay['props'].get('visible',True) is True and group['props'].get('visible',True) is True
    assert any('#casting_native_queue_controls{display:none!important}' in str(x['props'].get('value','')) for x in components)
    assert not any(x['type']=='accordion' for x in components)
    dependency=next(x for x in config['dependencies'] if [relay['id'],'click'] in [list(y) for y in x['targets']])
    assert dependency['outputs'] and dependency['backend_fn']
    key=_create_public_selection(c)
    result=c.post(API+'/generator/submit',json={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint','steps':8,'resolution':'1280x720'})
    assert result.status_code==200,result.text
    assert len(p.queue_bridge._pending)==1 and not session.submitted
    assert 'completed' in p.queue_bridge.process_pending_in_gradio(session)
    assert len(session.submitted)==1
    assert p.queue_bridge.process_pending_in_gradio(session)=='No casting jobs are waiting.'
    assert len(session.submitted)==1

def test_troubleshooting_retry_clicks_hidden_parent_button():
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page();page.set_default_timeout(5000)
        # A srcdoc iframe inherits its parent origin without network navigation.
        page.set_content('<style>#casting_native_queue_controls{display:none!important}</style><div id="casting_native_queue_controls"><button id="casting_native_queue_button" onclick="window.relayClicks=(window.relayClicks||0)+1">Native</button></div><iframe id="testFrame" style="width:100%;height:900px" srcdoc="<html></html>"></iframe>')
        frame=page.frames[1]
        frame.evaluate(setup_js)
        frame.set_content(HTML,wait_until='domcontentloaded')
        frame.wait_for_function('choices.length===2')
        assert not page.locator('#casting_native_queue_button').is_visible()
        frame.evaluate("$('settingsModal').classList.add('open')")
        frame.locator('#queueTroubleshooting summary').click()
        frame.locator('#retryNativeQueue').click()
        assert page.evaluate('window.relayClicks')==1
        assert 'Native handoff requested' in frame.locator('#nativeQueueRetryStatus').text_content()
        assert frame.evaluate('window.responses.length')==0
        assert frame.locator('#retryNativeQueue').is_disabled()
        frame.wait_for_function("!$('retryNativeQueue').disabled")
        page.locator('#casting_native_queue_button').evaluate('e=>e.remove()')
        frame.locator('#retryNativeQueue').click()
        assert 'unavailable' in frame.locator('#nativeQueueRetryStatus').text_content()
        assert page.evaluate('window.relayClicks')==1
        browser.close()

def test_first_run_data_swap_preserves_model_library(installation):
    import importlib
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    c,p,root,_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    models={f:f.read_bytes() for f in (root/'refmods').rglob('*.safetensors')}
    assert c.post(API+'/personal',json={'name':'Example Private','consent':False}).status_code==200
    assert c.post(API+'/productions/cast',json={'actress':'Example Person','production':'Example Series','character':'Example Role'}).status_code==200
    data=root/'user_data';backup=root/'user_data_backup';fresh=root/'user_data_fresh'
    def restart():
        importlib.reload(srv)
        host=FastAPI();host.mount('/casting-studio',p.create_web_app());return TestClient(host)
    data.rename(backup)
    try:
        c=restart()
        assert c.get(API+'/personal').json()==[]
        assert c.get(API+'/choices').json()==[]
        assert c.get(API+'/productions?q=Example Series').json()==[]
        assert any(m['path']=='Ada_Test_H3.safetensors' for m in c.get(API+'/catalog').json()['models'])
        assert {f:f.read_bytes() for f in models}==models
    finally:
        if data.exists():data.rename(fresh)
        backup.rename(data)
    c=restart()
    assert c.get(API+'/personal').json()[0]['name']=='Example Private'
    assert c.get(API+'/productions?q=Example Series').json()[0]['name']=='Example Series'
    assert {f:f.read_bytes() for f in models}==models

def test_native_queue_manager_exact_task_and_batch_skip(installation):
    import json
    from types import SimpleNamespace
    c,p,_,_=installation;b=p.queue_bridge;calls=[]
    tasks=[{'queue_id':'active','position':1,'status':'running','model_type':'fixture','prompt':'<script>not markup</script>','client_id':'c1'}, {'queue_id':'waiting','position':2,'status':'queued','client_id':'c2'}, {'queue_id':'other','position':3,'status':'queued','client_id':''}]
    def cancel(key):
        calls.append(key);tasks[:]=[t for t in tasks if t['queue_id']!=key];return {'status':'cancelled'}
    session=SimpleNamespace(list_queue=lambda:{'tasks':tasks},cancel_queue_task=cancel)
    b._jobs['batch']={'batch':True,'state':'running','_monitor_native_ids':{'c1':1,'c2':2}}
    def request(**kw):return json.loads(b.manage_native_queue(session,json.dumps({'token':'test',**kw})))
    d=request(action='list');assert len(d['tasks'])==3 and d['can_cancel'] and d['token']=='test'
    assert 'client_id' not in d['tasks'][0]
    assert 'error' in request(action='cancel',queue_id='active',status='queued') and not calls
    d=request(action='cancel',queue_id='waiting',status='queued');assert calls==['waiting'] and len(d['tasks'])==2
    assert b._jobs['batch']['_monitor_skipped']=={2}
    assert 'error' in request(action='cancel',queue_id='waiting',status='queued') and calls==['waiting']
    assert 'error' in json.loads(b.manage_native_queue(object(),'{"action":"list"}'))
    ui=p.create_ui(session);config=ui.config
    relay=next(x for x in config['components'] if x['props'].get('elem_id')=='casting_queue_manage_button')
    dep=next(x for x in config['dependencies'] if [relay['id'],'click'] in [list(y) for y in x['targets']])
    assert dep['inputs'] and dep['outputs'] and 'boardRequest' in dep['js']


def test_native_queue_manager_browser():
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page();page.set_default_timeout(5000)
        page.set_content('''<div style="display:none"><button id="casting_queue_manage_button">Native</button><div id="casting_queue_response"><textarea></textarea></div></div><iframe style="width:100%;height:900px" srcdoc="<html></html>"></iframe>''')
        page.evaluate('''()=>{window.calls=[];let tasks=[{queue_id:'a',position:1,status:'running',model_type:'fixture',prompt:'<img src=x onerror=alert(1)>'},{queue_id:'b',position:2,status:'queued',prompt:'Other task'}];document.querySelector('#casting_queue_manage_button').onclick=e=>{let r=JSON.parse(e.target.dataset.boardRequest);calls.push(r);if(r.action==='cancel')tasks=tasks.filter(t=>t.queue_id!==r.queue_id);document.querySelector('textarea').value=JSON.stringify({token:r.token,tasks,can_cancel:true})}}''')
        frame=page.frames[1];frame.evaluate(setup_js);frame.set_content(HTML,wait_until='domcontentloaded')
        assert page.evaluate('calls.length')==0
        frame.locator('#nativeQueuePanel summary').click();frame.locator('#nativeQueueRows').get_by_role('button',name='Remove').wait_for()
        assert frame.locator('#nativeQueueRows img').count()==0
        page.once('dialog',lambda d:d.accept());frame.locator('#nativeQueueRows').get_by_role('button',name='Remove').click()
        frame.wait_for_function("!$('nativeQueueRows').textContent.includes('Other task')")
        assert page.evaluate('calls[1].queue_id')=='b'
        frame.locator('#nativeQueuePanel summary').click();frame.wait_for_timeout(250)
        assert page.evaluate('calls.length')==2
        browser.close()

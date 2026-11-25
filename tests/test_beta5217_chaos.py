"""Seeded misuse tests. Isolated local data, simulated WanGP; no online or GPU work."""
import random, shutil, io
from pathlib import Path
import pytest
from test_native_plugin import installation,_mock_fork,_create_public_selection,FakeWanSession
from test_dev512_image_sets import _image_session,_set_image_template
API='/casting-studio/api'
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

@pytest.fixture
def browser_page():
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1440,'height':950});page.set_default_timeout(5000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('dialog',lambda d:d.dismiss())
        page.evaluate(setup_js)
        page.evaluate('''() => {const old=window.fetch;window.workshopWrites=0;window.batchWrites=0;window.failPreview=false;window.fetch=async(u,o={})=>{const path=String(u).split('?')[0];let data;const reply=(data,ok=true)=>({ok,status:ok?200:400,json:async()=>data,text:async()=>JSON.stringify(data)});if(path==='api/generator/submit'){await new Promise(r=>setTimeout(r,80));return old(u,o)}if(path==='api/generator/batch/submit'){window.batchWrites++;await new Promise(r=>setTimeout(r,80));return reply({id:'batch-test',task_count:5})}if(path==='api/generator/prompt-edit'&&JSON.parse(o.body).prompt?.trim().length<12)return reply({detail:'Prompt too short'},false);if(path==='api/generator/preview'&&window.failPreview)return reply({detail:'Simulated failed preview'},false);if(path==='api/workshop/create'){window.workshopWrites++;await new Promise(r=>setTimeout(r,80));return reply({job_id:'workshop-test',target:'Example'})}if(path==='api/workshop/jobs/workshop-test')return reply({state:'failed',message:'Simulated failure'});if(path==='api/workshop/sources')return reply({sources:[]});if(path==='api/workshop/models')return reply({models:[]});if(path==='api/workshop/mods')return reply({mods:[]});if(path==='api/personal/refmods'||path==='api/productions'||path==='api/discovery/people')return reply([]);if(path==='api/maintenance/activity')return reply({running:false,jobs:[]});return old(u,o);};}''')
        page.set_content(HTML,wait_until='domcontentloaded');page.wait_for_function('choices.length===2')
        yield page,errors
        browser.close()


def test_queue_click_storm_and_preview_recovery(browser_page):
    page,errors=browser_page
    page.evaluate('openGenerator()');page.wait_for_function("!$('generatorPreview').disabled && !$('generatorSubmit').disabled")
    page.evaluate('''async()=>{await Promise.all(Array.from({length:50},(_,i)=>submitGenerator(i%2===0)));}''')
    assert page.evaluate('window.responses.length')==1
    page.wait_for_function("!$('generatorSubmit').disabled && !$('generatorPreview').disabled")
    # A failed new-scene preview must not make the previous prompt editable as the new one.
    page.evaluate("window.failPreview=true;$('generatorScene').value='2';generatorSceneChanged()")
    page.wait_for_function("$('generatorPreviewInfo').textContent==='Preview unavailable'")
    assert page.locator('#generatorPreview').is_disabled()
    assert page.locator('#generatorPreview').input_value()==''
    page.evaluate('window.failPreview=false;previewGenerator()');page.wait_for_function("!$('generatorPreview').disabled")
    for field,value in [('generatorSeed','-2'),('generatorSeed','1.5'),('generatorSteps','101'),('generatorStrength','0')]:
        old=page.locator('#'+field).input_value();page.locator('#'+field).evaluate('(e,v)=>e.value=v',value)
        assert page.evaluate("()=>{try{generatorBody();return false}catch(e){return true}}")
        page.locator('#'+field).evaluate('(e,v)=>e.value=v',old)
    assert not errors,errors


def test_keyboard_mashing_and_navigation(browser_page):
    page,errors=browser_page;rng=random.Random(5217)
    page.evaluate('openPersonalEditor()');page.wait_for_function("activeCastingModal()?.id==='personalModal'")
    for i in range(160):
        page.keyboard.press(rng.choice(['Tab','Shift+Tab','ArrowLeft','ArrowRight','Home','End','Backspace','a','7','Space']))
        assert page.evaluate("!activeCastingModal() || activeCastingModal().contains(document.activeElement)")
        if not page.locator('#personalModal').evaluate("e=>e.classList.contains('open')"):
            page.evaluate('openPersonalEditor()')
    # Test two stacked dialogs and one Escape at a time.
    page.evaluate("$('aboutModal').classList.add('open')")
    page.wait_for_function("activeCastingModal()?.id==='aboutModal'")
    page.keyboard.press('Escape');assert page.locator('#personalModal').evaluate("e=>e.classList.contains('open')")
    page.keyboard.press('Escape');page.wait_for_function('!activeCastingModal()')
    tabs=['productions','personal','performers','models','adult','television','workshop']
    for i in range(140):
        tab=rng.choice(tabs)
        page.evaluate('(t)=>showTab(t)',tab)
        assert page.evaluate("$('castingSelectionsPanel').hidden===(activeTab==='workshop')")
    assert page.evaluate('choices.length')==2
    assert not errors,errors


def test_workshop_storm_and_recovery(browser_page):
    page,errors=browser_page
    page.evaluate("workshopRun('extract',{name:'',model_type:'',image_ids:[]})")
    assert 'Choose a model' in page.locator('#workshopCreateStatus').text_content()
    page.evaluate('''async()=>{await Promise.all(Array.from({length:50},()=>workshopRun('extract',{name:'Example',model_type:'fixture',image_ids:['a']})));}''')
    assert page.evaluate('window.workshopWrites')==1
    page.wait_for_function('!workshopBusy',timeout=6000)
    assert 'failed' in page.locator('#workshopCreateStatus').text_content()
    assert not errors,errors


def test_bad_inputs_and_unicode_identity(installation):
    c,p,root,_=installation
    for text in (' ', '   ', '???', '\t\n', '🦄🦄'):
        for endpoint,payload in [('personal',{'name':text}),('productions',{'name':text}),('productions/cast',{'production':'Example Series','actress':text})]:
            assert 400<=c.post(API+'/'+endpoint,json=payload).status_code<500
    for name in ['山田','李雷','مثال']:
        assert c.post(API+'/personal',json={'name':name}).status_code==200
    assert len(c.get(API+'/personal').json())==3
    assert c.post(API+'/productions',json={'name':'Example Series','year':99999}).status_code==400
    assert c.post(API+'/productions/cast',json={'production':'Example Series','actress':'Example Person','year':-2}).status_code==400
    # Seeded malformed requests: every failure must be a client error, not a traceback.
    _mock_fork(root);s=FakeWanSession();s.defs[0]['sliding_window']=True;p.queue_bridge.api_session=s;p.queue_bridge.dispatch_mode='gradio';key=_create_public_selection(c)
    task={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint','video_seconds':30,'video_script_mode':'sequence','sliding':{'sliding_window_size':362,'sliding_window_overlap':18}}
    mutants=[{'seed':v} for v in [-2,1.2,'bad',10**30]]+ [{'steps':v} for v in [0,-1,101,1.5,'bad']]+[{'strength':v} for v in [0,-1,3,'bad']]+[{'video_seconds':v} for v in [0,20,61]]+ [{'sliding':{'sliding_window_size':v}} for v in [0,True,1e20,100.5,{},'bad']]+[{'extra_settings':{k:0}} for k in ['prompt','custom_settings','video_length','sliding_window_size','multi_prompts_gen_type']]+[{'loras':[{'name':'missing','multiplier':1}]},{'model_type':'wrong'},{'choice_key':'missing'}]
    rng=random.Random(5217);rng.shuffle(mutants)
    for mutant in mutants:
        r=c.post(API+'/generator/submit',json={**task,**mutant});assert 400<=r.status_code<500,(mutant,r.status_code,r.text)
    assert not p.queue_bridge._pending
    assert c.post(API+'/generator/submit',json=task).status_code==200


def test_workshop_invalid_settings_and_duplicate_pending(installation,monkeypatch):
    import importlib
    c,p,root,_=installation;srv=importlib.import_module('cb_under_test.app.server')
    source=root/'photo.jpg';source.write_bytes(b'fixture')
    monkeypatch.setattr(srv,'workshop_photo_rows',lambda *a:[{'id':'a','path':source},{'id':'b','path':source}])
    monkeypatch.setattr(p.adapter,'discover',lambda:{'fork_revision':58,'installed':True})
    monkeypatch.setattr(p.queue_bridge,'models',lambda *a:[{'model_type':'fixture-model','ready':True}])
    p.queue_bridge.dispatch_mode='gradio';p.queue_bridge.api_session=object()
    task={'person':'Example Person','image_ids':['a'],'name':'Example','model_type':'fixture-model','family':'flux2'}
    for change in [{'layout':'bad'},{'budget':123},{'image_ids':['a','b']},{'image_ids':[]},{'name':'!!!'}]:
        r=c.post(API+'/workshop/create',json={**task,**change});assert 400<=r.status_code<500,r.text
    assert c.post(API+'/workshop/create',json=task).status_code==200
    assert c.post(API+'/workshop/create',json=task).status_code==409
    assert len(p.queue_bridge._pending)==1


def test_image_sets_ignore_stale_native_repeat_settings(installation):
    c,p,root,_=installation;_mock_fork(root);s=_image_session();old=s.merge_settings_with_defaults
    s.merge_settings_with_defaults=lambda data:{**old(data),'batch_size':7,'repeat_generation':9}
    p.queue_bridge.api_session=s;p.queue_bridge.dispatch_mode='gradio';key=_create_public_selection(c);_set_image_template(c,count=3)
    body={'task':{'choice_key':key,'model':'h3_image_pruned','model_type':'h3_image_pruned_checkpoint'},'scope':'selection:'+key,'scene_mode':'all'}
    assert c.post(API+'/generator/batch/submit',json=body).status_code==200
    p.queue_bridge.process_pending_in_gradio(s)
    assert len(s.manifests[0])==3
    assert all(x['batch_size']==x['repeat_generation']==1 for x in s.manifests[0])


def test_invalid_prompt_discard_recovers_editor(browser_page):
    page,errors=browser_page
    page.evaluate('openGenerator()');page.wait_for_function("!$('generatorPreview').disabled")
    page.locator('#generatorPreviewPanel').evaluate('(e)=>e.open=true')
    page.locator('#generatorPreview').fill('')
    page.wait_for_function("$('generatorPromptSaveStatus').textContent.includes('Not saved')")
    assert page.locator('#generatorDiscardDraft').is_visible()
    page.evaluate("window.confirm=()=>true")
    page.locator('#generatorDiscardDraft').click()
    page.wait_for_function("!$('generatorPreview').disabled && $('generatorPreview').value==='Test prompt'")
    assert not page.locator('#generatorDiscardDraft').is_visible()
    assert not errors,errors

from test_native_plugin import reviewed_submit
from pathlib import Path
import shutil
import pytest
from test_native_plugin import installation,_mock_fork,_create_public_selection,FakeWanSession
from test_dev512_image_sets import _image_session,_set_image_template
API='/casting-studio/api'
CUSTOM='A custom portrait prompt with soft daylight and a blue background.'

def test_persistent_scene_edit_review_native_manifest_and_reset(installation):
    c,p,root,_=installation;_mock_fork(root);session=_image_session();p.queue_bridge.api_session=session;p.queue_bridge.dispatch_mode='gradio'
    key=_create_public_selection(c);_set_image_template(c,count=3)
    task={'choice_key':key,'model':'h3_image_pruned','model_type':'h3_image_pruned_checkpoint','scene':2}
    preview=lambda t:c.post(API+'/generator/preview',json=t).json()
    original=preview(task)['prompt'];assert not preview(task)['edited']
    r=c.put(API+'/generator/prompt-edit',json={'task':task,'prompt':CUSTOM});assert r.status_code==200,r.text
    assert preview(task)['prompt']==CUSTOM and preview(task)['edited']
    assert preview({**task,'scene':1})['prompt']!=CUSTOM
    assert preview({**task,'model_type':'alternate'})['prompt']!=CUSTOM
    body={'task':task,'scope':'selection:'+key,'scene_mode':'all'}
    result=c.post(API+'/generator/batch/preview',json=body);assert result.status_code==200,result.text
    assert [x['prompt']==CUSTOM for x in result.json()['tasks']]==[False,True,False]
    r=reviewed_submit(c,API+'/generator/batch/submit',json=body);assert r.status_code==200,r.text
    r=c.put(API+'/generator/prompt-edit',json={'task':task,'prompt':CUSTOM+' Revised.'});assert r.status_code==200
    p.queue_bridge.process_pending_in_gradio(session)
    assert len(session.manifests[0])==3 and session.manifests[0][1]['prompt']==CUSTOM
    assert c.put(API+'/generator/prompt-edit',json={'task':task,'prompt':None}).status_code==200
    assert preview(task)['prompt']==original and not preview(task)['edited']

def test_window_edits_keep_scheduler_and_consent(installation):
    c,p,root,_=installation;_mock_fork(root);session=FakeWanSession();session.defs[0]['sliding_window']=True;p.queue_bridge.api_session=session
    p.queue_bridge._lora_catalog=lambda *args:{'supported':True,'loras':['a.safetensors']}
    key=_create_public_selection(c)
    task={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint','video_seconds':30,'video_script_mode':'sequence','sliding':{'sliding_window_size':362,'sliding_window_overlap':18},'loras':[{'name':'a.safetensors','multiplier':1}], 'window_loras':{'a.safetensors':[0,1]}}
    assert c.put(API+'/generator/prompt-edit',json={'task':task,'prompt':CUSTOM}).status_code==400
    text=CUSTOM+'\n\nA second distinct motion prompt for the video.'
    assert c.put(API+'/generator/prompt-edit',json={'task':task,'prompt':text}).status_code==200
    d=c.post(API+'/generator/preview',json=task).json();assert d['editable_prompt']==text and d['prompt'].count('[/loras_mult=')==2
    assert c.post(API+'/generator/preview',json={**task,'video_seconds':15,'window_loras':{}}).json()['prompt']!=text
    private={'name':'Private Test','relationship':'Friend','notes':'Private','consent':True,'h3_refmod':'personal/Private_Test_H3.safetensors'}
    assert c.post(API+'/personal',json=private).status_code==200
    pid=c.get(API+'/personal').json()[0]['id'];assert c.put(API+'/choices',json={'key':'','person':'Private Test','character':'','production':'','refmod':private['h3_refmod'],'personal_id':pid}).status_code==200
    pk=next(x['key'] for x in c.get(API+'/choices').json() if x.get('personal_id')==pid)
    pt={**task,'choice_key':pk}
    assert c.put(API+'/generator/prompt-edit',json={'task':pt,'prompt':text}).status_code==200
    assert c.put(API+'/personal/'+pid,json={**private,'consent':False}).status_code==200
    assert c.post(API+'/generator/preview',json=pt).status_code==403
    assert c.put(API+'/generator/prompt-edit',json={'task':pt,'prompt':text}).status_code==403
    assert c.delete(API+'/personal/'+pid).status_code==200
    import sys
    with sys.modules['cb_under_test.app.server'].connect() as db:assert not db.execute('SELECT 1 FROM final_prompt_edits WHERE personal_id=?',(pid,)).fetchone()

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium unavailable')
def test_browser_autosaves_and_refreshes_without_discarding():
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    html=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1440,'height':950});page.set_default_timeout(6000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.evaluate('''() => {const original=window.fetch;const edits=new Map();const key=t=>JSON.stringify([t.choice_key,t.model,t.model_type,t.scene]);window.fetch=async(url,opts={})=>{const path=String(url);let data;if(path==='api/generator/prompt-edit'){const {task,prompt}=JSON.parse(opts.body);if(prompt===null)edits.delete(key(task));else edits.set(key(task),prompt);data={saved:prompt!==null}}else if(path==='api/generator/preview'){const t=JSON.parse(opts.body);data={review_token:'test-preview',refmod_filename:'Ada.safetensors',prompt:edits.get(key(t))||'Original generated prompt for scene '+t.scene,edited:edits.has(key(t))}}else return original(url,opts);return {ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)}};}''')
        page.set_content(html,wait_until='domcontentloaded');page.wait_for_function('choices.length===2');page.evaluate('openGenerator()')
        page.wait_for_function("!$('generatorPreview').disabled")
        page.locator('#generatorPreviewPanel').evaluate('(e)=>e.open=true')
        page.locator('#generatorPreview').fill(CUSTOM)
        page.get_by_role('button',name='Refresh prompt',exact=True).click()
        page.wait_for_function("!$('generatorPreview').disabled && $('generatorPromptSaveStatus').textContent==='Custom prompt saved'")
        assert page.locator('#generatorPreview').input_value()==CUSTOM
        page.locator('#generatorScene').select_option('2');page.wait_for_function("!$('generatorPreview').disabled && $('generatorPreview').value.includes('scene 2')")
        page.locator('#generatorScene').select_option('1');page.wait_for_function("!$('generatorPreview').disabled && $('generatorPreview').value.startsWith('A custom')")
        page.once('dialog',lambda d:d.accept());page.locator('#generatorPromptReset').click();page.wait_for_function("!$('generatorPreview').disabled && $('generatorPreview').value.includes('Original generated')")
        assert not errors,errors;browser.close()

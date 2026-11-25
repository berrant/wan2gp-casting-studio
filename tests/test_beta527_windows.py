from pathlib import Path
import shutil
import pytest
from test_native_plugin import installation,_mock_fork,_create_public_selection,_await_job,FakeWanSession
API='/casting-studio/api'

def test_exact_two_window_queue_with_window_only_lora(installation):
    c,p,root,_=installation;_mock_fork(root);session=FakeWanSession();session.defs[0]['sliding_window']=True;p.queue_bridge.api_session=session
    p.queue_bridge._lora_catalog=lambda *args:{'supported':True,'loras':['base.safetensors','action.safetensors']}
    key=_create_public_selection(c)
    task={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint','video_seconds':30,'video_script_mode':'sequence','fixed_windows':True,'sliding':{'sliding_window_size':362,'sliding_window_overlap':18,'sliding_window_discard_last_frames':8},'loras':[{'name':'base.safetensors','multiplier':1.5},{'name':'action.safetensors','multiplier':0}], 'window_loras':{'action.safetensors':[0,.8]}}
    r=c.post(API+'/generator/preview',json=task);assert r.status_code==200,r.text
    expected=r.json()['prompt'];parts=expected.split('\n\n');assert len(parts)==2
    assert parts[0].startswith('[/duration=354] [/loras_mult=1.5 0]')
    assert parts[1].startswith('[/duration=336] [/loras_mult=1.5 0.8]')
    assert '[/duration=' not in r.json()['editable_prompt']
    r=c.post(API+'/generator/submit',json=task);assert r.status_code==200,r.text
    assert _await_job(c,r.json()['id'])['state']=='completed'
    assert len(session.submitted)==1
    assert session.submitted[0]['video_length']==690
    assert session.submitted[0]['prompt']==expected
    assert session.submitted[0]['multi_prompts_gen_type']=='PW'
    assert session.submitted[0]['activated_loras']==['base.safetensors','action.safetensors']
    default_task={**task,'sliding':{}}
    r=c.post(API+'/generator/submit',json=default_task);assert r.status_code==200,r.text
    assert _await_job(c,r.json()['id'])['state']=='completed'
    assert session.submitted[-1]['video_length']==690
    assert session.submitted[-1]['sliding_window_discard_last_frames']==8
    assert session.submitted[-1]['sliding_window_size']==362
    assert session.submitted[-1]['sliding_window_overlap']==18
    assert c.post(API+'/generator/preview',json={**task,'sliding':{'sliding_window_size':100,'sliding_window_overlap':100}}).status_code==400
    assert c.put(API+'/generator/prompt-edit',json={'task':task,'prompt':'[/duration=600] First distinct action.\n\nSecond distinct action.'}).status_code==400

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium unavailable')
def test_browser_add_windows_and_lora_without_opening_session_settings():
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    html=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1440,'height':950});page.set_default_timeout(6000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.evaluate('''() => {const original=window.fetch;window.fetch=async(url,opts={})=>{const r=await original(url,opts);if(String(url).startsWith('api/generator/model-details')){const d=await r.json();d.sliding_window_supported=true;d.default_loras=[];d.sliding_window_defaults={sliding_window_size:400,sliding_window_overlap:20,sliding_window_discard_last_frames:0};return {...r,json:async()=>d}}return r;};}''')
        page.set_content(html,wait_until='domcontentloaded');page.wait_for_function('choices.length===2');page.evaluate('openGenerator()')
        page.wait_for_function("!$('generatorAddWindow').disabled && !$('generatorPreview').disabled")
        page.locator('#generatorSessionPanel').evaluate('(e)=>e.open=false')
        assert page.locator('#generatorAddWindow').is_visible()
        page.locator('#generatorAddWindow').click();assert page.locator('#generatorVideoSeconds').input_value()=='30'
        assert page.locator('#generatorWindowLoraPanel').is_visible()
        assert '690 output frames' in page.locator('#generatorWindowSummary').text_content()
        page.locator('#generatorLoraTarget').select_option('1')
        page.locator('#generatorWindowLoraPicker').select_option('Other.safetensors')
        page.locator('#generatorAddWindowLora').click()
        assert page.locator('[aria-label="Other.safetensors Window 1 strength"]').input_value()=='0'
        assert page.locator('[aria-label="Other.safetensors Window 2 strength"]').input_value()=='1'
        page.locator('[aria-label="Other.safetensors Window 2 strength"]').fill('0.8')
        body=page.evaluate('generatorBody()');assert body['fixed_windows'] and body['window_loras']=={'Other.safetensors':[0,0.8]}
        assert body['loras']==[{'name':'Other.safetensors','multiplier':0}]
        page.locator('#generatorAddWindow').click();page.locator('#generatorAddWindow').click();assert page.locator('#generatorAddWindow').is_disabled()
        assert page.locator('[aria-label="Other.safetensors Window 4 strength"]').input_value()=='0'
        page.locator('#generatorRemoveWindow').click();page.locator('#generatorRemoveWindow').click();assert page.locator('#generatorVideoSeconds').input_value()=='30'
        assert page.locator('[aria-label="Other.safetensors Window 2 strength"]').input_value()=='0.8'
        page.evaluate('submitGenerator(false)');page.wait_for_function('window.responses.length===1');assert page.evaluate('window.responses[0].window_loras["Other.safetensors"]')==[0,0.8]
        assert not errors,errors;browser.close()

"""Exercise recovery UI and the native handoff after a privacy transition."""
from test_native_plugin import reviewed_submit
from test_native_plugin import installation, _create_public_selection, _mock_fork, FakeWanSession
from test_rc2_jackhammer import server, API, seed_reference
from PIL import Image
import shutil
import pytest


def test_native_handoff_rejects_public_to_personal_transition(installation):
    c,p,root,_=installation
    _mock_fork(root);fake=FakeWanSession();b=p.queue_bridge
    b.api_session=fake;b.dispatch_mode='gradio'
    b.providers={'list_model_defs':fake.list_model_defs,'get_factory_settings':lambda _: {},'get_lora_dir':lambda _:str(root/'loras'/'h3')}
    key=_create_public_selection(c)
    response=reviewed_submit(c,API+'/generator/submit',json={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint'})
    assert response.status_code==200,response.text
    jid=response.json()['id']
    assert c.post(API+'/personal',json={'name':'Ada Test','consent':True,'h3_refmod':'personal/Private_Test_H3.safetensors'}).status_code==200
    b.process_pending_in_gradio(fake)
    assert b.status(jid)['state']=='failed' and not fake.submitted
    assert (root/'refmods/minimax_h3/celebs/Ada_Test_H3.safetensors').read_bytes()==b'not a real model'
    assert (root/'refmods/minimax_h3/personal/Private_Test_H3.safetensors').read_bytes()==b'not a real model'
    # Explicit private selection is still supported after the transition.
    pid=c.get(API+'/personal').json()[0]['id']
    assert c.put(API+'/choices',json={'key':'','person':'Ada Test','character':'','production':'','refmod':'personal/Private_Test_H3.safetensors','personal_id':pid}).status_code==200
    assert c.post(API+'/generator/preview',json={'choice_key':key,'model':'h3_video','scene':1}).status_code==200


def test_workshop_rejects_two_records_for_one_source(installation):
    c,p,*_=installation;s=server();filename='b'*24+'.jpg'
    Image.new('RGB',(800,800)).save(s.REFERENCE_DIR/filename)
    seed_reference(s,'one','passed',filename);seed_reference(s,'two','reviewed',filename)
    r=c.post(API+'/workshop/create',json={'person':'Example Person','production':'Example Series','image_ids':['one','two'],'name':'Synthetic_Test','model_type':'fixture','family':'minimax_h3'})
    assert r.status_code==400 and 'different reference photos' in r.json()['detail']
    assert not p.queue_bridge._pending and (s.REFERENCE_DIR/filename).is_file()


def test_browser_recovery_warning_and_explicit_reset():
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js,HTML
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page();page.set_default_timeout(5000);errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.evaluate('''()=>{const base=window.fetch;window.deletes=0;window.fetch=async(url,opts={})=>{if(String(url)==='api/choices'){if(opts.method==='DELETE'){window.deletes++;return {ok:true,json:async()=>({removed:3})}}return {ok:true,json:async()=>[],headers:{get:k=>k.toLowerCase()==='x-casting-choice-warning'?'3':null}}}return base(url,opts)}}''')
        page.set_content(HTML,wait_until='domcontentloaded')
        page.wait_for_function("!$('choiceRecoveryWarning').hidden && !$('removeAllBtn').disabled")
        assert '3 saved selection' in page.locator('#choiceRecoveryWarning').text_content()
        page.once('dialog',lambda d:d.dismiss());page.locator('#removeAllBtn').click();assert page.evaluate('window.deletes')==0
        assert page.locator('#choiceRecoveryWarning').is_visible()
        page.once('dialog',lambda d:d.accept());page.locator('#removeAllBtn').click()
        page.wait_for_function("$('choiceRecoveryWarning').hidden && $('removeAllBtn').disabled")
        assert page.evaluate('window.deletes')==1 and not errors,errors
        b.close()

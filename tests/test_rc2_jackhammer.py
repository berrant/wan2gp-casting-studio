"""Adversarial fixtures, isolated from real user data and WanGP hardware."""
import importlib,json
from concurrent.futures import ThreadPoolExecutor
import pytest
from PIL import Image
from test_native_plugin import installation
API='/casting-studio/api'
def server():return importlib.import_module('cb_under_test.app.server')
def seed_reference(srv,id_,status,filename):
    with srv.connect() as db:
        db.execute('INSERT INTO reference_images(id,person,production,character,source_url,page_url,filename,width,height,quality_status,quality_notes,perceptual_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(id_,'Example Person','Example Series','Role','https://example.invalid/'+id_,'',filename,800,800,status,'','0000000000000000'))
def test_malformed_path_settings_recover(installation):
    c,_,_,_=installation;srv=server();good=c.get(API+'/settings/paths').json()
    for value in [[],None,42,'wrong',{'refmod_root':[1]},{'refmod_root':123},{'refmod_root':'\x00'},{'refmod_root':'~nonexistent_example_user/foo'}]:
        raw=json.dumps(value);srv.PATHS_FILE.write_text(raw)
        assert c.get(API+'/settings/paths').json()==good
        assert srv.PATHS_FILE.read_text()==raw
    for value in ['\x00','~nonexistent_example_user/foo']:
        assert c.put(API+'/settings/paths',json={'refmod_root':value}).status_code==422
    assert c.put(API+'/settings/paths',json={'refmod_root':good['refmod_root']}).status_code==200

def test_reference_rejection_cannot_be_laundered(installation,monkeypatch):
    c,_,_,_=installation;srv=server()
    for i,status in enumerate(['rejected','pending','missing','review','reviewed','passed']):
        id_=str(i);filename=id_+'.jpg';Image.new('RGB',(800,800)).save(srv.REFERENCE_DIR/filename);seed_reference(srv,id_,status,filename)
        if status in ('rejected','pending','missing'):
            assert c.put(API+'/reference-images/'+id_+'/review',json={'approved':False}).status_code==422
            assert c.put(API+'/reference-images/'+id_+'/review',json={'approved':True}).status_code==422
        else:assert c.put(API+'/reference-images/'+id_+'/review',json={'approved':False}).status_code==200
    calls=iter([False,True,True,True,True,True]);monkeypatch.setattr(srv,'analyze_reference_image',lambda im:{'width':800,'height':800,'sharpness':1,'face_count':0,'fingerprint':'0000000000000000','hard_reasons':['Blurred'] if next(calls) else [],'review_reasons':[]})
    result=c.post(API+'/reference-images/audit',params={'person':'Example Person','production':'Example Series'}).json()
    assert result['counts']['rejected']==5 and result['counts']['passed']==1

def test_corrupted_media_records_never_expose_or_delete_other_files(installation):
    c,_,root,_=installation;srv=server();outside=root/'outside.jpg';outside.write_bytes(b'private sentinel')
    seed_reference(srv,'bad','passed',str(outside))
    assert c.get(API+'/reference-images/export',params={'person':'Example Person','production':'Example Series'}).status_code==409
    assert c.get(API+'/reference-images/file/bad').status_code==404
    assert c.post(API+'/reference-images/audit',params={'person':'Example Person','production':'Example Series'}).json()['counts']['missing']==1
    assert c.delete(API+'/reference-images/bad').status_code==200
    assert outside.read_bytes()==b'private sentinel'
    pid=c.post(API+'/personal',json={'name':'Example Private'}).json()['id']
    with srv.connect() as db:db.execute('UPDATE personal_profiles SET portrait=? WHERE id=?',(str(outside),pid))
    assert c.delete(API+'/personal/'+pid).status_code==200
    assert outside.read_bytes()==b'private sentinel'
    filename='a'*64+'.jpg'
    try:(srv.PHOTO_DIR/filename).symlink_to(outside)
    except OSError:pytest.skip('Symlinks unavailable')
    assert c.get(API+'/photos/'+filename).status_code==404

def test_upload_invalid_header_and_image_decode(installation,monkeypatch):
    c,_,_,_=installation;srv=server()
    for length in ['invalid','-1']:
        r=c.post(API+'/images/upload',params={'key':'role|a|b|c'},content=b'not image',headers={'content-type':'image/png','content-length':length})
        assert 400<=r.status_code<500
    def bomb(*args,**kwargs):raise Image.DecompressionBombError('simulated oversized image')
    monkeypatch.setattr(srv.Image,'open',bomb)
    r=c.post(API+'/images/upload',params={'key':'role|a|b|c'},content=b'not image',headers={'content-type':'image/png'})
    assert r.status_code==422

def test_concurrent_catalog_writes(installation):
    c,_,_,_=installation;srv=server()
    def create(i):return c.post(API+'/personal',json={'name':'Synthetic Person '+str(i%20)}).status_code
    with ThreadPoolExecutor(max_workers=12) as pool:results=list(pool.map(create,range(120)))
    assert results.count(200)==20 and results.count(409)==100
    assert len(c.get(API+'/personal').json())==20
    with srv.connect() as db:assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)


def test_corrupt_browser_preferences_and_navigation_storm():
    import shutil,random
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js,HTML
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1100,'height':800});page.set_default_timeout(5000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('dialog',lambda d:d.dismiss());page.evaluate(setup_js)
        page.evaluate('''()=>{const storage={'casting-studio:global-loras:v1':JSON.stringify({version:2,profiles:{'h3_video::h3_ref2va_pruned_checkpoint':{invalid:true},'valid-model':[{name:'Kept.safetensors',multiplier:1,enabled:false}]},legacy:{image:[null]}})};Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>storage[k]??null,setItem:(k,v)=>storage[k]=v}});sessionStorage.setItem('casting-studio:generator:session:v1',JSON.stringify({version:1,boardModel:'h3_video',selectedModels:[],modelSettings:{'h3_video::h3_ref2va_pruned_checkpoint':{loras:[null]}}}))}''')
        page.set_content(HTML,wait_until='domcontentloaded');page.wait_for_function('choices.length===2')
        page.evaluate('openGenerator()');page.wait_for_function("!$('generatorPreview').disabled && !$('generatorSubmit').disabled")
        assert page.evaluate("globalLoraPrefs.profiles['valid-model'][0].enabled===false")
        page.evaluate('closeGenerator()')
        rng=random.Random(2026);tabs=['productions','personal','performers','models','adult','television','workshop']
        for _ in range(250):
            page.evaluate('(t)=>showTab(t)',rng.choice(tabs))
            assert page.evaluate("$('castingSelectionsPanel').hidden===(activeTab==='workshop')")
        assert page.evaluate('choices.length')==2
        assert not errors,errors
        browser.close()

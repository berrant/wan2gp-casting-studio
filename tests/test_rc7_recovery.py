"""RC7: stale references, privacy transitions and damaged templates."""
import io
from PIL import Image
from test_native_plugin import installation, _create_public_selection
from test_rc2_jackhammer import server,seed_reference,API


def test_shared_reference_deletion_preserves_other_record(installation):
    c,_,_,_=installation;s=server();filename='a'*24+'.jpg'
    Image.new('RGB',(800,800)).save(s.REFERENCE_DIR/filename)
    seed_reference(s,'first','passed',filename);seed_reference(s,'second','passed',filename)
    assert c.delete(API+'/reference-images/first').status_code==200
    assert c.get(API+'/reference-images/file/second').status_code==200
    assert c.delete(API+'/reference-images/second').status_code==200
    assert not (s.REFERENCE_DIR/filename).exists()


def test_audit_cannot_apply_old_result_to_replacement(installation,monkeypatch):
    c,_,_,_=installation;s=server();old='a'*24+'.jpg';new='b'*24+'.jpg'
    for filename in (old,new):Image.new('RGB',(800,800)).save(s.REFERENCE_DIR/filename)
    seed_reference(s,'image','passed',old)
    def analyze(im):
        with s.connect() as db:db.execute("UPDATE reference_images SET filename=?,quality_status='reviewed' WHERE id='image'",(new,))
        return {'hard_reasons':['Blurred'],'review_reasons':[],'fingerprint':'0'*16,'sharpness':1,'face_count':0}
    monkeypatch.setattr(s,'analyze_reference_image',analyze)
    r=c.post(API+'/reference-images/audit',params={'person':'Example Person','production':'Example Series'})
    assert r.status_code==200
    assert r.json()['images'][0]['quality_status']=='reviewed'
    assert r.json()['counts']['changed']==1


def test_personal_transition_blocks_public_reference_access(installation):
    c,_,_,_=installation;s=server();filename='a'*24+'.jpg'
    Image.new('RGB',(800,800)).save(s.REFERENCE_DIR/filename);seed_reference(s,'image','passed',filename)
    assert c.get(API+'/reference-images/file/image').status_code==200
    assert c.post(API+'/personal',json={'name':'Example Person'}).status_code==200
    assert c.get(API+'/reference-images/file/image').status_code==403
    assert c.put(API+'/reference-images/image/review',json={'approved':True}).status_code==403
    assert c.delete(API+'/reference-images/image').status_code==403
    assert (s.REFERENCE_DIR/filename).exists()


def test_damaged_templates_keep_catalog_available_and_block_queue(installation):
    c,_,_,_=installation;s=server();key=_create_public_selection(c)
    task={'choice_key':key,'model':'h3_video','scene':1}
    for raw in ('not json','[]','{"video_count":99}'):
        with s.connect() as db:db.execute("INSERT OR REPLACE INTO prompt_settings VALUES ('default',?)",(raw,))
        r=c.get(API+'/prompts/template');assert r.status_code==200
        assert r.headers.get('x-casting-template-warning')
        assert r.json()==s.SAMPLE_TEMPLATE
        r=c.post(API+'/generator/preview',json=task);assert r.status_code==409 and 'reset' in r.json()['detail'].lower()
        with s.connect() as db:assert db.execute("SELECT payload FROM prompt_settings WHERE id='default'").fetchone()[0]==raw
    assert c.post(API+'/prompts/template/reset').status_code==200
    assert c.post(API+'/generator/preview',json=task).status_code==200
    with s.connect() as db:db.execute("INSERT OR REPLACE INTO prompt_settings VALUES ('image_h3_image',?)",('[]',))
    assert c.get(API+'/prompts/image-template?model=h3_image').status_code==409
    assert c.post(API+'/prompts/image-template/reset?model=h3_image').status_code==200
    assert c.get(API+'/prompts/image-template?model=h3_image').status_code==200


def test_phone_photo_orientation_before_metadata_removed(installation):
    c,_,_,_=installation;s=server();image=Image.new('RGB',(120,240),'blue');exif=image.getexif();exif[274]=6
    raw=io.BytesIO();image.save(raw,format='JPEG',exif=exif)
    r=c.post(API+'/images/upload',params={'key':'actress|synthetic'},content=raw.getvalue(),headers={'content-type':'image/jpeg'})
    assert r.status_code==200
    with Image.open(s.PHOTO_DIR/r.json()['url'].split('/')[-1]) as saved:
        assert saved.size==(240,120) and not saved.getexif()


def test_corrupt_override_blocks_only_affected_role(installation):
    c,p,root,_=installation;s=server()
    from test_native_plugin import _mock_fork,FakeWanSession
    _mock_fork(root);p.queue_bridge.api_session=FakeWanSession()
    key=_create_public_selection(c)
    assert c.put(API+'/choices',json={'key':'','person':'Ada Test','character':'Pilot','production':'Example Show','refmod':'Ada_Test_H3.safetensors'}).status_code==200
    other=next(x['key'] for x in c.get(API+'/choices').json() if x['key']!=key)
    with s.connect() as db:db.execute('INSERT INTO prompt_overrides VALUES (?,?)',(key,'null'))
    r=c.get(API+'/prompts/overrides');assert r.status_code==200 and r.headers.get('x-casting-template-warning') and key not in r.json()
    task={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint','scene':1}
    assert c.post(API+'/generator/preview',json=task).status_code==409
    assert c.post(API+'/generator/submit',json=task).status_code==409
    assert not p.queue_bridge._pending
    assert c.post(API+'/generator/preview',json={**task,'choice_key':other}).status_code==200
    assert c.delete(API+'/prompts/overrides/'+key).status_code==200
    assert c.post(API+'/generator/preview',json=task).status_code==200


def test_portrait_rotation_and_metadata_removal(installation):
    c,_,_,_=installation;s=server()
    pid=c.post(API+'/personal',json={'name':'Synthetic Person'}).json()['id']
    raw=io.BytesIO();pic=Image.new('RGB',(120,240));exif=pic.getexif();exif[274]=6;exif[270]='synthetic metadata';pic.save(raw,format='JPEG',exif=exif)
    r=c.post(API+'/personal/'+pid+'/portrait',content=raw.getvalue(),headers={'content-type':'image/jpeg'})
    assert r.status_code==200,r.text
    with Image.open(s.PERSONAL_PORTRAITS/r.json()['portrait_url'].split('/')[-1]) as saved:
        assert saved.size==(240,120) and not saved.getexif()


def test_browser_damaged_template_and_delayed_reference_response():
    import shutil,pytest
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js,HTML
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page();page.set_default_timeout(5000);errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.evaluate('''()=>{const base=window.fetch;window.writes=0;window.recovered=false;window.fetch=async(url,opts={})=>{let u=String(url);if(u==='api/prompts/template/reset'){window.recovered=true;return {ok:true,json:async()=>({video_count:2,name:'Factory'})}}if(u==='api/prompts/template'){if(opts.method==='PUT')window.writes++;return {ok:true,json:async()=>({video_count:2,name:'Factory'}),headers:{get:()=>window.recovered?null:'Saved video template is damaged. Reset it.'}}}if(u.startsWith('api/reference-images?'))return new Promise(resolve=>{window.finishReference=()=>resolve({ok:true,json:async()=>[{id:'old',quality_status:'passed',width:800,height:800}]})});return base(url,opts)}}''')
        page.set_content(HTML,wait_until='domcontentloaded');page.wait_for_function("choices.length===2 && $('quickMusicCheckbox').disabled")
        page.evaluate('toggleQuickMusic(true)');assert page.evaluate('window.writes')==0
        page.evaluate('openEditor()');page.wait_for_function("$('editorStatus').textContent.includes('damaged')")
        page.evaluate('resetEditor()');page.wait_for_function("!$('quickMusicCheckbox').disabled")
        page.evaluate('''()=>{activeImage={collect:true,name:'First',production:'Example'};window.pendingReference=showReferenceCollection();activeImage={collect:true,name:'Second',production:'Example'};$('referenceReviewList').textContent='Second collection';window.finishReference()}''')
        page.evaluate('window.pendingReference');assert page.locator('#referenceReviewList').text_content()=='Second collection'
        assert not errors,errors
        browser.close()

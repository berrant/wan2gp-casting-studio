"""Manual portrait placement and persistent local image saving."""
import io, importlib, shutil
from pathlib import Path
import pytest
from PIL import Image
from test_native_plugin import installation
API='/casting-studio/api'

def test_manual_url_is_archived_and_survives_source_failure(installation,monkeypatch):
    c,p,root,_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    import httpx
    blob=io.BytesIO();Image.new('RGB',(180,220),'#abcdee').save(blob,format='PNG')
    raw=blob.getvalue(); calls=[]
    client_class=httpx.Client
    def handler(req):
        calls.append(str(req.url))
        if req.url.path=='/good.png':return httpx.Response(200,headers={'Content-Type':'image/png'},content=raw)
        return httpx.Response(403)
    monkeypatch.setattr(srv,'validate_public_url',lambda u:'93.184.216.34')
    monkeypatch.setattr(srv.httpx,'Client',lambda **kw:client_class(transport=httpx.MockTransport(handler),**kw))
    key='actress|exampleperson'
    r=c.put(API+'/images/saved',json={'key':key,'url':'https://example.com/good.png'})
    assert r.status_code==200,r.text
    local=r.json()['url'];assert local.startswith('api/photos/') and (srv.PHOTO_DIR/Path(local).name).is_file()
    assert c.get('/casting-studio/'+local).status_code==200
    with srv.connect() as db:
        assert db.execute('SELECT url FROM images WHERE key=?',(key,)).fetchone()[0]==local
        db.execute('INSERT INTO auto_images(key,url,checked) VALUES(?,?,?)',(key,'https://example.com/wrong.png',0))
    assert c.get(API+'/images/cached').json()[key]==local
    r=c.put(API+'/images/saved',json={'key':key,'url':'https://example.com/blocked.png'})
    assert r.status_code==422
    assert c.get(API+'/images/saved').json()[key]==local
    assert c.get(API+'/images/auto',params={'key':key,'actress':'Example Person','kind':'actress'}).json()['url']==local
    assert len(calls)==2

def test_legacy_alias_and_manual_priority(installation,monkeypatch):
    c,p,root,_=installation;srv=importlib.import_module('cb_under_test.app.server')
    monkeypatch.setitem(srv.identity_overrides,'formername','Correct Name')
    old='actress|formername';new='actress|correctname';role='role|formername|captain|testshow2023'
    with srv.connect() as db:
        db.execute('INSERT INTO images VALUES (?,?)',(old,'https://example.com/manual.jpg'))
        db.execute('INSERT INTO images VALUES (?,?)',(role,'https://example.com/role.jpg'))
        db.execute('INSERT INTO auto_images VALUES (?,?,?)',(new,'https://example.com/wrong.jpg',0))
    cache=c.get(API+'/images/cached').json()
    assert cache[new]=='https://example.com/manual.jpg'
    assert cache['role|correctname|captain|testshow']=='https://example.com/role.jpg'
    with srv.connect() as db:db.execute('INSERT INTO images VALUES (?,?)',(new,'https://example.com/replacement.jpg'))
    assert c.get(API+'/images/cached').json()[new]=='https://example.com/replacement.jpg'

def test_url_download_failure_no_new_saved_entry(installation,monkeypatch):
    c,p,root,_=installation;srv=importlib.import_module('cb_under_test.app.server')
    monkeypatch.setattr(srv,'download_image',lambda u:'')
    assert c.put(API+'/images/saved',json={'key':'actress|newperson','url':'https://example.com/unavailable.jpg'}).status_code==422
    assert 'actress|newperson' not in c.get(API+'/images/saved').json()

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium unavailable')
def test_browser_manual_controls_first_and_save_failure_retry():
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    html=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1200,'height':780});page.set_default_timeout(6000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.evaluate('''() => {const orig=window.fetch;window.failSave=true;window.searchCount=0;window.savedBodies=[];window.fetch=async(url,opts={})=>{let data,status=200;const path=String(url);if(path.startsWith('api/images/search?')){window.searchCount++;data={query:'Example',has_more:true,images:Array.from({length:24},(_,i)=>({url:'https://example.com/'+i+'.jpg',thumbnail:'',title:'Photo',width:800,height:900}))};}else if(path==='api/images/saved'){const body=JSON.parse(opts.body);window.savedBodies.push(body);if(window.failSave){status=422;data={detail:'Host unavailable'}}else{data={saved:true,key:body.key,url:'api/photos/'+ 'a'.repeat(64)+'.jpg'}}}else return orig(url,opts);return {ok:status===200,status,json:async()=>data,text:async()=>JSON.stringify(data)}};}''')
        page.set_content(html,wait_until='domcontentloaded');page.wait_for_function('choices.length===2')
        page.evaluate("photos['actress|example']='https://example.com/old.jpg';openPhoto('Example',null,'actress')")
        page.wait_for_function("$('photos').children.length===24")
        assert page.locator('#imageURL').is_visible()
        assert page.evaluate("$('manualPhotoControls').getBoundingClientRect().bottom < $('photos').getBoundingClientRect().top")
        assert page.locator('#imageURL').bounding_box()['y']<780
        page.locator('#modal .panel').evaluate('(e)=>e.scrollTop=e.scrollHeight')
        page.wait_for_timeout(200);assert page.evaluate('window.searchCount')==1
        page.locator('#imageURL').fill('https://example.com/replacement.jpg');page.locator('#manualPhotoSave').click()
        page.wait_for_function("$('manualPhotoStatus').textContent.includes('Previous picture kept')")
        assert page.evaluate("photos['actress|example']")=='https://example.com/old.jpg'
        page.evaluate('window.failSave=false');page.locator('#manualPhotoSave').click()
        page.wait_for_function("!$('modal').classList.contains('open')")
        assert page.evaluate("photos['actress|example']").startswith('api/photos/')
        assert page.evaluate("imageKey('role','Example',{character:'Captain',production:'Test Show (2023)'})")=='role|example|captain|testshow'
        assert not errors,errors;browser.close()

"""Synthetic public character research, local caching and cast action UI."""
import importlib, shutil
from pathlib import Path
import pytest
import httpx
from test_native_plugin import installation, _mock_fork, FakeWanSession, _await_job
API='/casting-studio/api'

@pytest.fixture
def research(installation,monkeypatch):
    c,p,root,_=installation;srv=importlib.import_module('cb_under_test.app.server')
    import sys,types
    calls=[]
    def wiki(client,params):
        calls.append('wiki')
        return {'query':{'pages':[{'title':'Example Alien','extract':'Example Alien appears in Example Series. Example Alien is a blue-skinned alien with horns, portrayed by Example Performer. Other Person has red eyes. She has green hair. Example Alien wears a robe.'},{'title':'Example Series','extract':'Example Alien has silver eyes.'}]}}
    class Search:
        def __init__(self,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def text(self,q,**kw):
            calls.append('search');return [{'title':'Example Alien | Example Wiki','body':'Example Alien appears in Example Series.','href':'https://example.fandom.com/wiki/Example_Alien'}]
    def handler(req):
        calls.append('encyclopedia');return httpx.Response(200,content=b'''<h1 class="page-header__title">Example Alien</h1><div class="mw-parser-output"><p>Appears in Example Series.</p><aside class="portable-infobox"><div class="pi-item pi-data"><div class="pi-data-label">Species</div><div class="pi-data-value">Example species</div></div><div class="pi-item pi-data"><div class="pi-data-label">Skin color</div><div class="pi-data-value">Blue</div></div><div class="pi-item pi-data"><div class="pi-data-label">Wardrobe</div><div class="pi-data-value">Coat</div></div></aside></div>''')
    original=httpx.Client
    monkeypatch.setattr(srv,'wiki_api',wiki);monkeypatch.setitem(sys.modules,'ddgs',types.SimpleNamespace(DDGS=Search))
    monkeypatch.setattr(srv.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    return c,p,root,srv,calls

def test_automatic_traits_and_local_cache(research):
    c,p,root,srv,calls=research
    q={'character':'Example Alien','production':'Example Series','auto':'true'}
    with srv.connect() as db:db.execute('INSERT INTO character_identity_suggestions VALUES (?,?,?,?)',(srv.character_identity_key(q['character'],q['production']),'','',int(srv.time.time())))
    d=c.get(API+'/characters/identity',params=q).json()
    assert d['source']=='researched' and 'blue-skinned' in d['traits'] and 'horns' in d['traits'] and 'silver eyes' in d['traits']
    assert 'Species: Example species' not in d['traits'] and 'https://en.wikipedia.org/wiki/Example_Alien' in d['reference']
    assert all(x not in d['traits'] for x in ('red eyes','green hair','robe','portrayed','Coat'))
    assert calls==['wiki']
    assert c.get(API+'/characters/identity',params=q).json()==d
    assert calls==['wiki']
    # Prompt building is local; identity is included in every still/video segment.
    item={'person':'Example Performer','character':q['character'],'production':q['production'],'refmod':'example.safetensors'}
    for prompt in srv.prompt_for_selection(item,{**srv.SAMPLE_TEMPLATE,'video_count':4}).split('\n\n'):
        assert 'blue-skinned' in prompt
    image=srv.image_prompts_for_selection(item,'flux2_dev',srv.ImageTemplate().model_dump(),srv.SAMPLE_TEMPLATE,{})
    assert all('blue-skinned' in prompt and 'The production-specific character defines the complete physical appearance' in prompt and 'facial identity only' in prompt and 'Example Performer' not in prompt for prompt in image.split('\n\n'))
    assert calls==['wiki']
    assert c.put(API+'/characters/identity',json={**q,'traits':'Custom violet skin'}).status_code==200
    assert c.get(API+'/characters/identity',params={**q,'refresh':'true'}).json()['traits']=='Custom violet skin'
    assert calls==['wiki']

def test_failed_refresh_preserves_cache_and_private_guard(research,monkeypatch):
    c,p,root,srv,calls=research
    q={'character':'Example Alien','production':'Example Series','auto':'true'}
    first=c.get(API+'/characters/identity',params=q).json()
    monkeypatch.setattr(srv,'research_character_traits',lambda *a:('',''))
    assert c.get(API+'/characters/identity',params={**q,'refresh':'true'}).json()==first
    assert c.post(API+'/personal',json={'name':'Example Private','consent':False}).status_code==200
    assert c.get(API+'/characters/identity',params={**q,'character':'Example Private'}).status_code==403
    assert c.get(API+'/characters/identity',params={**q,'production':'Example Private'}).status_code==403
    assert srv.character_identity_traits('Example Alien','Other Series')==''

def test_cast_actions_and_automatic_identity_ui():
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    html=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.evaluate('''() => {const old=window.fetch;window.identityReady=false;window.fetch=async(u,o)=>{const path=String(u);if(path.startsWith('api/characters/identity?')){await new Promise(r=>setTimeout(r,100));window.identityReady=true;return {ok:true,json:async()=>({traits:'Blue skin and horns',source:'researched',reference:'Synthetic source'})}}if(path==='api/generator/preview')return {ok:true,json:async()=>({refmod_filename:'Example.safetensors',prompt:window.identityReady?'Blue skin and horns':'Old prompt'})};return old(u,o)}}''')
        page.set_content(html,wait_until='domcontentloaded');page.wait_for_function('choices.length===2')
        page.evaluate('''() => {catalog={people:[],roles:[],models:[{name:'Installed Example',family:'flux2',path:'flux2/Example.safetensors'},{name:'Convertible Example',family:'minimax_h3',path:'Example_H3.safetensors',convertible_to_flux:true}]};$('promptModel').value='flux2_dev';showProductionCast({production:'Example Series',cast:[{actress:'Installed Example',character:'A',production:'Example Series'},{actress:'Convertible Example',character:'B',production:'Example Series'},{actress:'Missing Example',character:'C',production:'Example Series'}]});}''')
        rows=page.locator('#productionCast .cast-row');assert rows.count()==3
        for i in (0,1):
            assert rows.nth(i).get_by_role('button',name='Select' if i==0 else 'Select for conversion',exact=True).count()==1
            assert rows.nth(i).get_by_role('button',name='Create RefMod').count()==0
            rows.nth(i).locator('details.secondary-actions summary').click()
            assert rows.nth(i).get_by_role('button',name='Collect reference photos').is_visible()
            assert rows.nth(i).get_by_role('button',name='Download image pack').count()==0
        assert 'Conversion required' in rows.nth(1).text_content()
        assert rows.nth(2).get_by_role('button',name='Collect reference photos').count()==1
        assert rows.nth(2).get_by_role('button',name='Create RefMod').count()==0
        page.evaluate("$('promptModel').value='h3_video';openGenerator()")
        page.wait_for_function("$('generatorPreview').value==='Blue skin and horns'")
        assert page.locator('#generatorCharacterTraits').input_value()=='Blue skin and horns'
        page.locator('button[data-workspace=identity]').click()
        assert page.locator('#generatorCharacterPanel').evaluate('(e)=>e.open')
        assert page.locator('#generatorCharacterTraits').is_visible()
        assert not errors,errors
        b.close()

"""Television discovery and opt-in, quality-checked bulk reference collection."""
from pathlib import Path
from types import SimpleNamespace
import sys, shutil
import pytest
from test_native_plugin import installation
API='/casting-studio/api'
NAME='Example Broadcast Anchor'; STATION='Example Local News'; ROLE='Morning news anchor'

def mock_research(monkeypatch):
    calls=[]
    class Search:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def text(self,query,**kwargs):
            calls.append(query)
            return [{'href':'https://example.org/anchor','title':NAME+' - '+STATION,'body':NAME+' is a morning news anchor at '+STATION},
                    {'href':'https://example.org/unrelated','title':'Unrelated Name','body':'Other presenter'}]
    monkeypatch.setitem(sys.modules,'ddgs',SimpleNamespace(DDGS=Search))
    return calls

def test_television_discovery_without_refmod_and_idempotent_credit(installation,monkeypatch):
    c,p,root,_=installation;calls=mock_research(monkeypatch)
    assert c.get(API+'/television/people',params={'q':NAME}).json()==[] and not calls
    data={'name':NAME,'station':STATION}
    result=c.post(API+'/television/research',json=data).json();assert len(result['sources'])==1 and result['suggested_role']==ROLE and len(calls)==1
    assert c.get(API+'/television/people',params={'q':NAME}).json()==[] # lookup never imports on its own
    body={**data,'role':ROLE,'confirmed':False}
    assert c.post(API+'/television/register',json=body).status_code==400
    for _ in range(3):assert c.post(API+'/television/register',json={**body,'confirmed':True}).status_code==200
    for q in (NAME,STATION):
        row=c.get(API+'/television/people',params={'q':q}).json()[0];assert row['name']==NAME and len(row['credits'])==1 and 'TV personality' in row['categories']
    cast=c.get(API+'/productions/cast',params={'production':STATION}).json()['cast'];assert len(cast)==1 and not cast[0]['installed']
    assert c.get(API+'/discovery/people',params={'q':NAME}).json()[0]['name']==NAME
    assert len(c.get(API+'/discovery/credits',params={'name':NAME}).json()['credits'])==1
    assert c.get(API+'/choices').json()==[]
    srv=sys.modules['cb_under_test.app.server'];item={'person':NAME,'character':ROLE,'production':STATION,'refmod':'example.safetensors'}
    text=srv.prompt_for_selection(item,srv.SAMPLE_TEMPLATE);assert 'appearing as themselves, known for their on-air role' in text and 'as portrayed by' not in text
    text=srv.image_prompts_for_selection(item,'h3_image_pruned',srv.ImageTemplate().model_dump(),srv.SAMPLE_TEMPLATE,{})
    assert 'appearing as themselves, known for their on-air role' in text and 'as portrayed by' not in text

def test_personal_names_never_researched_or_registered(installation,monkeypatch):
    c,_,_,_=installation;calls=mock_research(monkeypatch)
    body={'name':'Private Test','relationship':'Friend','notes':'','consent':True,'h3_refmod':'personal/Private_Test_H3.safetensors'}
    assert c.post(API+'/personal',json=body).status_code==200
    assert c.post(API+'/television/research',json={'name':'Private Test'}).status_code==403 and not calls
    assert c.post(API+'/television/register',json={'name':'Private Test','confirmed':True}).status_code==403
    assert c.get(API+'/television/people',params={'q':'Private Test'}).json()==[]

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium unavailable')
def test_television_browser_research_and_bulk_collection(installation,monkeypatch):
    from playwright.sync_api import sync_playwright
    from concurrent.futures import ThreadPoolExecutor
    c,_,_,_=installation;mock_research(monkeypatch)
    srv=sys.modules['cb_under_test.app.server'];monkeypatch.setattr(srv,'fetch_credits',lambda name:([],[]))
    calls=[];saved=[]
    def fetch_api(url,opts):
        path='/casting-studio/'+url.lstrip('/');calls.append(path)
        if path.startswith(API+'/images/search?'):
            return {'status':200,'data':{'query':NAME+' '+STATION,'images':[{'url':'https://example.org/'+str(i)+'.jpg','thumbnail':'','title':'Candidate '+str(i),'source':'https://example.org/anchor','width':800,'height':900,'quality_hint':'candidate'} for i in range(3)],'has_more':False,'web_search':'https://example.org'}}
        if path==API+'/reference-images' and opts.get('method')=='POST':
            import json
            item=json.loads(opts['body']);saved.append(item)
            return {'status':409 if len(saved)==2 else 200,'data':{'quality_status':'passed'}}
        with ThreadPoolExecutor(max_workers=1) as pool:r=pool.submit(c.request,opts.get('method','GET'),path,content=opts.get('body'),headers={'Content-Type':'application/json'}).result()
        try:payload=r.json()
        except ValueError:payload=r.text
        return {'status':r.status_code,'data':payload}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1440,'height':950});page.set_default_timeout(8000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.expose_function('testFetch',fetch_api)
        page.evaluate("""() => {const makeStorage=()=>{const m=new Map();return {getItem:k=>m.get(k)||null,setItem:(k,v)=>m.set(k,v),removeItem:k=>m.delete(k)}};Object.defineProperty(window,'localStorage',{value:makeStorage()});Object.defineProperty(window,'sessionStorage',{value:makeStorage()});window.fetch=async (url,opts={})=>{const r=await window.testFetch(String(url),opts);return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.data,text:async()=>typeof r.data==='string'?r.data:JSON.stringify(r.data)}};}""")
        page.set_content((Path(__file__).resolve().parents[1]/'app/index.html').read_text(),wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('#productionSearchStatus').textContent.includes('Type a title')")
        page.locator('#peopleMenuButton').click();page.locator('[data-people-category=\"'+str('television')+'\"]').click();assert page.locator('#televisionSection').is_visible() and not page.locator('#browseSection').is_visible()
        assert not any('/television/' in x for x in calls)
        page.locator('#televisionName').fill(NAME);page.locator('#televisionStation').fill(STATION)
        page.locator('#televisionResearchButton').click();page.locator('#televisionConfirmed').wait_for();assert page.locator('#televisionConfirmRole').input_value()==ROLE
        page.locator('#televisionSave').click();assert not any('/television/register' in x for x in calls)
        page.locator('#televisionConfirmed').check();page.locator('#televisionSave').click()
        page.locator('#modal').wait_for();page.wait_for_function("document.querySelectorAll('.bulk-reference-check').length===3")
        for checkbox in page.locator('.bulk-reference-check').all():checkbox.check()
        page.once('dialog',lambda d:d.accept());page.locator('#bulkPhotoCollect').click();page.get_by_text('2 saved or already collected · 1 skipped; inspect skipped candidates individually.',exact=True).wait_for()
        assert len(saved)==3 and all(s['person']==NAME and s['production']==STATION and not s['accept_review'] for s in saved)
        assert not errors,errors;browser.close()

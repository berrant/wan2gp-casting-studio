"""Cross-chat regression gate for current beta; uses fake WanGP, no GPU."""
from test_native_plugin import reviewed_submit
import json
import shutil
import pytest
from test_native_plugin import installation, _mock_fork, FakeWanSession, _create_public_selection, _await_job
API='/casting-studio/api'

def add_example_cast(c):
    assert c.post(API+'/productions',json={'name':'Example Series','kind':'series','year':2023}).status_code==200
    for name,role in [('Example Performer','Example Captain'),('Example Second','Example Engineer'),('Example Third','Example Doctor'),('Example Fourth','Example Pilot')]:
        assert c.post(API+'/productions/cast',json={'actress':name,'character':role,'production':'Example Series','year':2023}).status_code==200

def test_discovery_without_installed_mods_and_private_consent(installation):
    c,p,root,_=installation
    assert c.get(API+'/productions').json()==[]
    assert c.get(API+'/productions',params={'q':'Example Series'}).json()==[]
    add_example_cast(c)
    shows=c.get(API+'/productions',params={'q':'Example Series'}).json()
    assert any(x['name']=='Example Series' and x['year']==2023 for x in shows)
    cast=c.get(API+'/productions/cast',params={'production':'Example Series'}).json()['cast']
    assert len(cast)>=4 and all(not x['installed'] for x in cast)
    people=c.get(API+'/discovery/people',params={'q':'Example Series'}).json()
    assert any(x['name']=='Example Performer' for x in people)
    assert c.get(API+'/discovery/credits',params={'name':'Example Performer'}).json()['credits']
    data={'name':'Private Test','relationship':'Friend','notes':'PRIVATE NOTES','consent':False,'h3_refmod':'personal/Private_Test_H3.safetensors'}
    assert c.post(API+'/personal',json=data).status_code==200
    assert c.get(API+'/discovery/credits',params={'name':'Private Test'}).status_code==403
    assert not c.get(API+'/discovery/people',params={'q':'Private Test'}).json()
    assert c.get(API+'/personal/refmods').json()[0]['path']=='personal/Private_Test_H3.safetensors'

def test_window_lora_native_payload(installation):
    c,p,root,_=installation;_mock_fork(root)
    session=FakeWanSession();session.defs[0]['sliding_window']=True
    session.list_loras=lambda model:{'supported':True,'loras':['a.safetensors','b.safetensors']}
    p.queue_bridge.api_session=session
    # Override catalog only to simulate installed models in this isolated test.
    p.queue_bridge._lora_catalog=lambda *args:{'supported':True,'loras':['a.safetensors','b.safetensors']}
    key=_create_public_selection(c)
    body={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint','video_seconds':60,'video_script_mode':'sequence','sliding':{'sliding_window_size':362,'sliding_window_overlap':18},'loras':[{'name':'a.safetensors','multiplier':1.5},{'name':'b.safetensors','multiplier':0}], 'window_loras':{'b.safetensors':[0,.8,0,0]}}
    r=reviewed_submit(c,API+'/generator/submit',json=body);assert r.status_code==200,r.text
    assert _await_job(c,r.json()['id'])['state']=='completed'
    task=session.submitted[-1];assert task['activated_loras']==['a.safetensors','b.safetensors'];assert task['loras_multipliers']=='1.5 0'
    assert [part.split(']')[0]+']' for part in task['prompt'].split('\n\n')]==['[/loras_mult=1.5 0]','[/loras_mult=1.5 0.8]','[/loras_mult=1.5 0]','[/loras_mult=1.5 0]']
    assert c.post(API+'/generator/submit',json={**body,'window_loras':{'b.safetensors':[7]}}).status_code==400

def test_browser_navigation_search_personal_and_lora_profiles(installation):
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    c,p,root,_=installation
    add_example_cast(c)
    data={'name':'Private Test','relationship':'Friend','notes':'private','consent':False,'h3_refmod':'personal/Private_Test_H3.safetensors'}
    assert c.post(API+'/personal',json=data).status_code==200
    from urllib.parse import urlsplit
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1440,'height':950});page.set_default_timeout(6000)
        errors=[];calls=[];page.on('pageerror',lambda e:errors.append(str(e)))
        def fetch_api(url,opts):
            from concurrent.futures import ThreadPoolExecutor
            path=API.rsplit('/api',1)[0]+'/'+url.lstrip('/')
            calls.append(path)
            if 'api/generator/models?' in path:
                return {'status':200,'data':{'models':[{'model_type':'test_model','name':'Test model','ready':True}]}}
            if 'api/generator/model-details?' in path:
                return {'status':200,'data':{'model_type':'test_model','loras':['a.safetensors','b.safetensors'],'lora_supported':True,'resolutions':[],'sliding_window_supported':True}}
            with ThreadPoolExecutor(max_workers=1) as pool:
                response=pool.submit(c.request,opts.get('method','GET'),path,content=opts.get('body'),headers={'Content-Type':'application/json'}).result()
            try:data=response.json()
            except ValueError:data=response.text
            return {'status':response.status_code,'data':data}
        page.expose_function('testFetch',fetch_api)
        page.evaluate("""() => {const makeStorage=()=>{const m=new Map();return {getItem:k=>m.get(k)||null,setItem:(k,v)=>m.set(k,v),removeItem:k=>m.delete(k)}};Object.defineProperty(window,'localStorage',{value:makeStorage()});Object.defineProperty(window,'sessionStorage',{value:makeStorage()});window.fetch=async (url,opts={})=>{const r=await window.testFetch(String(url),opts);return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.data,text:async()=>typeof r.data==='string'?r.data:JSON.stringify(r.data)}};}""")
        from pathlib import Path
        page.set_content((Path(__file__).resolve().parents[1]/'app/index.html').read_text(),wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('#productionSearchStatus').textContent.includes('Type a title')")
        assert page.locator('#productionSection').is_visible();assert not page.locator('#browseSection').is_visible()
        assert not any(x.startswith(API+'/productions?') for x in calls)
        assert page.locator('#navTabs #modelsTab').count()==0
        assert 'Models / Influencers' in page.locator('#peopleMenu').text_content()
        page.locator('#productionQuery').fill('Example Series')
        page.locator('#productionMatches').get_by_role('button',name='View cast',exact=True).first.click()
        page.wait_for_function("document.querySelector('#productionCast').textContent.includes('Example Captain')")
        assert page.locator('#productionCast').get_by_text('Collect reference photos').count()>=4
        page.locator('#peopleMenuButton').click();page.locator('[data-people-category=\"'+str('personal')+'\"]').click()
        page.get_by_text('Consent not obtained',exact=True).wait_for()
        assert page.locator('.consent-no').count()==1
        page.get_by_role('button',name='Edit profile',exact=True).click()
        assert page.locator('#personalH3').input_value()=='personal/Private_Test_H3.safetensors'
        page.locator('#personalModal').get_by_role('button',name='Cancel',exact=True).click()
        page.get_by_role('button',name='Local paths and settings',exact=True).click()
        page.locator('#defaultLorasSettings summary').click()
        page.wait_for_function("!document.querySelector('#globalAddLora').disabled")
        page.locator('#globalAddLora').click()
        page.wait_for_function("document.querySelector('#globalModelLoraRows select') !== null")
        assert page.locator('#globalModelLoraRows select').input_value()=='a.safetensors'
        assert not errors,errors
        browser.close()

def test_personal_shared_templates_neutral_background(installation):
    c,p,root,_=installation
    data={'name':'Private Test','relationship':'Friend','notes':'PRIVATE NOTES','consent':True,'h3_refmod':'personal/Private_Test_H3.safetensors'}
    assert c.post(API+'/personal',json=data).status_code==200
    pid=c.get(API+'/personal').json()[0]['id']
    assert c.put(API+'/choices',json={'key':'','person':'Private Test','character':'','production':'','refmod':data['h3_refmod'],'personal_id':pid}).status_code==200
    template=c.get(API+'/prompts/template').json();template.update({'wardrobe':'A blue jacket and green trousers','video1_action':'She walks toward the camera.','setting':'Unrelated mountain landscape','include_non_diegetic_music':True,'include_caption':True})
    assert c.put(API+'/prompts/template',json=template).status_code==200
    key=c.get(API+'/choices').json()[0]['key']
    r=c.post(API+'/generator/preview',json={'choice_key':key,'model':'h3_video','scene':1});assert r.status_code==200,r.text
    for text in (r.json()['prompt'],c.get(API+'/prompts/export?model=h3_video').text):
        assert 'She walks toward the camera.' in text and 'A blue jacket and green trousers' in text
        assert 'neutral gray photography studio' in text and 'Unrelated mountain landscape' not in text
        assert 'PRIVATE NOTES' not in text and 'Private Test - Friend' in text

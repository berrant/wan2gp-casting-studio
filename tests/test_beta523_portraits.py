import io,json
from types import SimpleNamespace
from PIL import Image
from test_native_plugin import installation,_mock_fork,FakeWanSession,FakeTaskHandle,_await_job
API='/casting-studio/api'

def setup(installation):
    c,p,root,_=installation;_mock_fork(root)
    data={'name':'Private Test','relationship':'Friend','notes':'SECRET','consent':True,'h3_refmod':'personal/Private_Test_H3.safetensors'}
    pid=c.post(API+'/personal',json=data).json()['id']
    model={'model_type':'custom_h3_image','architecture':'minimax_h3_image_pruned','name':'Custom H3 image','custom_settings':[{'id':'h3_refmod_state'}]}
    session=FakeWanSession([model]);session.get_default_settings=lambda model: {"resolution":"1024x1024"};p.queue_bridge.api_session=session
    p.queue_bridge.dispatch_mode='gradio'
    out=root/'result.png';Image.new('RGB',(300,300),'blue').save(out)
    def submit(settings,callbacks=None):
        session.submitted.append(settings);return FakeTaskHandle(SimpleNamespace(success=True,generated_files=['result.png'],errors=[],cancelled=False))
    session.submit_task=submit
    base=API+'/personal/'+pid;body={'model':'h3_image_pruned','model_type':'custom_h3_image'}
    return c,p,session,base,body,data,out

def upload(c,base):
    buf=io.BytesIO();Image.new('RGB',(160,160),'red').save(buf,format='PNG')
    r=c.post(base+'/portrait',content=buf.getvalue(),headers={'Content-Type':'image/png'});assert r.status_code==200,r.text
    return r.json()['portrait_url']

def test_one_native_portrait_auto_saved_no_selection_or_template_mutation(installation):
    c,p,s,base,body,data,out=setup(installation)
    models=c.get(base+'/portrait-models').json();assert models==[{'model':'h3_image_pruned','model_type':'custom_h3_image','name':'Custom H3 image'}]
    original=s.merge_settings_with_defaults
    s.merge_settings_with_defaults=lambda x:{**original(x),'batch_size':5,'repeat_generation':9}
    before=c.get(API+'/prompts/image-template?model=h3_image_pruned').json()
    r=c.post(base+'/portrait-generate',json=body);assert r.status_code==200,r.text
    jid=r.json()['id'];assert not s.submitted
    assert c.post(base+'/portrait-generate',json=body).status_code==409
    p.queue_bridge.process_pending_in_gradio(s)
    state=_await_job(c,jid);assert state['state']=='completed',state
    assert len(s.submitted)==1;task=s.submitted[0]
    assert task['batch_size']==task['repeat_generation']==1
    assert task['model_type']==body['model_type'] and 'neutral gray studio' in task['prompt'] and 'SECRET' not in task['prompt']
    assert json.loads(task['custom_settings']['h3_refmod_state'])['rows'][0]['use_audio'] is False
    assert c.get(API+'/choices').json()==[]
    assert c.get(API+'/prompts/image-template?model=h3_image_pruned').json()==before
    url=c.get(API+'/personal').json()[0]['portrait_url'];assert url==state['portrait_url']
    assert c.get('/casting-studio/'+url).status_code==200
    assert c.post(base+'/portrait-generate',json=body).status_code==409

def test_revocation_before_relay_and_during_completion(installation):
    c,p,s,base,body,data,out=setup(installation)
    url=upload(c,base);body['replace']=True
    r=c.post(base+'/portrait-generate',json=body);assert r.status_code==200,r.text
    assert c.put(base,json={**data,'consent':False}).status_code==200
    p.queue_bridge.process_pending_in_gradio(s);assert _await_job(c,r.json()['id'])['state']=='failed';assert not s.submitted
    assert c.post(base+'/portrait-generate',json=body).status_code==403
    assert c.put(base,json=data).status_code==200
    r=c.post(base+'/portrait-generate',json=body);assert r.status_code==200,r.text
    old=s.submit_task
    def revoke(settings,callbacks=None):
        handle=old(settings,callbacks);assert c.put(base,json={**data,'consent':False}).status_code==200;return handle
    s.submit_task=revoke;p.queue_bridge.process_pending_in_gradio(s)
    assert _await_job(c,r.json()['id'])['state']=='failed';assert c.get(API+'/personal').json()[0]['portrait_url']==url

def test_bad_output_and_concurrent_upload_preserve_portrait(installation):
    c,p,s,base,body,data,out=setup(installation);url=upload(c,base);body['replace']=True
    old=s.submit_task
    for files in ([],['missing.png'],['result.png','result.png']):
        s.submit_task=lambda settings,callbacks=None:FakeTaskHandle(SimpleNamespace(success=True,generated_files=files,errors=[],cancelled=False))
        r=c.post(base+'/portrait-generate',json=body);assert r.status_code==200,r.text
        p.queue_bridge.process_pending_in_gradio(s);assert _await_job(c,r.json()['id'])['state']=='failed'
        assert c.get(API+'/personal').json()[0]['portrait_url']==url
    r=c.post(base+'/portrait-generate',json=body);assert r.status_code==200,r.text
    s.submit_task=old;new=upload(c,base);p.queue_bridge.process_pending_in_gradio(s)
    assert _await_job(c,r.json()['id'])['state']=='failed';assert c.get(API+'/personal').json()[0]['portrait_url']==new
    assert c.post(base+'/portrait-generate',json={**body,'model':'h3_video'}).status_code==400
    assert c.post(base+'/portrait-generate',json={**body,'model_type':'wrong'}).status_code==400

def test_repeated_replacement(installation):
    c,p,s,base,body,data,out=setup(installation)
    for i in range(12):
        r=c.post(base+'/portrait-generate',json={**body,'replace':True});assert r.status_code==200,r.text
        p.queue_bridge.process_pending_in_gradio(s);assert _await_job(c,r.json()['id'])['state']=='completed'
    assert len(s.submitted)==12
    assert len(list((installation[2]/'user_data'/'personal_portraits').glob('*.webp')))==1

def test_browser_single_portrait_dialog(installation):
    import shutil,pytest
    from pathlib import Path
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    c,p,s,base,body,data,out=setup(installation)
    requests=[]
    def fetch_api(url,opts):
        from concurrent.futures import ThreadPoolExecutor
        path='/casting-studio/'+url.lstrip('/');requests.append(path)
        with ThreadPoolExecutor(max_workers=1) as pool:
            r=pool.submit(c.request,opts.get('method','GET'),path,content=opts.get('body'),headers={'Content-Type':'application/json'}).result()
            if path.endswith('/portrait-generate') and r.status_code==200:pool.submit(p.queue_bridge.process_pending_in_gradio,s).result()
        try:payload=r.json()
        except ValueError:payload=r.text
        return {'status':r.status_code,'data':payload}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1440,'height':950});page.set_default_timeout(8000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.expose_function('testFetch',fetch_api)
        page.evaluate("""() => {const makeStorage=()=>{const m=new Map();return {getItem:k=>m.get(k)||null,setItem:(k,v)=>m.set(k,v),removeItem:k=>m.delete(k)}};Object.defineProperty(window,'localStorage',{value:makeStorage()});Object.defineProperty(window,'sessionStorage',{value:makeStorage()});window.fetch=async (url,opts={})=>{const r=await window.testFetch(String(url),opts);return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.data,text:async()=>typeof r.data==='string'?r.data:JSON.stringify(r.data)}};}""")
        page.set_content((Path(__file__).resolve().parents[1]/'app/index.html').read_text(),wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('#productionSearchStatus').textContent.includes('Type a title')")
        page.locator('#peopleMenuButton').click();page.locator('[data-people-category=\"'+str('personal')+'\"]').click()
        page.get_by_role('button',name='Generate portrait',exact=True).click()
        page.wait_for_function("!document.querySelector('#portraitQueue').disabled")
        assert 'Custom H3 image' in page.locator('#portraitModel').inner_text()
        assert not page.locator('#generatorModal').is_visible()
        page.locator('#portraitQueue').click()
        page.get_by_text('Profile portrait saved.',exact=True).wait_for()
        assert page.locator('#personalList img.personal-portrait').count()==1
        assert len(s.submitted)==1 and not any('/generator/batch/' in r for r in requests)
        assert not errors,errors
        browser.close()

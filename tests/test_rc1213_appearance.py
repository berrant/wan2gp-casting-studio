"""Synthetic local references and mocked native inference, no real GPU."""
import importlib
from contextlib import contextmanager
from PIL import Image
import pytest
from test_native_plugin import installation

class FakeNative:
    def __init__(self):self.loads=0;self.releases=0;self.calls=[]
    def options(self):return [{'id':'3','label':'Qwen 4B','backend':'quanto_int8'},{'id':'4','label':'Qwen 9B','backend':'gguf'}]
    @contextmanager
    def session(self,state,engine,stop):
        self.loads+=1
        def analyze(label,images):
            self.calls.append((label,engine,len(images)))
            assert all(i.mode=='RGB' and max(i.size)<=1024 for i in images)
            return 'Distinctive green skin and ridged forehead.'
        try:yield analyze
        finally:self.releases+=1

@pytest.fixture
def app(installation):
    client,plugin,root,_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    native=FakeNative();bridge=plugin.vision_bridge;bridge.native=native;bridge.ready=True
    prefix='/casting-studio/api';roles=[]
    for i in (1,2):
        role=dict(key='',person='Ada Test',character=f'Example Alien {i}',production='Example Series',year=2023,refmod='Ada_Test_H3.safetensors')
        res=client.put(prefix+'/choices',json=role);assert res.status_code==200,res.text
        key=srv.canonical_role_key(role['person'],role['character'],role['production']);filename=f'{i:024x}.jpg'
        Image.new('RGB',(120,160),(10*i,80,20)).save(srv.REFERENCE_DIR/filename)
        with srv.connect() as db:db.execute('INSERT INTO reference_images (id,person,production,character,source_url,page_url,filename,width,height,quality_status) VALUES (?,?,?,?,?,?,?,?,?,?)',(str(i),role['person'],'Example Series (2023)',role['character'],'','',filename,120,160,'passed'))
        roles.append(dict(choice_key=key,image_ids=[str(i)]))
    return client,prefix,srv,bridge,native,roles

def stage(a,roles=None,engine='3'):
    c,p,s,b,n,r=a
    return c.post(p+'/appearance/batch',json={'engine':engine,'selections':roles if roles is not None else r})

def run(a,job):
    c,p,s,b,n,r=a;b.run(job,{'gen':{}},s.resolve_appearance_images)
    return c.get(p+'/appearance/batch/'+job).json()

def approve(a,job,index=0,traits='Approved green skin and ridged forehead.'):
    c,p,*_=a;return c.post(p+'/appearance/batch/'+job+'/approve',json=dict(index=index,traits=traits))

def test_batch_approval_and_persistent_portrayal_scope(app):
    c,p,s,b,n,r=app
    opts=c.get(p+'/appearance/options').json();assert opts['default']=='3';assert len(opts['models'])==2
    assert c.get(p+'/appearance/references',params={'choice_key':r[0]['choice_key']}).json()['photos'][0]['id']=='1'
    res=stage(app,engine='4');assert res.status_code==200,res.text;job=res.json()['id'];assert n.loads==0
    assert stage(app).status_code==409
    result=run(app,job);assert result['state']=='completed',result;assert n.loads==n.releases==1;assert len(n.calls)==2
    assert all(x['state']=='review' for x in result['results']);assert all(x[1]=='4' for x in n.calls)
    role=result['results'][0];key=role['profile_key'];assert s.exact_identity_snapshot(key) is None
    assert approve(app,job).status_code==200;assert approve(app,job).status_code==409
    assert s.character_identity_traits('Example Alien 1','Example Series','Ada Test',2023).startswith('Approved green')
    assert s.exact_identity_snapshot(s.portrayal_identity_key('Example Alien 1','Example Series','Ada Test',2024)) is None
    assert s.exact_identity_snapshot(s.portrayal_identity_key('Example Alien 1','Example Series','Other Test',2023)) is None
    assert s.exact_identity_snapshot(result['results'][1]['profile_key']) is None
    assert c.get(p+'/appearance/references',params={'choice_key':r[0]['choice_key']}).json()['saved']['year']==2023
    item=next(x for x in c.get(p+'/choices').json() if x['key']==r[0]['choice_key'])
    assert 'Approved green skin' in str(s.prompt_for_selection(item,s.SAMPLE_TEMPLATE))
    for model in ('h3_image','flux2_dev'):
        if model in s.MODEL_BY_ID:
            assert 'Approved green skin' in str(s.image_prompts_for_selection(item,model,s.image_template_normalized(),s.SAMPLE_TEMPLATE,{}))
    assert n.loads==1

def test_reject_wrong_role_and_duplicate_sources(app):
    c,p,s,b,n,r=app
    assert stage(app,[{**r[0],'image_ids':['2']}]).status_code==400
    assert stage(app,[{**r[0],'image_ids':['1','1']}]).status_code==400
    assert stage(app,[r[0],r[0]]).status_code==400
    assert stage(app,engine='99').status_code==409
    assert n.loads==0

def test_stale_reference_before_and_after_analysis(app):
    c,p,s,b,n,r=app
    job=stage(app).json()['id']
    path=s.REFERENCE_DIR/f'{1:024x}.jpg';Image.new('RGB',(120,160),'red').save(path)
    result=run(app,job);assert result['results'][0]['state']=='failed';assert len(n.calls)==1
    assert approve(app,job,0).status_code==409
    path=s.REFERENCE_DIR/f'{2:024x}.jpg';Image.new('RGB',(120,160),'blue').save(path)
    assert approve(app,job,1).status_code==409

def test_manual_edit_not_overwritten_and_cancel(app):
    c,p,s,b,n,r=app
    job=stage(app).json()['id'];result=run(app,job)
    assert c.put(p+'/characters/identity',json={'person':'Ada Test','character':'Example Alien 1','production':'Example Series','year':2023,'traits':'Manual edit'}).status_code==200
    assert approve(app,job).status_code==409
    assert s.exact_identity_snapshot(result['results'][0]['profile_key'])[0]=='Manual edit'
    job=stage(app).json()['id'];assert c.post(p+'/appearance/batch/'+job+'/cancel').status_code==200
    assert run(app,job)['state']=='cancelled';assert n.loads==1

def test_expired_staged_handoff_does_not_run(app):
    c,p,s,b,n,r=app;job=stage(app).json()['id'];b.job['_created']-=91
    assert run(app,job)['state']=='failed';assert n.loads==0

from test_dev55_browser import page

def test_browser_model_picker_and_reference_selection(page):
    tab,errors=page
    tab.evaluate('''()=>{const orig=fetch;window.fetch=async(u,o={})=>{let d;const url=String(u);if(url==='api/appearance/options')d={ready:true,default:'3',models:[{id:'3',label:'Qwen 4B',backend:'quanto_int8'},{id:'4',label:'Qwen 9B',backend:'gguf'}]};else if(url==='api/choices')d=[{key:'a',person:'Ada Test',character:'Example Alien',production:'Example Series',year:2023}];else if(url.startsWith('api/appearance/references?'))d={role:{label:'Example Alien portrayed by Ada Test in Example Series (2023)'},photos:Array.from({length:5},(_,i)=>({id:String(i),url:'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',label:'Reference '+i,dated:true}))};else return orig(u,o);return {ok:true,json:async()=>d,text:async()=>JSON.stringify(d)};};openAppearance('batch');}''')
    tab.wait_for_function("document.querySelectorAll('#appearanceRoles img').length===5")
    assert tab.locator('#appearanceEngine').input_value()=='3'
    tab.locator('#appearanceEngine').select_option('4')
    assert tab.locator('#appearanceEngine').input_value()=='4'
    tab.locator('#appearanceRoles details summary').click() if not tab.locator('#appearanceRoles details').evaluate('(e)=>e.open') else None
    tab.locator('#appearanceRoles input[type=checkbox]').last.click()
    assert tab.locator('#appearanceRoles input[type=checkbox]:checked').count()==5 # one role plus four references
    assert 'four pictures' in tab.locator('#appearanceStatus').inner_text()
    assert not errors,errors

def test_native_adapter_load_and_release_once_and_fail_closed(app,monkeypatch):
    from types import SimpleNamespace as NS
    import sys
    from contextlib import nullcontext
    c,p,s,b,n,r=app
    mod=importlib.import_module('cb_under_test.vision_bridge'); events=[]
    state={'gen':{}}
    host=NS(_deepy_hybrid=NS(_state=state),server_config={'prompt_enhancer_quantization':'gguf_q3'},global_queue_ref=[],init_pipe=lambda *args:0,offloadobj=NS(unload_all=lambda:events.append('main-unload')))
    qwen=NS(get_qwen35_prompt_enhancer_variant=lambda i:{3:'4b',4:'9b'}[i],get_qwen35_variant_spec=lambda v:{'display_name':v,'vision_filename':'vision','text_int8':'int8'},get_qwen35_quantization=lambda backend,variant:backend,QWEN_CHECKPOINTS={'quanto_int8':('text_int8','int8')})
    runtime=NS(image_caption_model=NS(generate_image_captions=lambda:None),image_caption_processor=None,llm_model=NS(),llm_tokenizer=None,pipe_models={},budgets={},co_tenants={})
    missing=[False];busy=[False]
    def ensure(check,**kwargs):check(repoId='synthetic')
    def load(check,**kwargs):events.append(('load',kwargs['enhancer_enabled']));ensure(check,**kwargs);return runtime
    def acquire(st,process,label):assert st is state;events.append('acquire');return not busy[0]
    def release(st,process):assert st is state;events.append('release')
    def generate(a,b,c,d,prompts,images=None,**kwargs):
        if images is None:
            assert kwargs['image_contexts'] is None and 'vision' not in kwargs
            assert kwargs['max_new_tokens']==768 and 'wardrobe' in kwargs['prompt_enhancer_instructions']
            events.append('text-infer');return ['{"wardrobe":"Blue coat","setting":"Starship bridge"}']
        assert len(kwargs['image_contexts'][0][0])==len(images);assert kwargs['vision']['max_tokens']==384;events.append('infer');return ['Stable physical traits.']
    modules={'shared.prompt_enhancer.qwen35_vl':qwen,'shared.utils.process_locks':NS(try_acquire_GPU_ressources=acquire,release_GPU_ressources=release),'shared.prompt_enhancer.loader':NS(load_prompt_enhancer_runtime=load,ensure_prompt_enhancer_assets=ensure,unload_prompt_enhancer_models=lambda *x:events.append('unload')),'shared.utils.download':NS(download_def_missing_files=lambda d:['missing'] if missing[0] else []),'shared.prompt_enhancer.prompt_enhance_utils':NS(generate_cinematic_prompt=generate),'shared.prompt_enhancer.images':NS(ImageContext=lambda images,labels:(images,labels)),'mmgp':NS(offload=NS(profile=lambda *a,**k:NS(release=lambda:events.append('offload-release')))),'shared.utils.model_unload':NS(wait_for_model_unload=lambda:None,model_unload_guard=nullcontext),'shared.utils.offload_registry':NS(unload_vram=lambda:events.append('registry-unload'))}
    for name,stub in modules.items():monkeypatch.setitem(sys.modules,name,stub)
    native=mod.NativeVision(host);assert native.shared_state() is state;assert native.options()[0]=={'id':'3','label':'4b','backend':'quanto_int8'}
    missing[0]=True
    with pytest.raises(mod.VisionUnavailable,match='missing'):
        with native.session(state,'3',lambda:False):pass
    assert not events
    missing[0]=False;busy[0]=True
    with pytest.raises(mod.VisionUnavailable,match='busy'):
        with native.session(state,'3',lambda:False):pass
    assert events==['acquire'];events.clear();busy[0]=False
    with native.session(state,'3',lambda:False) as analyze:
        with Image.new('RGB',(80,80)) as img:
            assert analyze('Example 1',[img])=='Stable physical traits.'
            assert analyze('Example 2',[img,img])=='Stable physical traits.'
    assert events==['acquire','main-unload','registry-unload',('load',3),'infer','infer','unload','offload-release','release']
    assert host.server_config=={'prompt_enhancer_quantization':'gguf_q3'}
    events.clear()
    with native.text_session(state,'3',lambda:False) as analyze:
        assert mod.parse_scene_draft(analyze(mod.SCENE_REQUEST_PREFIX+'Exact dated portrayal',[]))['setting']=='Starship bridge'
    assert events==['acquire','main-unload','registry-unload',('load',3),'text-infer','unload','offload-release','release']
    events.clear()
    # A queued generation takes priority, even if it arrives during lock acquisition.
    host.global_queue_ref.append('synthetic queued generation')
    with pytest.raises(mod.VisionBusy,match='queued'):
        with native.session(state,'3',lambda:False):pass
    assert not events
    host.global_queue_ref.clear()
    def acquire_race(st,process,label):
        events.append('acquire');state['gen']['queue']=['synthetic queued generation'];return True
    modules['shared.utils.process_locks'].try_acquire_GPU_ressources=acquire_race
    with pytest.raises(mod.VisionBusy,match='queued'):
        with native.session(state,'3',lambda:False):pass
    assert events==['acquire','release']
    state['gen'].pop('queue');events.clear()
    modules['shared.utils.process_locks'].try_acquire_GPU_ressources=acquire
    with pytest.raises(mod.VisionUnavailable,match='state'):
        with native.session({'gen':{}},'3',lambda:False):pass
    assert not events

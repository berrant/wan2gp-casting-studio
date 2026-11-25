"""RC12.3 workflow tests using synthetic data and browser mocks."""
from types import SimpleNamespace as NS
import json
from test_native_plugin import installation, _mock_fork, _create_public_selection
from test_dev512_image_sets import _image_session, _set_image_template
from test_persona_power import tab
from test_rc2_jackhammer import server
API='/casting-studio/api'

def setup(installation):
    c,p,root,_=installation;_mock_fork(root);session=_image_session();b=p.queue_bridge
    b.api_session=session;b.dispatch_mode='gradio';key=_create_public_selection(c);_set_image_template(c,count=2)
    req={'task':{'choice_key':key,'model':'h3_image_pruned','model_type':'h3_image_pruned_checkpoint'},'scope':'selection:'+key,'scene_mode':'all'}
    return c,b,session,req

def test_preflight_no_submission_and_invalid_refmod(installation):
    c,b,session,req=setup(installation)
    r=c.post(API+'/generator/batch/preflight',json=req);assert r.status_code==200,r.text
    d=r.json();assert d['count']==2 and d['ready']==2 and d['relay_ready'] and not b._pending
    s=server()
    with s.connect() as db:
        key,raw=db.execute('SELECT key,payload FROM choices').fetchone();item=json.loads(raw);item['refmod']='missing.safetensors';db.execute('UPDATE choices SET payload=? WHERE key=?',(json.dumps(item),key))
    r=c.post(API+'/generator/batch/preflight',json=req);assert r.status_code==200,r.text
    d=r.json();assert d['blocked']==2 and len(d['issues'])==2 and not b._pending

def test_history_and_exact_retry(installation):
    c,b,session,req=setup(installation);manifests=[]
    def submit(settings,callbacks=None):
        manifests.append(settings)
        res=NS(success=False,generated_files=['synthetic-output.png'],errors=[NS(task_index=2,message='test failure',cancelled=False)],failed_tasks=1,cancelled=False) if len(manifests)==1 else NS(success=True,generated_files=['synthetic-retry.png'],errors=[],cancelled=False)
        return NS(result=lambda:res,cancel=lambda:None,webui_client_ids=[])
    session.submit_manifest=submit
    r=c.post(API+'/generator/batch/submit',json=req);assert r.status_code==200,r.text;jid=r.json()['id'];b.process_pending_in_gradio(session)
    d=c.get(API+'/generator/history').json()['jobs'][0];assert d['id']==jid and d['state']=='failed' and d['retry_count']==1 and 'choice_key' not in d['settings']
    r=c.post(API+'/generator/jobs/'+jid+'/retry-failed');assert r.status_code==200,r.text;assert r.json()['task_count']==1
    assert c.post(API+'/generator/jobs/'+jid+'/retry-failed').status_code==400
    b.process_pending_in_gradio(session);assert len(manifests[1])==1 and manifests[1][0]['prompt']==manifests[0][1]['prompt']
    assert len(c.get(API+'/generator/history').json()['jobs'])==2
    with b._lock:b._jobs.clear()
    assert all(j['retry_count']==0 for j in c.get(API+'/generator/history').json()['jobs'])

def test_retry_never_infers_failed_tasks(installation):
    _,b,_,_=setup(installation)
    assert b._confirmed_failures(NS(success=False,errors=[NS(task_index=1)],failed_tasks=1),250,10,{251})==[]
    assert b._confirmed_failures(NS(success=False,errors=[NS(task_index=0)],failed_tasks=1),0,10,set())==[]
    assert b._confirmed_failures(NS(success=False,errors=[NS(task_index=2)],failed_tasks=1),250,10,set())==[252]
    assert b._confirmed_failures(NS(success=False,errors=[NS(task_index=2)],failed_tasks=2),0,10,set())==[]

def test_undo_and_responsive_cards(tab):
    tab.evaluate('removeChoice(choices[0].key)');assert tab.locator('#count').text_content()=='0';assert tab.locator('#uxUndo').is_enabled()
    tab.evaluate('undoUXChoice()');assert tab.locator('#count').text_content()=='1'
    tab.evaluate("choices[0].person='Long Performer Name '.repeat(9);renderPicks();$('selectionDetails').open=true")
    for w in (1400,700,420):
        tab.set_viewport_size({'width':w,'height':900});assert tab.locator('#picks .selected-pick').evaluate("el=>{const a=el.getBoundingClientRect(),b=el.querySelector('button').getBoundingClientRect();return b.right<=a.right+1&&b.left>=a.left}")

def test_basic_and_setup(tab):
    tab.evaluate('openUXGuide()');assert tab.locator('#uxGuideGenerate').is_enabled()
    tab.evaluate('checkUXSetup()');assert 'compatible model' in tab.locator('#uxGuideChecks').inner_text()
    tab.evaluate("closeUXModal('uxGuideModal');setUXMode(true);$('generatorModal').classList.add('open')")
    assert tab.locator('#generatorBatchPanel').is_hidden() and tab.locator('#uxSingleJob').is_visible()
    tab.evaluate('setUXMode(false)');assert tab.locator('#generatorBatchPanel').is_visible() and tab.locator('#uxSingleJob').is_hidden()

def test_preset_round_trip(tab):
    # about:blank denies browser storage and the test sandbox blocks navigation.
    # Provide the Storage interface with isolated, in-memory test data.
    tab.evaluate("""() => {const values=new Map();Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,String(v)),removeItem:k=>values.delete(k)}})}""")
    tab.evaluate("openGenerator()")
    tab.wait_for_function('!!generatorDetails&&!generatorRequestInProgress')
    tab.evaluate("$('generatorSteps').value='17';window.prompt=()=> 'Test preset';saveUXPreset()")
    assert tab.locator('#uxPreset').input_value()=='Test preset'
    tab.evaluate("$('generatorSteps').value='5';applyUXPreset()")
    assert tab.locator('#generatorSteps').input_value()=='17'

def test_preflight_blocked_in_browser(tab):
    tab.evaluate('openGenerator()');tab.wait_for_function('!!generatorDetails&&!generatorRequestInProgress')
    tab.evaluate("""() => {const orig=fetch;window.fetch=(u,o)=>String(u).includes('batch/preflight')?Promise.resolve({ok:true,json:async()=>({count:1,ready:0,blocked:1,relay_ready:true,issues:[{person:'Example',issue:'Missing RefMod'}]})}):orig(u,o)}""")
    tab.evaluate('reviewGeneratorBatch()');assert tab.locator('#generatorSubmitBatch').is_disabled();assert 'Missing RefMod' in tab.locator('#uxPreflight').text_content()

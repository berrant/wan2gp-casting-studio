"""RC12.8 local persistence and Workshop workflow regressions."""
import copy,json
from types import SimpleNamespace as NS
from PIL import Image
from test_native_plugin import installation
from test_rc123_workflows import setup
from test_rc127_moab_plus import choose
from test_rc2_jackhammer import server
from test_persona_power import tab
API='/casting-studio/api'

def test_gallery_restart_and_changed_files(installation):
    c,p,root,_=installation;s=server();b=p.queue_bridge
    b._jobs['gallery']={'id':'gallery','state':'running','_monitor_tasks':[{'person':'Synthetic actor','prompt':'Synthetic prompt','scene':1}]}
    for i in range(2):
        f=root/f'result-{i}.png';Image.new('RGB',(16,16),(i,0,0)).save(f);b._record_monitor_output('gallery',str(f),1)
    before=b.monitor_gallery();assert len(before)==2
    fresh=type(b)(b.adapter);fresh.restore_gallery(s.load_cast_gallery());s.app.state.casting_queue_bridge=fresh
    assert c.get(API+'/generator/monitor-gallery').json()['results']==before
    assert c.get(API+'/generator/monitor-output/'+before[0]['id']).status_code==200
    (root/'result-1.png').unlink()
    assert c.get(API+'/generator/monitor-output/'+before[0]['id']).status_code==404
    assert c.get(API+'/generator/monitor-gallery').json()['results']==before[1:]
    assert fresh._last_monitor_output is None

def failed_job(installation):
    c,b,session,req=setup(installation);manifests=[]
    def submit(settings,callbacks=None):
        manifests.append(settings)
        result=NS(success=False,generated_files=['synthetic-output.png'],errors=[NS(task_index=2,message='test failure',cancelled=False)],failed_tasks=1,cancelled=False) if len(manifests)==1 else NS(success=True,generated_files=['synthetic-retry.png'],errors=[],cancelled=False)
        return NS(result=lambda:result,cancel=lambda:None,webui_client_ids=[])
    session.submit_manifest=submit
    r=c.post(API+'/generator/batch/submit',json=req);assert r.status_code==200,r.text
    jid=r.json()['id'];b.process_pending_in_gradio(session)
    fresh=type(b)(b.adapter);fresh.api_session=session;fresh.dispatch_mode='gradio';fresh.history_sink=server().persist_cast_job_history
    server().app.state.casting_queue_bridge=fresh
    return c,fresh,session,jid,manifests

def test_historical_retry_preserves_exact_prompt_and_blocks_repeat(installation):
    c,b,session,jid,manifests=failed_job(installation)
    h=c.get(API+'/generator/history').json()['jobs'][0];assert h['retry_count']==1 and not any(k.startswith('_retry_') for k in h)
    tpl=c.get(API+'/prompts/image-template?model=h3_image_pruned').json();tpl['shots'][1]['action']='Changed after original submission';assert c.put(API+'/prompts/image-template?model=h3_image_pruned',json=tpl).status_code==200
    r=c.post(API+'/generator/jobs/'+jid+'/retry-failed');assert r.status_code==200,r.text;assert r.json()['task_count']==1
    assert c.post(API+'/generator/jobs/'+jid+'/retry-failed').status_code==400
    b.process_pending_in_gradio(session);assert len(manifests[1])==1 and manifests[1][0]['prompt']==manifests[0][1]['prompt']
    assert next(j for j in c.get(API+'/generator/history').json()['jobs'] if j['id']==jid)['retry_count']==0

def test_historical_retry_refuses_replaced_refmod(installation):
    c,b,session,jid,_=failed_job(installation);root=installation[2]
    (root/'refmods/minimax_h3/celebs/Ada_Test_H3.safetensors').write_bytes(b'changed model payload')
    r=c.post(API+'/generator/jobs/'+jid+'/retry-failed');assert r.status_code==400,r.text;assert not b._pending

def test_backup_restores_saved_production_sets_atomically(installation):
    c,*_=installation;s=server();choose(c);req={'production':'Example Show','family':'minimax_h3'}
    assert c.put(API+'/production-selection-set',json=req).status_code==200
    original=c.get(API+'/production-selection-set',params=req).json()['choices'];backup=c.get(API+'/settings/prompt-backup').json();assert len(backup['production_sets'])==1
    with s.connect() as db:db.execute('DELETE FROM production_selection_sets')
    assert c.post(API+'/settings/prompt-backup',json=backup).json()['production_sets']==1
    assert c.get(API+'/production-selection-set',params=req).json()['choices'][0]['key']==original[0]['key']
    bad=copy.deepcopy(backup);bad['production_sets'][0]['choices'][0]['refmod']='../outside.safetensors'
    assert c.post(API+'/settings/prompt-backup',json=bad).status_code==422
    assert c.get(API+'/production-selection-set',params=req).json()['choices'][0]['refmod']==original[0]['refmod']
    legacy=copy.deepcopy(backup);legacy.pop('production_sets');assert c.post(API+'/settings/prompt-backup',json=legacy).status_code==200
    assert c.get(API+'/production-selection-set',params=req).json()['choices']

def test_quality_ranking_and_near_duplicate_groups(installation):
    s=server();base={'person':'Ada','production':'Example','character':'Captain','quality_status':'passed','width':1000,'height':1000,'face_count':1}
    rows=[{**base,'id':'low','sharpness':20,'perceptual_hash':'0000000000000001'}, {**base,'id':'best','sharpness':300,'perceptual_hash':'0000000000000000'}, {**base,'id':'different','sharpness':100,'perceptual_hash':'ffffffffffffffff'}, {**base,'id':'other-role','character':'Doctor','sharpness':10,'perceptual_hash':'0000000000000000'}, {**base,'id':'unknown','sharpness':0,'perceptual_hash':''}]
    ranked=s.rank_reference_photos(rows);assert ranked[0]['id']=='best';by={r['id']:r for r in ranked}
    assert by['low']['duplicate_of']=='best' and by['best']['duplicate_group']=='best'
    assert all(by[k]['duplicate_of'] is None for k in ('different','other-role','unknown'))

def test_workshop_preselects_unique_ranked_photos(tab):
    tab.evaluate('''() => {workshopSources=[{person:'Example',production:'Example Show',character:'Captain'}];$('workshopCollection').innerHTML='<option value="0">Example</option>';const old=fetch;window.fetch=(u,o)=>String(u).startsWith('api/workshop/photos')?Promise.resolve({ok:true,json:async()=>({photos:[{id:'best',quality_rank:1,quality:'passed',duplicate_group:'best',width:800,height:800,url:'best.png'},{id:'similar',quality_rank:2,quality:'passed',duplicate_of:'best',width:800,height:800,url:'similar.png'},{id:'unique',quality_rank:3,quality:'passed',width:800,height:800,url:'unique.png'}]})}):old(u,o);loadWorkshopPhotos()}''')
    tab.wait_for_function("$('workshopPhotos').querySelectorAll('.workshopPhotoCheck').length===3")
    assert tab.locator('#workshopPhotos .workshopPhotoCheck:checked').evaluate_all('es=>es.map(e=>e.value)')==['best','unique']
    assert tab.locator('#workshopTestPortrait').is_checked() is False

def test_optional_workshop_test_portrait_exact_refmod(installation,monkeypatch):
    from test_dev510 import mod
    c,p,root,_=installation;s=server();b=p.queue_bridge;source=root/'source.png';Image.new('RGB',(40,40)).save(source)
    monkeypatch.setattr(s,'workshop_photo_rows',lambda *a:[{'id':'abc','person':'Ada Test','production':'Example Show','character':'Captain','path':source,'width':800,'height':800,'quality':'passed'}])
    monkeypatch.setattr(p.adapter,'discover',lambda:{'fork_revision':58,'installed':True})
    monkeypatch.setattr(b,'models',lambda board:[{'model_type':'flux-test','name':'FLUX','ready':True}] if board=='flux2_klein9' else [])
    b.dispatch_mode='gradio';sent=[]
    class Session:
        def list_model_defs(self):return [{'model_type':'flux-test','architecture':'flux2_klein9','custom_settings':[{'id':'flux_refmod_state'}]}]
        def merge_settings_with_defaults(self,data):return data
        def submit_task(self,settings,callbacks):
            sent.append(settings);payload=json.loads(settings['custom_settings']['flux_refmod_state'])
            if '__flux_refmod_extract__' in payload:
                mod(root/'refmods/flux2/celebs/Ada_Test_New_FLUX.safetensors',{'name':'celebs/Ada_Test_New_FLUX'},'klein9_refmod_meta');res=NS(errors=[])
            else:
                f=root/'test-portrait.png';Image.new('RGB',(32,32)).save(f);res=NS(success=True,generated_files=[str(f)],errors=[],cancelled=False)
            return NS(result=lambda:res,cancel=lambda:None,webui_client_ids=[])
    session=Session();b.api_session=session
    req={'person':'Ada Test','production':'Example Show','character':'Captain','image_ids':['abc'],'name':'Ada_Test_New_FLUX','model_type':'flux-test','family':'flux2','test_portrait':True}
    r=c.post(API+'/workshop/create',json=req);assert r.status_code==200,r.text;jid=r.json()['job_id'];b.process_pending_in_gradio(session)
    status=c.get(API+'/workshop/jobs/'+jid).json();assert status['state']=='completed' and status.get('test_portrait_state')=='completed',status
    assert len(sent)==2 and 'Ada_Test_New_FLUX' in sent[1]['custom_settings']['flux_refmod_state']
    assert c.get(API+'/choices').json()==[]
    assert c.get(API+'/generator/monitor-gallery').json()['results'][0]['task_details']['character']=='Captain'

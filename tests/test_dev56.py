"""dev5.6: batch manifest queue and source-specific character identity."""
import json
from types import SimpleNamespace
from test_native_plugin import installation, _mock_fork, FakeWanSession, FakeTaskHandle

API='/casting-studio/api'

class ManifestSession(FakeWanSession):
    def __init__(self):
        super().__init__();self.manifests=[]
    def submit_manifest(self,settings_list,callbacks=None):
        self.manifests.append(settings_list)
        return FakeTaskHandle(SimpleNamespace(success=True,generated_files=['/tmp/generated.mp4'],errors=[],cancelled=False))

def _init_128(installation):
    client,plugin,root,_=installation
    _mock_fork(root)
    from importlib import import_module
    srv=import_module('cb_under_test.app.server')
    with srv.connect() as db:
        for name,year in [('Ahsoka',2023),('Star Wars: A New Hope',1977)]:
            db.execute('INSERT INTO productions VALUES (?,?,?,?)',(srv.token(name),name,year,'other'))
        for i in range(128):
            production='Ahsoka' if i%2==0 else 'Star Wars: A New Hope'
            character=('Ahsoka Tano' if i==0 else f'Test Character {i:03d}')
            item={'person':'Ada Test','character':character,'production':production,
                  'refmod':'Ada_Test_H3.safetensors','personal_id':''}
            item['key']=srv.canonical_role_key(item['person'],item['character'],production)
            db.execute('INSERT INTO choices VALUES (?,?)',(item['key'],json.dumps(item)))
    srv.catalog_cache['until']=0
    session=ManifestSession()
    plugin.queue_bridge.api_session=session
    plugin.queue_bridge.dispatch_mode='gradio'
    task={'choice_key':'unused','model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint',
          'scene':1,'steps':8,'resolution':'832x480','loras':[]}
    return client,plugin,session,{'task':task,'scope':'all','scene_mode':'first'}

def test_all_128_have_individual_prompts_and_native_manifest(installation):
    client,plugin,session,body=_init_128(installation)
    preview=client.post(API+'/generator/batch/preview',json=body)
    assert preview.status_code==200,preview.text
    data=preview.json()
    assert data['count']==128 and data['selections']==128
    assert len(set(x['choice_key'] for x in data['tasks']))==128
    assert len(set(x['prompt'] for x in data['tasks']))==128
    assert 'Ahsoka (2023)' in data['tasks'][0]['prompt'] or 'Star Wars: A New Hope (1977)' in data['tasks'][0]['prompt']
    submit=client.post(API+'/generator/batch/submit',json=body)
    assert submit.status_code==200,submit.text
    bid=submit.json()['id']
    assert submit.json()['task_count']==128
    assert len(plugin.queue_bridge._pending)==1
    assert not session.manifests
    plugin.queue_bridge.process_pending_in_gradio(session)
    status=client.get(API+'/generator/jobs/'+bid).json()
    assert status['state']=='completed',status
    assert len(session.manifests)==1 and len(session.manifests[0])==128
    assert len(set(x['prompt'] for x in session.manifests[0]))==128
    assert all(x['num_inference_steps']==8 for x in session.manifests[0])
    assert all('h3_refmod_state' in x['custom_settings'] for x in session.manifests[0])

def test_scoped_batch_and_all_segments(installation):
    client,plugin,session,body=_init_128(installation)
    body['scope']='production:ahsoka'
    body['scene_mode']='all'
    r=client.post(API+'/generator/batch/preview',json=body)
    assert r.status_code==200,r.text
    d=r.json()
    assert d['selections']==64 and d['count']==128
    assert all(x['production']=='Ahsoka (2023)' for x in d['tasks'])
    assert {x['scene'] for x in d['tasks']}=={1,2}
    # Independent images now each have their own prompt, no phantom image chaining.
    image_batch={**body,'task':{**body['task'],'model':'h3_image','model_type':'h3_image'}}
    r=client.post(API+'/generator/batch/preview',json=image_batch)
    assert r.status_code==200,r.text
    assert r.json()['count']==320
    assert {x['scene'] for x in r.json()['tasks']}=={1,2,3,4,5}
    assert all('previous still' not in x['prompt'] for x in r.json()['tasks'])

def test_batch_is_atomic_on_missing_selection(installation):
    client,plugin,session,body=_init_128(installation)
    from importlib import import_module
    srv=import_module('cb_under_test.app.server')
    with srv.connect() as db:
        item=json.loads(db.execute('SELECT payload FROM choices LIMIT 1').fetchone()[0]);
        item['refmod']='missing.safetensors'
        db.execute('UPDATE choices SET payload=? WHERE key=?',(json.dumps(item),item['key']))
    r=client.post(API+'/generator/batch/submit',json=body)
    assert r.status_code==400,r.text
    assert len(plugin.queue_bridge._pending)==0
    assert not session.manifests

def test_character_traits_and_year_appear_in_all_scenes(installation):
    client,plugin,root,_=installation
    from importlib import import_module
    srv=import_module('cb_under_test.app.server')
    assert client.post(API+'/productions',json={'name':'Ahsoka','kind':'series','year':2023}).status_code==200
    with srv.connect() as db:
        db.execute('INSERT INTO character_identity_suggestions VALUES (?,?,?,?)',(srv.character_identity_key('Ahsoka Tano','Ahsoka'),'orange facial and body skin','Synthetic test fixture',0))
    item={'person':'Rosario Dawson','character':'Ahsoka Tano','production':'Ahsoka','refmod':'Rosario_Dawson_H3.safetensors'}
    p=srv.prompt_for_selection(item,{**srv.SAMPLE_TEMPLATE,'video_count':4})
    assert p.count('orange facial and body skin')==8  # definitions and retention in 4 clips
    assert p.count('Ahsoka (2023)')>=4
    assert 'Rosario Dawson - Ahsoka Tano - Ahsoka (2023)' in p
    assert '<Subject 2>' not in p
    r=client.get(API+'/characters/identity',params={'character':'Ahsoka Tano','production':'Ahsoka'})
    assert r.json()['source']=='researched'
    r=client.put(API+'/characters/identity',json={'character':'Ahsoka Tano','production':'Ahsoka','traits':'Permanent bright orange face and white eyebrow chevrons.'})
    assert r.status_code==200,r.text
    p2=srv.prompt_for_selection(item,srv.SAMPLE_TEMPLATE)
    assert 'Permanent bright orange face' in p2 and 'orange facial and body skin' not in p2
    assert client.put(API+'/characters/identity',json={'character':'Ahsoka Tano','production':'Ahsoka','traits':''}).status_code==200
    assert client.get(API+'/characters/identity',params={'character':'Ahsoka Tano','production':'Ahsoka'}).json()['source']=='researched'
    # Unknown roles are not assigned fabricated visual traits.
    assert client.get(API+'/characters/identity',params={'character':'Unknown Character','production':'Imaginary Show'}).json()['source']=='none'
    bad=client.put(API+'/characters/identity',json={'character':'Ahsoka Tano','production':'Ahsoka','traits':'wardrobe_description: override'})
    assert bad.status_code==400

def test_privacy_consent_rechecked_after_batch_staging(installation):
    client,plugin,session,body=_init_128(installation)
    # Stage, then delete a selection before native callback: all 128 must fail,
    # not silently admit the remaining 127 to the GPU queue.
    r=client.post(API+'/generator/batch/submit',json=body)
    assert r.status_code==200,r.text
    from importlib import import_module
    srv=import_module('cb_under_test.app.server')
    with srv.connect() as db:
        key=db.execute('SELECT key FROM choices LIMIT 1').fetchone()[0]
        db.execute('DELETE FROM choices WHERE key=?',(key,))
    plugin.queue_bridge.process_pending_in_gradio(session)
    st=client.get(API+'/generator/jobs/'+r.json()['id']).json()
    assert st['state']=='failed' and not session.manifests

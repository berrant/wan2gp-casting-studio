"""v5.12: image-set templates must drive every actual WanGP task."""
import json
from importlib import import_module
from test_native_plugin import installation, _mock_fork, FakeWanSession, FakeTaskHandle, _create_public_selection
from test_dev56 import ManifestSession

API='/casting-studio/api'

def _image_session():
    session=ManifestSession()
    session.defs.append({'model_type':'h3_image_pruned_checkpoint','architecture':'minimax_h3_image_pruned',
                         'name':'H3 Image Pruned 20B','custom_settings':[{'id':'h3_refmod_state'}]})
    return session

def _set_image_template(client,model='h3_image_pruned',count=3):
    old=client.get(API+'/prompts/image-template?model='+model).json()
    shots=[{'wardrobe':f'Wardrobe UNIQUE {i}', 'action':f'Action UNIQUE {i}',
            'framing':f'Framing UNIQUE {i}', 'expression':f'Expression UNIQUE {i}',
            'setting':f'Setting UNIQUE {i}'} for i in range(1,count+1)]
    payload={'image_count':count,'shots':shots,'visual_style':'Bright editorial lighting'}
    saved=client.put(API+'/prompts/image-template?model='+model,json=payload)
    assert saved.status_code==200,saved.text
    return old,shots

def test_legacy_five_scene_templates_migrate_without_erasing_edits(installation):
    client,plugin,root,_=installation
    srv=import_module('cb_under_test.app.server')
    with srv.connect() as db:
        db.execute('INSERT OR REPLACE INTO prompt_settings VALUES (?,?)',
                   ('image_flux2_dev',json.dumps({'scene3':'A CUSTOM saved pose','original_wardrobe':'Original clothing',
                                                  'transformed_wardrobe':'Updated clothing'})))
    got=client.get(API+'/prompts/image-template?model=flux2_dev').json()
    assert got['image_count']==5 and len(got['shots'])==5
    assert got['shots'][0]['wardrobe']=='Original clothing'
    assert got['shots'][2]['wardrobe']=='Updated clothing'
    assert got['shots'][2]['action']=='A CUSTOM saved pose'
    assert got['shots'][4]['action']

def test_saved_three_image_prompts_are_distinct_and_end_to_end(installation):
    client,plugin,root,_=installation
    _mock_fork(root)
    session=_image_session();plugin.queue_bridge.api_session=session;plugin.queue_bridge.dispatch_mode='gradio'
    key=_create_public_selection(client)
    _,shots=_set_image_template(client)
    task={'choice_key':key,'model':'h3_image_pruned','model_type':'h3_image_pruned_checkpoint',
          'steps':8,'scene':1,'resolution':'832x480'}
    body={'task':task,'scope':'selection:'+key,'scene_mode':'all'}
    review=client.post(API+'/generator/batch/preview',json=body)
    assert review.status_code==200,review.text
    d=review.json();assert d['count']==3 and d['selections']==1
    assert [x['scene'] for x in d['tasks']]==[1,2,3]
    for i,x in enumerate(d['tasks'],1):
        assert 'Wardrobe UNIQUE '+str(i) in x['prompt']
        assert 'Action UNIQUE '+str(i) in x['prompt']
        assert 'Framing UNIQUE '+str(i) in x['prompt']
        assert 'Setting UNIQUE '+str(i) in x['prompt']
        assert 'previous still' not in x['prompt'].lower()
    queue=client.post(API+'/generator/batch/submit',json=body)
    assert queue.status_code==200,queue.text
    assert queue.json()['task_count']==3 and not session.manifests
    plugin.queue_bridge.process_pending_in_gradio(session)
    assert len(session.manifests)==1 and len(session.manifests[0])==3
    for i,settings in enumerate(session.manifests[0],1):
        assert f'Action UNIQUE {i}' in settings['prompt']
        assert f'Wardrobe UNIQUE {i}' in settings['prompt']
        assert 'h3_refmod_state' in settings['custom_settings']
        assert settings['num_inference_steps']==8

def test_multi_role_image_sets_queue_exact_math_and_source_prompts(installation):
    client,plugin,root,_=installation
    _mock_fork(root)
    session=_image_session();plugin.queue_bridge.api_session=session;plugin.queue_bridge.dispatch_mode='gradio'
    first=_create_public_selection(client)
    srv=import_module('cb_under_test.app.server')
    a={'key':'','person':'Ada Test','character':'Character A','production':'Science Show','refmod':'Ada_Test_H3.safetensors'}
    b={'key':'','person':'Ada Test','character':'Character B','production':'Science Show','refmod':'Ada_Test_H3.safetensors'}
    assert client.put(API+'/choices',json=a).status_code==200
    assert client.put(API+'/choices',json=b).status_code==200
    _set_image_template(client,count=4)
    req={'task':{'choice_key':first,'model':'h3_image_pruned','model_type':'h3_image_pruned_checkpoint'},
         'scope':'production:scienceshow','scene_mode':'all'}
    review=client.post(API+'/generator/batch/preview',json=req)
    assert review.status_code==200,review.text
    d=review.json();assert d['count']==8 and d['selections']==2
    assert len(set(x['prompt'] for x in d['tasks']))==8
    assert set(x['scene'] for x in d['tasks'])=={1,2,3,4}
    result=client.post(API+'/generator/batch/submit',json=req)
    assert result.status_code==200,result.text
    plugin.queue_bridge.process_pending_in_gradio(session)
    assert len(session.manifests[0])==8

def test_invalid_image_set_update_and_out_of_range_rejected(installation):
    client,plugin,root,_=installation
    _set_image_template(client,count=3)
    bad=client.put(API+'/prompts/image-template?model=h3_image_pruned',json={'image_count':4,'shots':[{'action':'Only one'}]})
    assert bad.status_code==422
    assert client.get(API+'/prompts/image-template?model=h3_image_pruned').json()['image_count']==3
    too_many=client.put(API+'/prompts/image-template?model=h3_image_pruned',json={'image_count':11})
    assert too_many.status_code==422
    assert client.get(API+'/prompts/image-template?model=h3_image_pruned').json()['image_count']==3

def test_128_roles_times_five_images_automatically_chunked(installation):
    # No arbitrary 500-task ceiling for a 128-role photo set (128*5=640).
    from test_dev56 import _init_128
    client,plugin,session,body=_init_128(installation)
    session.defs.append({'model_type':'h3_image_pruned_checkpoint','architecture':'minimax_h3_image_pruned',
                         'name':'H3 Image Pruned 20B','custom_settings':[{'id':'h3_refmod_state'}]})
    body['task']['model']='h3_image_pruned';body['task']['model_type']='h3_image_pruned_checkpoint'
    body['scene_mode']='all'
    r=client.post(API+'/generator/batch/preview',json=body)
    assert r.status_code==200,r.text
    assert r.json()['count']==640
    assert {x['scene'] for x in r.json()['tasks']}=={1,2,3,4,5}
    queued=client.post(API+'/generator/batch/submit',json=body)
    assert queued.status_code==200,queued.text
    plugin.queue_bridge.process_pending_in_gradio(session)
    assert [len(x) for x in session.manifests]==[250,250,140]
    assert sum(map(len,session.manifests))==640
    status=client.get(API+'/generator/jobs/'+queued.json()['id']).json()
    assert status['state']=='completed' and status['total_tasks']==640

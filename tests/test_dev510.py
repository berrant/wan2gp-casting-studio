"""v6.9.0-dev5.10: H3 picture stack recognition, FLUX creation and Settings layout."""
from pathlib import Path
from types import SimpleNamespace
import importlib,json
from test_native_plugin import installation

API='/casting-studio/api'


def mod(path,metadata,key):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps({'__metadata__':{key:json.dumps(metadata)},
                    'samples':{'dtype':'F32','shape':[1,128,1,1], 'data_offsets':[0,512]}}).encode()
    path.write_bytes(len(raw).to_bytes(8,'little')+raw+bytes(512))


def test_picture_stack_detection_and_temporal_video_rejection(installation,monkeypatch):
    from cb_under_test.conversion_bridge import is_h3_picture_refmod as ok
    assert ok({'kind':'image','mode':'encode'})
    assert ok({'kind':'video','source_shape':'1x38x46 +1x38x46','tags':['23 img, 0 vid']})
    assert ok({'kind':'video','source':'stack','source_shape':'1x38x46 +1x38x46'})
    assert not ok({'kind':'video','tags':['0 img, 1 vid']})
    assert not ok({'kind':'video','source':'stack','tags':['23 img, 1 vid']})
    assert not ok({'kind':'audio'})
    assert not ok({'kind':'video','tags':['23 img, 0 vid'],'has_audio':True})


def test_flux_creation_uses_fork_payload_and_preserves_files(installation,monkeypatch):
    client,plugin,root,_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    from cb_under_test import workshop_bridge
    source=root/'user_data/reference_photos/abc123.jpg'
    source.parent.mkdir(parents=True,exist_ok=True);source.write_bytes(b'fake image for a contract test')
    def mock_photo_rows(person=None,production=None,character=None):
        return [{'id':'abc123','person':'Ada Test','production':'Sample Show','character':'Lead',
                 'path':source,'width':800,'height':900,'quality':'passed'}] if (
                     person in (None,'Ada Test') and production in (None,'Sample Show') and character in (None,'Lead')) else []
    monkeypatch.setattr(srv,'workshop_photo_rows',mock_photo_rows)
    monkeypatch.setattr(plugin.adapter,'discover',lambda:{'fork_revision':58,'installed':True})
    monkeypatch.setattr(plugin.queue_bridge,'models',lambda board:[{'model_type':'flux-klein-test','name':'FLUX Klein','ready':True}] if board=='flux2_klein9' else [])
    plugin.queue_bridge.dispatch_mode='gradio'
    class Session:
        def merge_settings_with_defaults(self,data):return data
        def submit_task(self,settings,callbacks):
            assert settings['model_type']=='flux-klein-test'
            spec=json.loads(settings['custom_settings']['flux_refmod_state'])['__flux_refmod_extract__']
            assert spec['name']=='celebs/Ada_Test_FLUX'
            assert spec['images']==[str(source)]
            assert spec['layout']=='separate' and spec['budget']==4096
            mod(root/'refmods/flux2/celebs/Ada_Test_FLUX.safetensors',{'name':spec['name']},'klein9_refmod_meta')
            return SimpleNamespace(result=lambda:SimpleNamespace(errors=[]))
    plugin.queue_bridge.api_session=Session()
    assert client.get(API+'/workshop/models?family=flux2').status_code==200
    assert client.get(API+'/workshop/models?family=other').status_code==400
    request={'person':'Ada Test','production':'Sample Show','image_ids':['abc123'],
             'name':'Ada_Test_FLUX','model_type':'flux-klein-test', 'family':'flux2',
             'layout':'separate','budget':4096}
    staged=client.post(API+'/workshop/create',json=request)
    assert staged.status_code==200,staged.text
    plugin.queue_bridge.process_pending_in_gradio(plugin.queue_bridge.api_session)
    job=client.get(API+'/workshop/jobs/'+staged.json()['job_id']).json()
    assert job['state']=='completed',job
    assert (root/'refmods/flux2/celebs/Ada_Test_FLUX.safetensors').exists()
    assert not (root/'refmods/minimax_h3/celebs/Ada_Test_FLUX.safetensors').exists()
    assert client.post(API+'/workshop/create',json=request).status_code in (400,409)


def test_maintenance_controls_in_settings_not_performers(installation):
    client,_,_,_=installation
    html=client.get('/casting-studio/').text
    assert 'id="backgroundTools"' in html
    main=html.split('<section id="browseSection"')[1].split('<section id="productionSection"')[0]
    assert 'id="prefetchStatus"' not in main
    settings=html.split('<div id="settingsModal"')[1].split('<div id="aboutModal"')[0]
    for token in ('id="prefetchStatus"','id="creditsStatus"','id="enrichStatus"'):
        assert token in settings
    assert 'id="workshopFamily"' in html


def test_video_game_character_classification_does_not_run_human_research(installation):
    client,plugin,root,_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    r=client.put(API+'/profiles/categories',json={'name':'Ada Test','categories':['Video game character']})
    assert r.status_code==200,r.text
    assert srv.is_video_game_character('Ada Test')
    assert client.get(API+'/profiles/categories').json()['Ada Test']==['Video game character']
    # A fictional game character must not be sent to performer filmography services.
    r=client.post(API+'/credits/refresh',json={'person':'Ada Test'})
    assert r.status_code==404,r.text
    try:
        srv.sync_one_public_person('Ada Test')
        assert False,'Human credits should reject fictional game characters'
    except ValueError as e:
        assert 'Video-game characters' in str(e)
    item={'person':'Ada Test','character':'','production':'','refmod':'Ada_Test_H3.safetensors'}
    prompt=srv.prompt_for_selection(item,srv.SAMPLE_TEMPLATE)
    assert 'fictional video-game character' in str(prompt)
    assert 'as themselves' not in str(prompt)
    text=client.get('/casting-studio/').text
    assert "'Video game character'" in text
    assert 'Find character art' in text
    assert 'Select character' in text

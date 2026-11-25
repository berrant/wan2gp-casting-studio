"""Native Gradio auto-conversion: no actual VAE/GPU in these contract tests."""
import json
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
from test_native_plugin import installation

API='/casting-studio/api'


def write_mod(path, key, metadata):
    path.parent.mkdir(parents=True,exist_ok=True)
    header={'__metadata__':{key:json.dumps(metadata)}}
    raw=json.dumps(header).encode()
    path.write_bytes(len(raw).to_bytes(8,'little')+raw+b'1234567890123456')


def _setup(installation, monkeypatch, *, kind='image', extract=True):
    client,plugin,root,_=installation
    import importlib
    server=importlib.import_module('cb_under_test.app.server')
    bridge=plugin.queue_bridge
    source=root/'refmods/minimax_h3/celebs/Ada_Test_H3.safetensors'
    write_mod(source,'refmod_meta',{'kind':kind,'mode':'encode','concept_type':'identity','description':'Test'})
    cast={'key':'','person':'Ada Test','production':'Sample Show',
          'character':'Friend','refmod':'Ada_Test_H3.safetensors'}
    assert client.put(API+'/choices',json=cast).status_code==200
    monkeypatch.setattr(bridge,'models',lambda m:[{'model_type':'h3-pruned','ready':True}] if m=='h3_video' else [{'model_type':'flux3-test','ready':True}])
    monkeypatch.setattr(bridge.adapter,'discover',lambda:{'fork_revision':58})
    bridge.dispatch_mode='gradio'
    class FakeSession:
        def merge_settings_with_defaults(self,settings):
            return dict(settings)
        def submit_task(self,settings,callbacks):
            nonlocal extract
            if settings['model_type']=='h3-pruned':
                payload=json.loads(settings['custom_settings']['h3_refmod_state'])['__h3refmod_extract__']
                assert payload['op']=='decompile' and payload['name']=='celebs/Ada_Test_H3'
                folder=root/'refmods/decompiled'/payload['name']
                folder.mkdir(parents=True,exist_ok=True)
                Image.new('RGB',(128,128)).save(folder/'frame.png')
            elif settings['model_type']=='flux3-test':
                payload=json.loads(settings['custom_settings']['flux_refmod_state'])['__flux_refmod_extract__']
                assert payload['converted_from']=='celebs/Ada_Test_H3'
                assert 'frame.png' in payload['images'][0]
                if extract:
                    write_mod(root/'refmods/flux2'/(payload['name']+'.safetensors'),
                              'klein9_refmod_meta',{'converted_from':payload['converted_from']})
            else:raise AssertionError(settings['model_type'])
            return SimpleNamespace(result=lambda:SimpleNamespace(success=False,errors=[],generated_files=[]))
    bridge.api_session=FakeSession()
    return client,plugin,root,server


def test_automatic_conversion_links_exact_output(installation,monkeypatch):
    client,plugin,root,server=_setup(installation,monkeypatch)
    res=client.post(API+'/choices/conversion/prepare',json={'target_model':'flux3_klein'})
    assert res.status_code==200,res.text
    plan=res.json();assert plan['count']==1 and plan['id']
    # An existing H3 model must not be deleted by staging a GPU conversion.
    assert client.get(API+'/choices').json()[0]['refmod']=='Ada_Test_H3.safetensors'
    plugin.queue_bridge.process_pending_in_gradio(plugin.queue_bridge.api_session)
    job=client.get(API+'/generator/jobs/'+plan['id']).json()
    assert job['state']=='completed',job
    assert job['converted'][0]['source']=='Ada_Test_H3.safetensors'
    done=client.post(API+'/choices/conversion/apply',json={'job_id':plan['id']})
    assert done.status_code==200,done.text
    assert done.json()['remaining']==1 and len(done.json()['converted'])==1
    assert done.json()['choices'][0]['refmod']=='flux2/celebs/Ada_Test_H3.safetensors'
    assert client.post(API+'/choices/conversion/apply',json={'job_id':plan['id']}).status_code==409
    assert (root/'refmods/minimax_h3/celebs/Ada_Test_H3.safetensors').exists()
    # Switching back to H3 can still use the original file.
    back=client.post(API+'/choices/reconcile',json={'family':'minimax_h3'})
    assert back.status_code==200 and back.json()['choices'][0]['refmod']=='Ada_Test_H3.safetensors'


def test_failed_conversion_does_not_fake_a_refmod(installation,monkeypatch):
    client,plugin,root,server=_setup(installation,monkeypatch,extract=False)
    plan=client.post(API+'/choices/conversion/prepare',json={'target_model':'flux3_klein'}).json()
    plugin.queue_bridge.process_pending_in_gradio(plugin.queue_bridge.api_session)
    job=client.get(API+'/generator/jobs/'+plan['id']).json()
    assert job['state']=='failed' and job['failures']
    assert job['converted']==[]
    assert client.get(API+'/choices').json()[0]['refmod']=='Ada_Test_H3.safetensors'
    done=client.post(API+'/choices/conversion/apply',json={'job_id':plan['id']})
    assert done.status_code==409
    assert client.get(API+'/choices').json()[0]['refmod']=='Ada_Test_H3.safetensors'
    assert not list((root/'refmods/flux2/celebs').glob('*.safetensors'))


def test_video_kind_is_not_auto_converted(installation,monkeypatch):
    client,plugin,root,server=_setup(installation,monkeypatch,kind='video')
    plan=client.post(API+'/choices/conversion/prepare',json={'target_model':'flux3_klein'})
    assert plan.status_code==200,plan.text
    assert plan.json()['count']==0 and 'still-image' in plan.json()['not_convertible'][0]['reason']


def test_many_roles_reuse_one_converted_refmod(installation,monkeypatch):
    client,plugin,root,server=_setup(installation,monkeypatch)
    cast={'key':'','person':'Ada Test','production':'Another Show','character':'Lead',
          'refmod':'Ada_Test_H3.safetensors'}
    assert client.put(API+'/choices',json=cast).status_code==200
    session=plugin.queue_bridge.api_session
    original=session.submit_task
    counter={'n':0}
    def counted(settings,callbacks):
        counter['n']+=1
        return original(settings,callbacks)
    session.submit_task=counted
    plan=client.post(API+'/choices/conversion/prepare',json={'target_model':'flux3_klein'}).json()
    assert plan['count']==2
    plugin.queue_bridge.process_pending_in_gradio(session)
    assert counter['n']==2 # one H3 decode and one FLUX encode, not four GPU tasks
    done=client.post(API+'/choices/conversion/apply',json={'job_id':plan['id']})
    assert done.status_code==200
    assert done.json()['remaining']==2 and len(done.json()['converted'])==2
    mods={c['refmod'] for c in client.get(API+'/choices').json()}
    assert len(mods)==1


def test_private_auto_conversion_preserves_privacy_and_consent(installation,monkeypatch):
    client,plugin,root,server=_setup(installation,monkeypatch)
    private_h3=root/'refmods/minimax_h3/personal/Private_Test_H3.safetensors'
    write_mod(private_h3,'refmod_meta',{'kind':'image','mode':'encode'})
    profile={'name':'Private Test','relationship':'Friend','notes':'NEVER EXPOSE NOTES',
             'consent':True,'h3_refmod':'personal/Private_Test_H3.safetensors'}
    result=client.post(API+'/personal',json=profile)
    assert result.status_code==200,result.text
    pid=client.get(API+'/personal').json()[0]['id']
    cast={'key':'','person':'Private Test','production':'','character':'',
          'refmod':'personal/Private_Test_H3.safetensors','personal_id':pid}
    assert client.put(API+'/choices',json=cast).status_code==200
    session=plugin.queue_bridge.api_session
    class PrivateSession:
        def merge_settings_with_defaults(self,data):return dict(data)
        def submit_task(self,settings,callbacks):
            if settings['model_type']=='h3-pruned':
                item=json.loads(settings['custom_settings']['h3_refmod_state'])['__h3refmod_extract__']
                assert item['name']=='personal/Private_Test_H3'
                folder=root/'refmods/decompiled'/item['name'];folder.mkdir(parents=True,exist_ok=True)
                Image.new('RGB',(64,64)).save(folder/'pic.png')
            else:
                item=json.loads(settings['custom_settings']['flux_refmod_state'])['__flux_refmod_extract__']
                assert item['name'].startswith('personal/')
                write_mod(root/'refmods/flux2'/(item['name']+'.safetensors'),
                    'klein9_refmod_meta',{'converted_from':item['converted_from']})
            return SimpleNamespace(result=lambda:SimpleNamespace(success=False,errors=[],generated_files=[]))
    plugin.queue_bridge.api_session=PrivateSession()
    plan=client.post(API+'/choices/conversion/prepare',json={'target_model':'flux3_klein'}).json()
    assert plan['count']==2 # Public Ada Test and private entry; both kept distinct.
    plugin.queue_bridge.process_pending_in_gradio(plugin.queue_bridge.api_session)
    done=client.post(API+'/choices/conversion/apply',json={'job_id':plan['id']})
    # The extra Ada Test cannot be decoded by the private-only test session: its
    # failure must not block the private person's separate conversion.
    assert done.status_code==409,done.text
    choices=client.get(API+'/choices').json()
    private_choice=next(c for c in choices if c.get('personal_id')==pid)
    assert private_choice['refmod']=='personal/Private_Test_H3.safetensors'
    assert not list((root/'refmods/flux2/celebs').glob('*Private*'))
    assert 'NEVER EXPOSE NOTES' not in str(done.json())


def test_missing_encoder_does_not_prevent_family_switch(installation,monkeypatch):
    client,plugin,root,server=_setup(installation,monkeypatch)
    monkeypatch.setattr(plugin.queue_bridge,'models',
        lambda family:[{'model_type':'h3-pruned','ready':True}] if family=='h3_video' else [])
    plan=client.post(API+'/choices/conversion/prepare',json={'target_model':'flux3_klein'})
    assert plan.status_code==200,plan.text
    assert not plan.json()['id'] and plan.json()['count']==0
    assert client.get(API+'/choices').json()[0]['refmod']=='Ada_Test_H3.safetensors'


def test_auto_conversion_unavailable_in_standalone_docker(installation):
    client,plugin,root,module=installation
    import importlib
    server=importlib.import_module('cb_under_test.app.server')
    original=getattr(server.app.state,'casting_queue_bridge',None)
    server.app.state.casting_queue_bridge=None
    try:
        r=client.post(API+'/choices/conversion/prepare',json={'target_model':'flux3_klein'})
        assert r.status_code==503,r.text
        r=client.post(API+'/choices/conversion/apply',json={'job_id':'missing'})
        assert r.status_code==503,r.text
    finally:
        server.app.state.casting_queue_bridge=original

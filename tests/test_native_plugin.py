"""Local smoke/regression tests for v6.9; no WanGP/GPU required."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PACKAGE=Path(__file__).resolve().parents[1]


@pytest.fixture()
def installation(tmp_path,monkeypatch):
    # Test private and public installation paths, not the user's actual files.
    h3=tmp_path/'refmods'/'minimax_h3'/'celebs';h3.mkdir(parents=True)
    private=tmp_path/'refmods'/'minimax_h3'/'personal';private.mkdir()
    flux=tmp_path/'refmods'/'flux2';(flux/'celebs').mkdir(parents=True)
    (flux/'personal').mkdir()
    (h3/'Ada_Test_H3.safetensors').write_bytes(b'not a real model')
    (private/'Private_Test_H3.safetensors').write_bytes(b'not a real model')
    monkeypatch.setenv('CASTING_STUDIO_REFMOD_ROOT',str(tmp_path/'refmods'))
    monkeypatch.setenv('CASTING_STUDIO_DATA_DIR',str(tmp_path/'user_data'))

    fake_shared=types.ModuleType('shared')
    fake_utils=types.ModuleType('shared.utils')
    fake_plugins=types.ModuleType('shared.utils.plugins')
    class WAN2GPPlugin:
        def __init__(self):self.tabs=[];self.web_apps=[]
        def request_global(self,name):pass
        def request_component(self,name):pass
        def add_tab(self,**kwargs):self.tabs.append(kwargs)
        def register_web_app(self,path,factory):self.web_apps.append((path,factory))
    fake_plugins.WAN2GPPlugin=WAN2GPPlugin
    monkeypatch.setitem(sys.modules,'shared',fake_shared)
    monkeypatch.setitem(sys.modules,'shared.utils',fake_utils)
    monkeypatch.setitem(sys.modules,'shared.utils.plugins',fake_plugins)
    prefix='cb_under_test'
    for module in list(sys.modules):
        if module==prefix or module.startswith(prefix+'.'):
            monkeypatch.delitem(sys.modules,module,raising=False)
    spec=importlib.util.spec_from_file_location(prefix, PACKAGE/'__init__.py',submodule_search_locations=[str(PACKAGE)])
    module=importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules,prefix,module)
    spec.loader.exec_module(module)
    from importlib import import_module
    plugin_cls=import_module(prefix+'.plugin').CastingStudioPlugin
    plugin=plugin_cls()
    # The real root is deterministic from plugin's install location;
    # override it to simulate a fresh user-installed WAN2GP root.
    plugin.wangp_root=tmp_path
    plugin.adapter=import_module(prefix+'.compat_adapter').RefmodForkAdapter(tmp_path)
    plugin.queue_bridge.adapter=plugin.adapter
    plugin.setup_ui()
    assert plugin.tabs[0]['tab_id']=='casting_studio'
    assert plugin.web_apps[0][0]=='/casting-studio'
    web_app=plugin.create_web_app()
    host=FastAPI()
    host.mount('/casting-studio',web_app)
    yield TestClient(host),plugin,tmp_path,import_module(prefix+'.compat_adapter')


def test_native_mount_routes_and_assets(installation):
    client, plugin, root, _=installation
    html=client.get('/casting-studio/')
    assert html.status_code==200
    assert 'v'+plugin.version in html.text
    assert "fetch('api/" in html.text
    assert 'src="api/ui/icons/personal"' in html.text
    assert client.get('/casting-studio/api/ui/icons/personal').status_code==200
    assert client.get('/casting-studio/api/catalog').status_code==200
    assert client.get('/casting-studio/api/models/options').status_code==200
    assert client.get('/casting-studio/api/prompts/export?model=h3_video').status_code==200
    status=client.get('/casting-studio/api/integration/status').json()
    assert status['mode']=='wangp-native'
    assert status['refmod_fork']['installed'] is False
    assert status['queue_integration']['ready'] is False
    assert (root/'user_data'/'casting.sqlite3').exists()


def test_public_private_separation_and_consent(installation):
    client, plugin, root, _=installation
    prefix='/casting-studio/api'
    res=client.get(prefix+'/catalog').json()
    assert any(x['path']=='Ada_Test_H3.safetensors' for x in res['models'])
    assert all('Private_Test' not in x['path'] for x in res['models'])
    public={'key':'','person':'Ada Test','character':'','production':'','refmod':'Ada_Test_H3.safetensors'}
    r=client.put(prefix+'/choices',json=public)
    assert r.status_code==200,r.text  # Regression: v6.8.2 checked private inventory for public choices.
    # Private RefMod cannot be used by a public profile.
    r=client.put(prefix+'/choices',json={**public,'person':'Private Test','refmod':'personal/Private_Test_H3.safetensors'})
    assert r.status_code==400,r.text
    private={'name':'Private Test','relationship':'Friend','notes':'DO NOT EXPORT THESE NOTES',
             'consent':False,'h3_refmod':'personal/Private_Test_H3.safetensors'}
    r=client.post(prefix+'/personal',json=private)
    assert r.status_code==200,r.text
    person=client.get(prefix+'/personal').json()[0]
    choice={'key':'','person':'Private Test','character':'','production':'',
            'refmod':'personal/Private_Test_H3.safetensors','personal_id':person['id']}
    assert client.put(prefix+'/choices',json=choice).status_code==403
    private['consent']=True
    assert client.put(prefix+'/personal/'+person['id'],json=private).status_code==200
    assert client.put(prefix+'/choices',json=choice).status_code==200
    prompt=client.get(prefix+'/prompts/export?model=h3_video').text
    assert 'Private Test' in prompt
    assert 'Friend' in prompt
    assert 'DO NOT EXPORT THESE NOTES' not in prompt
    # Consent revocation must be authoritative at export, not just choice time.
    private['consent']=False
    assert client.put(prefix+'/personal/'+person['id'],json=private).status_code==200
    prompt2=client.get(prefix+'/prompts/export?model=h3_video').text
    assert 'Private Test' not in prompt2
    assert client.get(prefix+'/images/search?actress=Private+Test').status_code==403


def test_fork_metadata_discovery_and_path_safety(installation):
    client, plugin, root, module=installation
    folder=root/'plugins'/'refmod-fork';folder.mkdir(parents=True)
    (folder/'plugin_info.json').write_text(json.dumps({
        'name':'Refmods For Wan GP','author':'jedsdead','version':'0.38.1-fork.58',
        'url':'https://github.com/jedsdead/Refmod-Fork'}))
    info=plugin.adapter.discover()
    assert info['installed'] is True
    assert info['version']=='0.38.1-fork.58'
    assert info['supported_models']['flux3_klein'] is True
    assert info['inventory']['h3_private']==1
    p=plugin.adapter.validate_refmod(relative_path='Ada_Test_H3.safetensors',family='minimax_h3')
    assert p.is_file()
    p=plugin.adapter.validate_refmod(relative_path='personal/Private_Test_H3.safetensors',family='minimax_h3',personal=True)
    assert p.is_file()
    for path,kind,private in [
        ('../personal/Private_Test_H3.safetensors','minimax_h3',False),
        ('personal/Private_Test_H3.safetensors','minimax_h3',False),
        ('Ada_Test_H3.safetensors','minimax_h3',True),
        ('flux2/personal/Private_Test_H3.safetensors','flux2',False),
        ('../../etc/passwd','flux2',False),
    ]:
        with pytest.raises(ValueError):
            plugin.adapter.validate_refmod(relative_path=path,family=kind,personal=private)


def test_docker_mode_unchanged(tmp_path):
    import subprocess
    env=dict(os.environ)
    env.update({'DATA_DIR':str(tmp_path/'docker_data'),
                'REFMOD_DIR':str(tmp_path/'public'),
                'REFMOD_FLUX_DIR':str(tmp_path/'flux'),
                'PERSONAL_H3_DIR':str(tmp_path/'private'),
                'PERSONAL_FLUX_DIR':str(tmp_path/'flux_private'),
                'PYTHONPATH':str(PACKAGE/'app')})
    for key in ('CASTING_STUDIO_DATA_DIR','CASTING_STUDIO_H3_DIR','CASTING_STUDIO_FLUX_DIR',
                'CASTING_STUDIO_PERSONAL_H3_DIR','CASTING_STUDIO_PERSONAL_FLUX_DIR'):
        env.pop(key,None)
    proc=subprocess.run([sys.executable,'-c', '''
import server
from fastapi.testclient import TestClient
server.startup()
client=TestClient(server.app)
assert client.get('/').status_code==200
assert client.get('/api/models/options').status_code==200
assert client.get('/api/personal').json()==[]
assert client.get('/api/prompts/export?model=h3_video').status_code==200
print('Standalone Docker interface works')
'''],env=env,text=True,capture_output=True)
    assert proc.returncode==0,proc.stderr
    assert (tmp_path/'docker_data'/'casting.sqlite3').exists()


def test_docker_import_creates_consistent_snapshot_without_overwrite(tmp_path):
    import sqlite3
    from importlib.machinery import SourceFileLoader
    source=tmp_path/'source';source.mkdir()
    (source/'photos').mkdir();(source/'photos'/'x.jpg').write_bytes(b'fake-photo')
    db=sqlite3.connect(source/'casting.sqlite3')
    db.execute('CREATE TABLE sample_private (text TEXT)')
    db.execute('INSERT INTO sample_private VALUES (?)',('private notes',))
    db.commit();db.close()
    spec=importlib.util.spec_from_file_location('import_tool',PACKAGE/'tools'/'import_docker_data.py')
    tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    target=tmp_path/'new_data'
    assert tool.import_data(source,target,dry_run=True)['dry_run'] is True
    assert not target.exists()
    tool.import_data(source,target)
    assert (target/'photos'/'x.jpg').read_bytes()==b'fake-photo'
    with sqlite3.connect(target/'casting.sqlite3') as db:
        assert db.execute('SELECT text FROM sample_private').fetchone()[0]=='private notes'
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    with pytest.raises(FileExistsError):
        tool.import_data(source,target)
    with sqlite3.connect(source/'casting.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM sample_private').fetchone()[0]==1

def _mock_fork(root):
    folder=root/'plugins'/'refmod-fork'
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'plugin_info.json').write_text(json.dumps({'name':'Refmods For Wan GP',
       'author':'jedsdead','version':'0.38.1-fork.58',
       'url':'https://github.com/jedsdead/Refmod-Fork'}))


class FakeTaskHandle:
    def __init__(self, result=None):
        from types import SimpleNamespace
        self._result = result or SimpleNamespace(success=True,generated_files=['/tmp/mock_output.mp4'],errors=[],cancelled=False)
    def result(self):return self._result
    def cancel(self):return True

class FakeWanSession:
    def __init__(self, defs=None):
        self.defs=defs if defs is not None else [
            {'model_type':'h3_ref2va_pruned_checkpoint','architecture':'minimax_h3_ref2va_pruned',
             'name':'H3 Ref2VA 20B pruned','metadata':{'base_model_type':'minimax_h3_ref2va'},
             'custom_settings':[{'id':'h3_refmod_state'}]},
            {'model_type':'flux2_dev','architecture':'flux2_dev','name':'Flux 2 Dev',
             'custom_settings':[{'id':'flux_refmod_state'}]},
        ]
        self.submitted=[]
    def list_model_defs(self):return self.defs
    def merge_settings_with_defaults(self,settings):
        return {**settings, 'custom_settings':{'stale':'prior state','h3_refmod_state':'old selector'}}
    def submit_task(self,settings,callbacks=None):
        self.submitted.append(settings)
        return FakeTaskHandle()


def _create_public_selection(client,refmod='Ada_Test_H3.safetensors'):
    prefix='/casting-studio/api'
    c={'key':'','person':'Ada Test','character':'','production':'','refmod':refmod}
    r=client.put(prefix+'/choices',json=c)
    assert r.status_code==200,r.text
    data=client.get(prefix+'/choices').json()
    return next(x for x in data if x['person']=='Ada Test')['key']


def _await_job(client,job_id):
    import time
    for _ in range(100):
        r=client.get('/casting-studio/api/generator/jobs/'+job_id)
        assert r.status_code==200,r.text
        state=r.json()
        if state['state'] not in ('queued','running'):
            return state
        time.sleep(.02)
    raise AssertionError('Mock job failed to finish')


def test_end_to_end_h3_queue_and_model_setting_guard(installation):
    client,plugin,root,_=installation
    _mock_fork(root)
    session=FakeWanSession();plugin.queue_bridge.api_session=session
    key=_create_public_selection(client)
    models=client.get('/casting-studio/api/generator/models?model=h3_video').json()['models']
    assert len(models)==1 and models[0]['ready']
    body={'choice_key':key,'model':'h3_video','model_type':models[0]['model_type'],'scene':1,
          'strength':1.5,'steps':8,'resolution':'1280x720'}
    r=client.post('/casting-studio/api/generator/preview',json=body)
    assert r.status_code==200,r.text
    assert 'Ada Test' in r.json()['prompt']
    r=client.post('/casting-studio/api/generator/submit',json=body)
    assert r.status_code==200,r.text
    job=_await_job(client,r.json()['id'])
    assert job['state']=='completed',job
    assert job['files']==['/tmp/mock_output.mp4']
    assert len(session.submitted)==1
    sent=session.submitted[0]
    assert sent['video_length']=='15s'
    assert sent['num_inference_steps']==8
    assert sent['resolution']=='1280x720'
    assert sent['custom_settings']['stale']=='prior state'
    state=json.loads(sent['custom_settings']['h3_refmod_state'])
    assert state['rows'][0]['mod']=='celebs/Ada_Test_H3'
    assert state['rows'][0]['strength']==1.5
    assert 'Ada Test' in sent['prompt']
    no_fork=FakeWanSession([{**session.defs[0], 'custom_settings':[]}])
    plugin.queue_bridge.api_session=no_fork
    models2=client.get('/casting-studio/api/generator/models?model=h3_video').json()['models']
    assert models2[0]['ready'] is False
    r=client.post('/casting-studio/api/generator/submit',json=body)
    assert r.status_code==400 and 'h3_refmod_state' in r.text
    assert not no_fork.submitted


def test_private_queue_consent_and_notes(installation):
    client,plugin,root,_=installation
    api='/casting-studio/api'
    _mock_fork(root)
    session=FakeWanSession();plugin.queue_bridge.api_session=session
    personal={'name':'Private Test','relationship':'Friend','notes':'PRIVATE NOTES MUST NOT ENTER GPU PROMPT',
              'consent':True,'h3_refmod':'personal/Private_Test_H3.safetensors'}
    assert client.post(api+'/personal',json=personal).status_code==200
    profile=client.get(api+'/personal').json()[0]
    choice={'key':'','person':'Private Test','character':'','production':'',
            'refmod':personal['h3_refmod'],'personal_id':profile['id']}
    assert client.put(api+'/choices',json=choice).status_code==200
    key=next(x for x in client.get(api+'/choices').json() if x['person']=='Private Test')['key']
    body={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint'}
    r=client.post(api+'/generator/submit',json=body)
    assert r.status_code==200,r.text
    state=_await_job(client,r.json()['id'])
    assert state['state']=='completed',state
    payload=session.submitted[-1]
    assert 'Friend' in payload['prompt']
    assert 'PRIVATE NOTES' not in payload['prompt']
    assert 'personal/Private_Test_H3'==json.loads(payload['custom_settings']['h3_refmod_state'])['rows'][0]['mod']
    personal['consent']=False
    assert client.put(api+'/personal/'+profile['id'],json=personal).status_code==200
    r=client.post(api+'/generator/submit',json=body)
    assert r.status_code==403,r.text
    assert len(session.submitted)==1


def test_flux_queue_and_image_chaining_guard(installation):
    client,plugin,root,_=installation
    api='/casting-studio/api'
    fluxfile=root/'refmods'/'flux2'/'celebs'/'Ada_Test_FLUX.safetensors'
    fluxfile.write_bytes(b'not a real model')
    _mock_fork(root)
    session=FakeWanSession();plugin.queue_bridge.api_session=session
    key=_create_public_selection(client)
    body={'choice_key':key,'model':'flux2_dev','model_type':'flux2_dev','scene':1}
    r=client.post(api+'/generator/submit',json=body)
    assert r.status_code==200,r.text
    state=_await_job(client,r.json()['id'])
    assert state['state']=='completed',state
    payload=session.submitted[-1]
    assert 'flux_refmod_state' in payload['custom_settings']
    assert json.loads(payload['custom_settings']['flux_refmod_state'])['rows'][0]['mod']=='celebs/Ada_Test_FLUX'
    assert 'h3_refmod_state' not in payload['custom_settings']
    r=client.post(api+'/generator/submit',json={**body,'scene':2})
    assert r.status_code==200,r.text
    assert _await_job(client,r.json()['id'])['state']=='completed'
    assert 'Image 2/5' in session.submitted[-1]['prompt']
    assert 'previous still' not in session.submitted[-1]['prompt']
    r=client.post(api+'/generator/submit',json={**body,'extra_settings':{'custom_settings':{'flux_refmod_state':'other'}}})
    assert r.status_code==400 and 'override' in r.text


def test_model_discovery_without_live_gradio_session_and_resolution_picker(installation):
    """Regression for screenshot: deferred session says live Gradio state missing."""
    client, plugin, root, _ = installation
    _mock_fork(root)
    fake = FakeWanSession()
    class DeferredSession:
        def list_model_defs(self):
            raise RuntimeError('WanGP WebUI session requires access to the live Gradio state component.')
    plugin.queue_bridge.api_session = DeferredSession()
    plugin.queue_bridge.providers = {
        'list_model_defs': fake.list_model_defs,
        'get_factory_settings': lambda model_type: {'resolution':'1280x720'},
        'get_lora_dir': lambda model_type: str(root/'loras'/model_type),
    }
    api='/casting-studio/api'
    r=client.get(api+'/generator/models?model=h3_video')
    assert r.status_code==200,r.text
    assert r.json()['models'][0]['ready'] is True
    r=client.get(api+'/generator/model-details?model=h3_video&model_type=h3_ref2va_pruned_checkpoint')
    assert r.status_code==200,r.text
    details=r.json()
    assert details['resolution_default']=='1280x720'
    assert any(item['value']=='1280x720' for item in details['resolutions'])
    html=client.get('/casting-studio/').text
    assert 'v1b5.2.1' in html
    assert '<select id="generatorResolution"' in html
    assert 'generatorLoraRows' in html
    assert 'function addGeneratorLora' in html


def test_multiple_lora_strengths_validation_and_submission(installation):
    client,plugin,root,_=installation
    _mock_fork(root)
    session=FakeWanSession();plugin.queue_bridge.api_session=session
    lora_dir=root/'loras'/'h3_ref2va_pruned_checkpoint'
    (lora_dir/'shared').mkdir(parents=True)
    (lora_dir/'MMH3-RealismSlider-V1.safetensors').write_bytes(b'fake weights')
    (lora_dir/'shared'/'Second_Style.sft').write_bytes(b'fake weights')
    (lora_dir/'refmods_plugin'/'private').mkdir(parents=True)
    (lora_dir/'refmods_plugin'/'private'/'Secret.safetensors').write_bytes(b'secret')
    plugin.queue_bridge.providers={
        'get_factory_settings':lambda model_type: {'resolution':'960x544'},
        'get_lora_dir': lambda model_type: str(lora_dir),
    }
    api='/casting-studio/api'
    modeltype='h3_ref2va_pruned_checkpoint'
    details=client.get(api+'/generator/model-details',params={'model':'h3_video','model_type':modeltype})
    assert details.status_code==200,details.text
    catalog=details.json()['loras']
    assert 'MMH3-RealismSlider-V1.safetensors' in catalog
    assert 'shared/Second_Style.sft' in catalog
    assert all('Secret' not in x for x in catalog)
    key=_create_public_selection(client)
    choices=[{'name':'MMH3-RealismSlider-V1.safetensors','multiplier':1.5},
             {'name':'shared/Second_Style.sft','multiplier':0.65}]
    body={'choice_key':key,'model':'h3_video','model_type':modeltype,'loras':choices}
    r=client.post(api+'/generator/submit',json=body)
    assert r.status_code==200,r.text
    state=_await_job(client,r.json()['id'])
    assert state['state']=='completed',state
    sent=session.submitted[-1]
    assert sent['activated_loras']==['MMH3-RealismSlider-V1.safetensors','shared/Second_Style.sft']
    assert sent['loras_multipliers']=='1.5 0.65'
    assert sent['custom_settings']['h3_refmod_state']
    for bad in ([{'name':'not-installed.safetensors','multiplier':1}],
                [{'name':'MMH3-RealismSlider-V1.safetensors','multiplier':'Infinity'}],
                [choices[0],choices[0]],
                [{'name':'refmods_plugin/private/Secret.safetensors','multiplier':1}]):
        result=client.post(api+'/generator/submit',json={**body,'loras':bad})
        assert result.status_code==400,result.text
    bad_advanced=client.post(api+'/generator/submit',json={**body,'extra_settings':{'activated_loras':['other']}})
    assert bad_advanced.status_code==400,bad_advanced.text
    assert len(session.submitted)==1


def test_native_gradio_handoff_never_submits_from_fastapi(installation):
    client,plugin,root,_=installation
    _mock_fork(root)
    session=FakeWanSession()
    plugin.queue_bridge.api_session=session
    plugin.queue_bridge.dispatch_mode='gradio'
    plugin.queue_bridge.providers={'list_model_defs':session.list_model_defs,
                                  'get_factory_settings':lambda _: {'resolution':'1280x720'},
                                  'get_lora_dir': lambda _: str(root/'loras'/'h3')}
    key=_create_public_selection(client)
    body={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint',
          'scene':1,'steps':8,'resolution':'1280x720'}
    api='/casting-studio/api'
    res=client.post(api+'/generator/submit',json=body)
    assert res.status_code==200,res.text
    jid=res.json()['id']
    assert not session.submitted, 'FastAPI must never submit to the Gradio queue'
    assert plugin.queue_bridge.status(jid)['state']=='queued'
    assert len(plugin.queue_bridge._pending)==1
    result=plugin.queue_bridge.process_pending_in_gradio(session)
    assert 'completed' in result
    assert plugin.queue_bridge.status(jid)['state']=='completed'
    assert len(session.submitted)==1
    assert plugin.queue_bridge.process_pending_in_gradio(session)=='No casting jobs are waiting.'
    html=client.get('/casting-studio/').text
    assert '#casting_native_queue_button' in html
    assert 'button.click()' in html


def test_native_gradio_revalidates_revoked_consent(installation):
    client,plugin,root,_=installation
    _mock_fork(root)
    fake=FakeWanSession()
    plugin.queue_bridge.api_session=fake
    plugin.queue_bridge.dispatch_mode='gradio'
    plugin.queue_bridge.providers={'list_model_defs':fake.list_model_defs,
                                  'get_factory_settings':lambda _: {},
                                  'get_lora_dir': lambda _: str(root/'loras'/'h3')}
    api='/casting-studio/api'
    person={'name':'Private Test','relationship':'Friend','notes':'SECRET',
            'consent':True,'h3_refmod':'personal/Private_Test_H3.safetensors'}
    res=client.post(api+'/personal',json=person)
    assert res.status_code==200,res.text
    pid=res.json()['id']
    choice={'key':'','person':'Private Test','character':'','production':'',
            'refmod':'personal/Private_Test_H3.safetensors','personal_id':pid}
    res=client.put(api+'/choices',json=choice)
    assert res.status_code==200,res.text
    key=next(x for x in client.get(api+'/choices').json() if x.get('personal_id')==pid)['key']
    body={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint'}
    res=client.post(api+'/generator/submit',json=body)
    assert res.status_code==200,res.text
    jid=res.json()['id']
    person['consent']=False
    assert client.put(api+'/personal/'+pid,json=person).status_code==200
    plugin.queue_bridge.process_pending_in_gradio(fake)
    status=plugin.queue_bridge.status(jid)
    assert status['state']=='failed'
    assert not fake.submitted, 'Consent revoked after save must block queue submission'


def test_native_gradio_queue_cancel_before_trigger(installation):
    client,plugin,root,_=installation
    _mock_fork(root)
    fake=FakeWanSession()
    plugin.queue_bridge.api_session=fake
    plugin.queue_bridge.dispatch_mode='gradio'
    plugin.queue_bridge.providers={'list_model_defs':fake.list_model_defs,
                                  'get_factory_settings':lambda _: {},
                                  'get_lora_dir': lambda _: str(root/'loras'/'h3')}
    key=_create_public_selection(client)
    api='/casting-studio/api'
    res=client.post(api+'/generator/submit',json={
        'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint'})
    jid=res.json()['id']
    assert client.post(api+'/generator/jobs/'+jid+'/cancel').status_code==200
    assert plugin.queue_bridge.status(jid)['state']=='cancelled'
    assert plugin.queue_bridge.process_pending_in_gradio(fake)=='No casting jobs are waiting.'
    assert not fake.submitted


def test_h3_character_first_prompts_and_years(installation):
    """New default must anchor one character, not become the performer after a transition."""
    client, _, _, _ = installation
    from importlib import import_module
    srv = import_module('cb_under_test.app.server')
    with srv.connect() as db:
        db.execute('INSERT OR REPLACE INTO productions(key,name,year,kind) VALUES(?,?,?,?)',
                   (srv.token('Star Wars: A New Hope'),'Star Wars: A New Hope',1977,'film'))
    item={'person':'Carrie Fisher','character':'Princess Leia Organa',
          'production':'Star Wars: A New Hope','refmod':'Carrie_Fisher_H3.safetensors'}
    template={**srv.SAMPLE_TEMPLATE,'video_count':4}
    video=srv.prompt_for_selection(item,template)
    scenes=video.split('\n\n')
    assert len(scenes)==4
    for scene in scenes:
        assert '<Subject 1> is Princess Leia Organa as portrayed by Carrie Fisher in Star Wars: A New Hope (1977).' in scene
        assert 'all images provided' in scene
        assert '<Subject 2>' not in scene
        assert '<Subject 1> (throughout [Shot 1]): fully_preserved' in scene
        assert 'Princess Leia Organa’' in scene
        assert 'partially_preserved' not in scene
        assert 'wardrobe_description:' in scene
    # One portrayal, not a second person called by another subject number.
    assert 'Carrie Fisher portraying' not in video
    assert 'A crisp, fixed bottom caption reads: "Carrie Fisher - Princess Leia Organa - Star Wars: A New Hope (1977)".' in scenes[0]
    # Year is used when available, never fabricated when the production has no recorded year.
    unknown={**item,'production':'Uncatalogued Story'}
    text=srv.prompt_for_selection(unknown,template)
    assert 'in Uncatalogued Story.' in text
    assert 'Uncatalogued Story (' not in text
    dated={**item,'production':'Star Wars: A New Hope (1977)'}
    assert 'in Star Wars: A New Hope (1977).' in srv.prompt_for_selection(dated,template)
    assert '(1977) (1977)' not in srv.prompt_for_selection(dated,template)

def test_h3_personal_profiles_preserve_previous_identity_template(installation):
    from importlib import import_module
    srv = import_module('cb_under_test.app.server')
    item={'person':'Private Test','relationship':'Friend', 'character':'','production':'',
          'refmod':'personal/Private_Test_H3.safetensors'}
    video=srv.prompt_for_selection(item,srv.SAMPLE_TEMPLATE,personal=True)
    assert '<Subject 1> is Private Test, appearing as themselves in a professional photography studio.' in video
    assert 'partially_preserved' in video
    assert 'fully_preserved' not in video
    assert 'Princess Leia' not in video
    assert 'Private Test - Friend' in video

# v6.9.0-dev5.2: public role refresh and RefMod Workshop regressions.
def test_saved_roles_are_selectable_without_network(installation):
    client,plugin,root,_=installation
    api='/casting-studio/api'
    for production,character in [('Example Series','Captain'),('Example Film','Engineer')]:
        assert client.post(api+'/productions/cast',json={'production':production,'actress':'Ada Test','character':character}).status_code==200
    catalog=client.get(api+'/catalog').json()
    found={(r['production'],r['character']) for r in catalog['roles'] if r['actress']=='Ada Test'}
    assert found=={('Example Series','Captain'),('Example Film','Engineer')}


def test_credit_refresh_adds_roles_idempotently_and_skips_personal(installation,monkeypatch):
    from importlib import import_module
    client,plugin,root,_=installation
    api='/casting-studio/api'
    (root/'refmods'/'minimax_h3'/'celebs'/'Mackenzie_Davis_H3.safetensors').write_bytes(b'test')
    client.post(api+'/catalog/rescan')
    server=import_module(plugin.__class__.__module__.rsplit('.',1)[0]+'.app.server')
    monkeypatch.setattr(server,'fetch_credits',lambda name: ([
        {'production':'Made Up Test Title','character':'Specific Named Role','year':2026,'source':'Test'}],[]))
    first=server.sync_one_public_person('Mackenzie Davis')
    second=server.sync_one_public_person('Mackenzie Davis')
    assert first['added']==1 and second['added']==0
    catalog=client.get(api+'/catalog').json()
    assert any(r['production']=='Made Up Test Title' and r['character']=='Specific Named Role' for r in catalog['roles'])
    assert client.post(api+'/credits/refresh',json={'person':'Private Test'}).status_code==404


def test_filmography_parsers_accept_explicit_roles_only():
    from app.credit_sync import parse_wikipedia_filmography, parse_tvmaze_castcredits
    wiki='''<h2>Filmography</h2><table class="wikitable">
      <tr><th>Year</th><th>Title</th><th>Role</th><th>Notes</th></tr>
      <tr><td>2015</td><td>The Martian</td><td>Mindy Park</td><td></td></tr>
      <tr><td>2025</td><td>Unreleased</td><td>TBA</td><td></td></tr></table>'''
    result=parse_wikipedia_filmography(wiki,'Mackenzie Davis')
    assert len(result)==1 and result[0]['character']=='Mindy Park'
    tv=[{'_embedded':{'show':{'name':'Halt and Catch Fire','premiered':'2014-06-01'},
                        'character':{'name':'Cameron Howe'}}},
        {'_embedded':{'show':{'name':'Show with unspecified role'},'character':{'name':''}}}]
    parsed=parse_tvmaze_castcredits(tv,'Mackenzie Davis')
    assert len(parsed)==1 and parsed[0]['year']==2014


def test_workshop_safe_names_and_fork_payload(installation):
    from importlib import import_module
    _client,plugin,root,_=installation
    wk=import_module(plugin.__class__.__module__.rsplit('.',1)[0]+'.workshop_bridge')
    assert wk.safe_mod_name('Mackenzie Davis H3')=='celebs/Mackenzie_Davis_H3'
    assert wk.safe_mod_name('../../name')=='celebs/name'
    with pytest.raises(ValueError):wk.safe_mod_name('..')
    with pytest.raises(ValueError):wk.build_extract_spec('personal/Private',[],mode='encode')
    paths=[root/'one.jpg',root/'two.jpg']
    spec=wk.build_extract_spec('celebs/Mackenzie_Davis_H3',paths)
    assert spec['image_paths']==list(map(str,paths))
    assert spec['save'] is True
    task=wk.WorkshopTask('extract','h3_ref2va_pruned_checkpoint',spec['name'],spec,root/'output.safetensors')
    result=wk.extract_job_settings(FakeWanSession(),task)
    assert result['video_length']==107
    assert json.loads(result['custom_settings']['h3_refmod_state'])['__h3refmod_extract__']['name']==task.name


def test_workshop_mount_is_readonly_without_live_queue(installation):
    client,plugin,root,_=installation
    api='/casting-studio/api'
    # Public photo discovery can work offline; actual VAE jobs require the native tab.
    assert client.get(api+'/workshop/sources').status_code==200
    assert client.get(api+'/workshop/models').status_code==503
    assert client.get(api+'/workshop/mods').status_code==200
    assert client.post(api+'/workshop/create',json={
        'person':'Ada Test','image_ids':['fake'],'name':'Ada Test','model_type':'h3_ref2va_pruned_checkpoint',
    }).status_code==400


def test_workshop_native_relay_requires_output_and_preserves_existing_file(installation):
    from importlib import import_module
    from types import SimpleNamespace
    client,plugin,root,_=installation
    _mock_fork(root)
    module=import_module(plugin.__class__.__module__.rsplit('.',1)[0]+'.workshop_bridge')
    h3=root/'refmods'/'minimax_h3'/'celebs'
    expected=h3/'New_Ada_H3.safetensors'
    session=FakeWanSession()
    def make_output(settings, callbacks=None):
        session.submitted.append(settings)
        # Fake the fork's disk output. A fork extraction normally returns no video.
        metadata=json.dumps({'__metadata__':{'refmod_meta':json.dumps({'kind':'image','name':'New_Ada_H3'})},'latent':{'dtype':'F32','shape':[1],'data_offsets':[0,4]}}).encode()
        expected.write_bytes(len(metadata).to_bytes(8,'little')+metadata+b'\x00'*4)
        return FakeTaskHandle(SimpleNamespace(success=False,generated_files=[],errors=[],cancelled=False))
    session.submit_task=make_output
    bridge=plugin.queue_bridge
    bridge.api_session=session
    bridge.dispatch_mode='gradio'
    bridge.providers={'list_model_defs':session.list_model_defs,'get_factory_settings':lambda m: {}}
    spec=module.build_extract_spec('celebs/New_Ada_H3',[root/'test.jpg'])
    task=module.WorkshopTask('extract','h3_ref2va_pruned_checkpoint',spec['name'],spec,expected)
    job_id=bridge.enqueue_workshop(task,lambda task: not task.expected.exists() or (_ for _ in ()).throw(ValueError('Exists')))
    assert bridge.status(job_id)['state']=='queued'
    bridge.process_pending_in_gradio(session)
    assert bridge.status(job_id)['state']=='completed'
    assert expected.stat().st_size>128
    assert json.loads(session.submitted[-1]['custom_settings']['h3_refmod_state'])['__h3refmod_extract__']['name']==task.name

"""RefMod Workshop path handling for linked storage, without a GPU."""
import importlib,json
from types import SimpleNamespace
import pytest
from test_native_plugin import installation
from test_dev510 import mod
API='/casting-studio/api'


def linked_folder(path, dest):
    path.rename(dest)
    try:path.symlink_to(dest,target_is_directory=True)
    except OSError:pytest.skip('Directory symlinks unavailable')


@pytest.mark.parametrize('family,linked', [('minimax_h3','family'),('minimax_h3','celebs'),('flux2','family'),('flux2','celebs'),('minimax_h3',None),('flux2',None)])
def test_create_in_real_or_linked_folder(installation,monkeypatch,family,linked):
    c,p,root,_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    from cb_under_test.queue_bridge import refmod_identifier
    base=root/'refmods'/family
    if linked:linked_folder(base if linked=='family' else base/'celebs',root/'external library')
    source=root/'photo.jpg';source.write_bytes(b'fixture')
    monkeypatch.setattr(srv,'workshop_photo_rows',lambda *a:[{'id':'a','path':source}])
    monkeypatch.setattr(p.adapter,'discover',lambda:{'fork_revision':58,'installed':True})
    monkeypatch.setattr(p.queue_bridge,'models',lambda *a:[{'model_type':'fixture-model','ready':True}])
    p.queue_bridge.dispatch_mode='gradio'
    class Session:
        def merge_settings_with_defaults(self,data):return data
        def submit_task(self,settings,callbacks):
            field='h3_refmod_state' if family=='minimax_h3' else 'flux_refmod_state'
            spec=next(iter(json.loads(settings['custom_settings'][field]).values()))
            assert spec['name']=='celebs/New_Example'
            mod(base/'celebs/New_Example.safetensors',{'name':spec['name'],'kind':'image'},'refmod_meta' if family=='minimax_h3' else 'klein9_refmod_meta')
            return SimpleNamespace(result=lambda:SimpleNamespace(errors=[]))
    p.queue_bridge.api_session=Session()
    request={'person':'Example Person','image_ids':['a'],'name':'New Example','model_type':'fixture-model','family':family}
    r=c.post(API+'/workshop/create',json=request);assert r.status_code==200,r.text
    p.queue_bridge.process_pending_in_gradio(p.queue_bridge.api_session)
    assert p.queue_bridge.status(r.json()['job_id'])['state']=='completed'
    output=base/'celebs/New_Example.safetensors';assert output.is_file()
    assert refmod_identifier(output,p.adapter.refmod_root,family)=='celebs/New_Example'
    logical='New_Example.safetensors' if family=='minimax_h3' else 'flux2/celebs/New_Example.safetensors'
    assert p.adapter.validate_refmod(relative_path=logical,family=family)==output.resolve()
    assert any(m['path']==logical for m in srv.scan(force=True))
    assert c.post(API+'/workshop/create',json=request).status_code==409
    assert c.get(API+'/settings/paths').json()['workshop_output']==str((root/'refmods/minimax_h3/celebs').resolve())


def test_block_dangling_file_link_and_public_private_overlap(installation):
    _,p,root,_=installation
    from cb_under_test.workshop_bridge import public_workshop_path
    public=root/'refmods/minimax_h3/celebs'
    target=root/'unrelated.safetensors'
    link=public/'example.safetensors'
    try:link.symlink_to(target)
    except OSError:pytest.skip('Symlinks unavailable')
    with pytest.raises(ValueError,match='link'):public_workshop_path(p.adapter.refmod_root,'minimax_h3','celebs/example','.safetensors')
    link.unlink()
    public.rename(root/'old_public');public.symlink_to(root/'refmods/minimax_h3/personal',target_is_directory=True)
    with pytest.raises(ValueError,match='overlap'):public_workshop_path(p.adapter.refmod_root,'minimax_h3','celebs/example','.safetensors')


def test_decompile_linked_directories_and_retarget_rejected(installation,monkeypatch):
    c,p,root,_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    from cb_under_test.workshop_bridge import WorkshopTask,public_workshop_path
    h3=root/'refmods/minimax_h3/celebs';linked_folder(h3,root/'external h3')
    dec=root/'refmods/decompiled/celebs';dec.mkdir(parents=True);linked_folder(dec,root/'external decode')
    mod(h3/'Example.safetensors',{'name':'Example','kind':'image'},'refmod_meta')
    monkeypatch.setattr(p.adapter,'discover',lambda:{'fork_revision':58})
    expected=public_workshop_path(p.adapter.refmod_root,'decompiled','celebs/Example')
    task=WorkshopTask('decompile','fixture-model','celebs/Example',{'op':'decompile','name':'celebs/Example'},expected)
    assert srv.validate_workshop_task(task)
    expected.mkdir();(expected/'one.png').write_bytes(b'fixture')
    assert c.get(API+'/workshop/decompiled',params={'name':'celebs/Example'}).status_code==200
    assert c.get(API+'/workshop/decompiled.zip',params={'name':'celebs/Example'}).status_code==200
    other=root/'other output';other.mkdir();dec.unlink();dec.symlink_to(other,target_is_directory=True)
    with pytest.raises(ValueError,match='Invalid decompile'):srv.validate_workshop_task(task)

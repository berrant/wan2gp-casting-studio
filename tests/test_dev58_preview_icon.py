"""Batch transitions clear old previews and native tab icon is rendered SVG."""
from types import SimpleNamespace
from PIL import Image
from test_native_plugin import installation


def test_native_tab_renders_svg_markup(installation):
    _,plugin,_,_=installation
    icon=plugin.tabs[0]['icon']
    assert icon.startswith('<svg') and icon.endswith('</svg>')
    assert 'clapperboard' not in icon
    assert '<path' in icon


def test_next_manifest_task_resets_previous_preview(installation):
    _,plugin,_,_=installation
    b=plugin.queue_bridge
    jid='test-123'
    b._jobs[jid]={'id':jid,'state':'running','batch':True,'total_tasks':3,
                  'task_index':1,'preview_rev':0,'progress':33}
    b._store_preview(jid,SimpleNamespace(image=Image.new('RGB',(160,90)),status='Prompt 1/3 - denoising'))
    assert b.preview(jid) is not None
    assert b.status(jid)['preview_task_index']==1
    b._observe_batch_status(jid,'Prompt 2/3 - Encoding Prompt')
    assert b.preview(jid) is None
    assert b.status(jid)['preview_task_index'] is None
    assert b.status(jid)['preview_rev']==0
    b._store_preview(jid,SimpleNamespace(image=Image.new('RGB',(160,90)),status='Prompt 1/3 - stale'))
    assert b.preview(jid) is None
    b._store_preview(jid,SimpleNamespace(image=Image.new('RGB',(160,90)),status='Prompt 2/3 - denoising'))
    assert b.status(jid)['preview_task_index']==2
    assert b.preview(jid) is not None
    b._observe_batch_progress(jid,SimpleNamespace(task_index=3,task_count=3,status='Prompt 3/3',progress=0))
    assert b.preview(jid) is None
    assert b.status(jid)['task_index']==3

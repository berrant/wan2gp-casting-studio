"""Native vision callback is owned by its Blocks, independent of post-UI hook order."""
import gradio as gr
import pytest
from test_native_plugin import installation

API='/casting-studio/api/appearance/options'

@pytest.mark.parametrize('hook_order',['omitted','before','after','both'])
def test_vision_relay_lifecycle(installation,monkeypatch,hook_order):
    c,p,*_=installation
    native=p.vision_bridge.native
    calls=[]
    models=[{'id':'3','label':'Qwen3.5VL 4B','backend':'quanto_int8'}]
    def options():
        calls.append('discover')
        return models
    monkeypatch.setattr(native,'options',options)
    assert c.get(API).json()['ready'] is False
    if hook_order in ('before','both'):p.post_ui_setup({})
    assert not calls
    ui=p.create_ui()
    if hook_order in ('after','both'):p.post_ui_setup({})
    config=ui.config
    comps={x['props'].get('elem_id'):x['id'] for x in config['components']}
    target=comps['casting_vision_button']
    deps=[d for d in config['dependencies'] if [target,'click'] in [list(t) for t in d['targets']]]
    assert len(deps)==1
    dep=deps[0]
    assert dep['backend_fn'] and 'dataset.jobId' in dep['js']
    assert dep['inputs']==[comps['casting_vision_request']]
    assert dep['outputs']==[comps['casting_vision_response']]
    assert not calls
    assert c.get(API).json()=={'ready':True,'models':models,'default':'3'}
    assert calls==['discover']


def test_failed_binding_does_not_report_ready(installation,monkeypatch):
    c,p,*_=installation
    original=gr.Button.click
    def reject_vision(button,*args,**kw):
        if button.elem_id=='casting_vision_button':raise RuntimeError('synthetic binding failure')
        return original(button,*args,**kw)
    monkeypatch.setattr(gr.Button,'click',reject_vision)
    with pytest.raises(RuntimeError,match='synthetic binding failure'):
        p.create_ui()
    assert c.get(API).json()['ready'] is False


def test_wangp_2020_generator_and_edit_hooks_precede_plugin_tab(installation,monkeypatch):
    """Host 72d50753 builds both forms before calling setup_ui_tabs."""
    c,p,*_=installation
    models=[{'id':'3','label':'Qwen3.5VL 4B','backend':'quanto_int8'}]
    monkeypatch.setattr(p.vision_bridge.native,'options',lambda:models)
    session=object()
    with gr.Blocks() as host:
        with gr.Tabs():
            with gr.Tab('Media Generator'):
                p.post_ui_setup({})
            with gr.Tab('Edit'):
                p.post_ui_setup({})
            assert c.get(API).json()['ready'] is False
            with gr.Tab('Casting Studio'):
                p.create_ui(session)
    comps={x['props'].get('elem_id'):x['id'] for x in host.config['components']}
    for name in ('casting_native_queue_button','casting_queue_manage_button','casting_vision_button'):
        deps=[d for d in host.config['dependencies'] if [comps[name],'click'] in [list(t) for t in d['targets']]]
        assert len(deps)==1 and deps[0]['backend_fn'],name
    assert p.queue_bridge.api_session is session
    assert c.get(API).json()=={'ready':True,'models':models,'default':'3'}

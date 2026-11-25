"""Shared host state must be requested before WanGP builds plugin tabs."""
import gradio as gr
import pytest
from test_native_plugin import installation
from test_dev58_conversion import _setup, API


def inject_main_form(plugin, state):
    # Model WanGP's component injection pass, which precedes the tab constructor.
    if 'state' in plugin.component_requests and getattr(plugin, 'state', None) is None:
        plugin.state = state
    plugin.post_ui_setup({})


@pytest.mark.parametrize('two_forms', [False, True])
def test_state_requested_before_tab_construction(installation, two_forms):
    _, plugin, *_ = installation
    with gr.Blocks():
        state = gr.State({'live': True})
        inject_main_form(plugin, state)
        if two_forms:
            inject_main_form(plugin, gr.State({'wrong': True}))
        plugin.request_component('state')
        plugin.create_ui(object())
    assert getattr(plugin, 'state', None) is state


def test_conversion_callback_resolves_early_injected_state(installation, monkeypatch):
    client, plugin, root, _ = _setup(installation, monkeypatch)
    bridge = plugin.queue_bridge
    session = bridge.api_session
    original = gr.Button.click
    callbacks = {}
    def wrap(button, *args, **kwargs):
        if button.elem_id == 'casting_native_queue_button':
            fn = kwargs['fn']
            def callback():
                # Host wrapper resolves state before invoking plugin code.
                if getattr(plugin, 'state', None) is not state:
                    raise RuntimeError('WanGP WebUI session requires access to the live Gradio state component.')
                return fn()
            callbacks['run'] = callback
            kwargs['fn'] = callback
        return original(button, *args, **kwargs)
    monkeypatch.setattr(gr.Button, 'click', wrap)
    with gr.Blocks():
        state = gr.State({'live': True})
        inject_main_form(plugin, state)
        plugin.request_component('state')
        plugin.create_ui(session)
    res = client.post(API+'/choices/conversion/prepare', json={'target_model':'flux3_klein'})
    assert res.status_code == 200, res.text
    job_id = res.json()['id']
    assert bridge.status(job_id)['state'] == 'queued'
    callbacks['run']()
    assert bridge.status(job_id)['state'] == 'completed'
    assert (root/'refmods/minimax_h3/celebs/Ada_Test_H3.safetensors').exists()
    assert len(bridge.status(job_id)['converted']) == 1

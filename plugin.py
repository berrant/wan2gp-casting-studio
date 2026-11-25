"""Native WanGP app host for the existing Casting Studio FastAPI UI.

WanGP public plugin interfaces host the UI and queue. The optional vision
bridge isolates capability-checked, private host runtime integration.
"""
from __future__ import annotations

import os, sys
from pathlib import Path

import gradio as gr
from fastapi import Response
from shared.utils.plugins import WAN2GPPlugin

from .compat_adapter import RefmodForkAdapter
from .queue_bridge import QueueBridge
from .vision_bridge import NativeVision, VisionBridge


# WanGP's AppBar renders `icon` as SVG markup (not a Lucide icon name).
# Keep the icon self-contained so tab rendering works without a separate image request.
CASTING_TAB_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 64 64" aria-hidden="true"><rect x="1" y="1" width="62" height="62" rx="15" fill="#17142d"/><path d="M18 10h-5a3 3 0 0 0-3 3v5m36-8h5a3 3 0 0 1 3 3v5M10 46v5a3 3 0 0 0 3 3h5m28 0h5a3 3 0 0 0 3-3v-5" fill="none" stroke="#80eadb" stroke-width="3" stroke-linecap="round"/><path d="M48 20a20 20 0 1 0 0 24" fill="none" stroke="#b5a0ff" stroke-width="8" stroke-linecap="round"/><path d="M29 22a2 2 0 0 0-3 1.7v16.6A2 2 0 0 0 29 42l14-8.3a2 2 0 0 0 0-3.4Z" fill="#80eadb"/></svg>'

class CastingStudioPlugin(WAN2GPPlugin):
    def __init__(self):
        super().__init__()
        self.name='Casting Studio for WanGP'
        self.version='1.0.1'
        self.description='Native casting, reference-photo curation, and prompt management for Refmod-Fork.'
        self.wangp_root=Path(__file__).resolve().parents[2]
        self.adapter=RefmodForkAdapter(self.wangp_root)
        self.queue_bridge=QueueBridge(self.adapter)
        self.vision_bridge=VisionBridge(NativeVision(sys.modules.get('wgp')))
        self.vision_button=None

    def setup_ui(self):
        # Request the host component before main-form injection. The session
        # proxy requests it again at tab creation, after injection on some hosts.
        self.request_component("state")
        # WanGP v20.00 may inject a deferred session whose discovery methods
        # demand live Gradio state. Documented requested globals are read-only
        # discovery providers; they do not bind to a browser's Gradio state.
        for global_name in ('list_model_defs', 'get_model_def', 'get_factory_settings', 'get_lora_dir'):
            self.request_global(global_name)
        self.register_web_app('/casting-studio', self.create_web_app)
        self.add_tab(tab_id='casting_studio', label='Casting Studio',
                     component_constructor=self.create_ui, position=-1, icon=CASTING_TAB_ICON)

    def create_ui(self, api_session=None):
        # WanGP injects a queue-backed session into plugin tab constructors.
        # This is the documented public API, not Refmod-Fork UI state.
        # Use ONLY the injected Gradio session, and only from a real Gradio
        # button callback. The iframe's FastAPI requests may validate/park a
        # pending job but must not call submit_task directly.
        self.queue_bridge.api_session=api_session
        self.queue_bridge.dispatch_mode='gradio'
        # Readiness belongs to the actual registered event, not a later host hook.
        self.vision_bridge.ready=False
        with gr.Blocks() as ui:
            # CSS hides the relay visually while keeping real Gradio components
            # mounted: visible=False can prevent DOM click dispatch on some hosts.
            gr.HTML('<style>#casting_native_queue_controls{display:none!important}</style>'
                    '<div class="wangp-addon-web-view" style="width:100%;height:calc(100vh - 178px);min-height:680px">'
                    f'<iframe title="Casting Studio for WanGP" src="./casting-studio/?embedded=1&amp;version={self.version}" '
                    'style="width:100%;height:100%;border:0;border-radius:8px" '
                    'loading="lazy"></iframe></div>')
            with gr.Group(elem_id='casting_native_queue_controls'):
                status = gr.Textbox(label='Casting queue relay', value='Ready for Casting Studio submissions',
                                    interactive=False, max_lines=2)
                run_button = gr.Button('Process pending Casting Studio generation',
                                       elem_id='casting_native_queue_button', size='sm')
                queue_request=gr.Textbox(elem_id='casting_queue_request', value='')
                queue_response=gr.Textbox(elem_id='casting_queue_response', value='', interactive=False)
                queue_button=gr.Button('Inspect or manage native queue', elem_id='casting_queue_manage_button')
                self.vision_request=gr.Textbox(elem_id='casting_vision_request',value='')
                self.vision_response=gr.Textbox(elem_id='casting_vision_response',value='',interactive=False)
                self.vision_button=gr.Button('Analyze character appearance',elem_id='casting_vision_button')
            def manage_queue(request):
                return self.queue_bridge.manage_native_queue(api_session,request)
            # The request is read in the originating browser, not shared via a
            # server-global mailbox. A separate event can run while generation waits.
            queue_button.click(fn=manage_queue, inputs=queue_request, outputs=queue_response,
                               js="(unused) => [document.querySelector('#casting_queue_manage_button')?.dataset.boardRequest || '{}']",
                               show_progress='hidden', concurrency_limit=1)
            def run_casting_submission():
                # A real Gradio callback is required to enter WanGP's native queue.
                return self.queue_bridge.process_pending_in_gradio(api_session)
            run_button.click(fn=run_casting_submission, outputs=status,
                             show_progress='hidden', concurrency_limit=1)
            # Register in the owning Blocks context, just like the native queue.
            # Some hosts skip or invoke post_ui_setup before plugin tabs exist.
            def analyze_native(job_id):
                from .app import server
                native_state=self.vision_bridge.native.shared_state()
                return self.vision_bridge.run(job_id,native_state,server.resolve_appearance_images)
            self.vision_button.click(fn=analyze_native,inputs=self.vision_request,outputs=self.vision_response,
                js="(unused) => [document.querySelector('#casting_vision_button')?.dataset.jobId || '']",
                show_progress='hidden',concurrency_limit=1)
        self.vision_bridge.ready=True
        return ui

    def post_ui_setup(self, components):
        # Request-global attributes are populated by WanGP after building its UI.
        self.queue_bridge.providers = {
            key: getattr(self, key, None)
            for key in ('list_model_defs', 'get_model_def', 'get_factory_settings', 'get_lora_dir')
            if callable(getattr(self, key, None))
        }
        return {}

    # Do not use on_tab_select to create a second WanGPSession. That session
    # lacks the native Gradio click's queue handoff context and can strand
    # inline_queue, producing "WanGP inline queue bridge is busy".

    def create_web_app(self):
        # These four directories exist independently of Refmod-Fork's source code.
        # Keep all persistent personal data OUTSIDE the plugin directory so Git
        # upgrades/reinstalls cannot overwrite them.
        paths=self.adapter.paths()
        os.environ['CASTING_STUDIO_DATA_DIR']=str(Path(os.environ.get('CASTING_STUDIO_DATA_DIR')
                                     or (self.wangp_root/'data'/'casting-studio')))
        os.environ['CASTING_STUDIO_H3_DIR']=str(paths['h3_public'])
        os.environ['CASTING_STUDIO_FLUX_DIR']=str(paths['flux_all'])
        os.environ['CASTING_STUDIO_PERSONAL_H3_DIR']=str(paths['h3_private'])
        os.environ['CASTING_STUDIO_PERSONAL_FLUX_DIR']=str(paths['flux_private'])
        from .app import server
        # A FastAPI app mounted below another ASGI app won't necessarily receive
        # its lifespan startup event; this idempotent initializer is essential.
        server.startup()
        server.app.state.casting_queue_bridge=self.queue_bridge
        server.app.state.casting_vision_bridge=self.vision_bridge
        self.queue_bridge.history_sink=server.persist_cast_job_history
        self.queue_bridge.gallery_sink=server.persist_cast_gallery
        self.queue_bridge.restore_gallery(server.load_cast_gallery())

        @server.app.get('/api/integration/status', include_in_schema=False)
        def integration_status(response: Response):
            response.headers['Cache-Control']='no-store'
            return {'casting_studio':self.version,'mode':'wangp-native',
                    'data_storage':'WanGP/data/casting-studio (or CASTING_STUDIO_DATA_DIR override)',
                    'refmod_fork':self.adapter.discover(),
                    'queue_integration':{'ready':self.queue_bridge.live_session_ready,
                       'reason':('Native Gradio click relay connected; all settings and consent are rechecked on submission.'
                                 if self.queue_bridge.live_session_ready
                                 else self.queue_bridge.session_error or 'Open Casting Studio tab to enable the native Gradio queue relay.')}}
        return server.app

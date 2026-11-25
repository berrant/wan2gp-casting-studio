"""Read-only Status Lite DOM adapter regression; no active WanGP/GPU needed."""
import shutil
from pathlib import Path
import pytest
pw=pytest.importorskip('playwright.sync_api')
from test_generator_session_browser import setup_js
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

HOST='''<section id="status-lite-container">
<section data-status-lite aria-label="Generation status">
<span data-sp-live>Denoising video</span>
<span data-sp-steps>218/360 steps</span><span data-sp-overall>Total elapsed 00:26</span><span data-sp-eta>00:17 ETA</span>
<div data-sp-stages>
<button data-stage-id="prepare" class="status-lite__stage status-lite__stage--complete"><span class="status-lite__stage-name">Prepare</span><span class="status-lite__stage-time">2s</span></button>
<button data-stage-id="denoise" class="status-lite__stage status-lite__stage--current"><span class="status-lite__stage-name">Generate</span><span class="status-lite__stage-time">26s</span></button>
</div>
<span data-sp-detail-progress>60.6%</span><span data-sp-detail-state>Running</span><span data-sp-detail-step-time>0.12s/step</span><span data-sp-detail-message>Generating frames</span>
<div data-sp-downloads><span data-sp-download-summary>1/2 files</span></div>
</section></section>'''

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium is optional')
def test_status_lite_telemetry_in_own_iframe_and_missing_plugin():
    with pw.sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page()
        page.set_content('<div id="lite-host"></div><iframe id="casting" name="casting" src="about:blank"></iframe>')
        frame=page.frame(name='casting')
        frame.evaluate(setup_js)
        frame.set_content(HTML,wait_until='domcontentloaded')
        frame.evaluate("document.querySelector('#generationMonitor').style.display='block'")
        frame.evaluate('syncStatusLiteTelemetry()')
        assert frame.locator('#statusLiteMirror').is_hidden()
        page.locator('#lite-host').evaluate('(el,html)=>{el.innerHTML=html}',HOST)
        frame.evaluate('syncStatusLiteTelemetry()')
        assert frame.locator('#statusLiteMirror').is_visible()
        assert 'Denoising video' in frame.locator('#slmLive').inner_text()
        assert '218/360' in frame.locator('#slmSteps').inner_text()
        assert '00:26' in frame.locator('#slmElapsed').inner_text()
        assert '00:17' in frame.locator('#slmEta').inner_text()
        assert '60.6%' in frame.locator('#slmProgress').inner_text()
        assert '0.12s/step' in frame.locator('#slmSpeed').inner_text()
        assert frame.locator('#slmStages .current').count()==1
        assert frame.locator('#slmStages .complete').count()==1
        assert '1/2 files' in frame.locator('#slmDownload').inner_text()
        # Suspicious text must remain TEXT, not executable HTML.
        page.locator('[data-sp-live]').evaluate('(el)=>el.textContent="<img src=x onerror=alert(1)>"')
        frame.evaluate('syncStatusLiteTelemetry()')
        assert frame.locator('#slmLive img').count()==0
        page.locator('[data-status-lite]').evaluate('(el)=>el.hidden=true')
        frame.evaluate('syncStatusLiteTelemetry()')
        assert 'awaiting active' in frame.locator('#slmLive').inner_text()
        assert frame.locator('#slmStages span').count()==0
        page.locator('#status-lite-container').evaluate('(el)=>el.remove()')
        frame.evaluate('syncStatusLiteTelemetry()')
        assert frame.locator('#statusLiteMirror').is_hidden()
        browser.close()

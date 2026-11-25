"""Workshop navigation hides casting-only controls without losing selections."""
from pathlib import Path
import shutil
import pytest

HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text(encoding='utf-8')

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium unavailable')
def test_workshop_hides_selections_and_restores_state():
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1400,'height':950})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.evaluate('''() => {const f=window.fetch;window.fetch=async (url,opts)=>{const path=String(url).split('?')[0];const data={'api/workshop/sources':{sources:[]},'api/workshop/models':{models:[]},'api/workshop/mods':{mods:[]},'api/personal/refmods':[]}[path];return data===undefined?f(url,opts):{ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)}}}''')
        page.set_content(HTML,wait_until='domcontentloaded')
        page.wait_for_function("choices.length===2 && $('count').textContent==='2'")
        panel=page.locator('#castingSelectionsPanel')
        assert panel.is_visible()
        page.evaluate("$('selectionDetails').open=true")
        state=page.evaluate("JSON.stringify({choices,model:$('promptModel').value,open:$('selectionDetails').open})")
        for tab in ['productions','performers','personal','models','adult','television']:
            page.locator('#workshopTab').click()
            assert not panel.is_visible()
            assert page.locator('#workshopSection').is_visible()
            assert page.locator('#generationMonitor').is_visible()
            assert page.locator('#castingSelectionsPanel').evaluate('(el)=>el.getBoundingClientRect().height')==0
            if tab=='productions':page.locator('#productionsTab').click()
            else:
                page.locator('#peopleMenuButton').click()
                page.locator('[data-people-category="'+('performers' if tab=='adult' else tab)+'"]').click()
                if tab=='adult':
                    # The former dedicated tab is now an ordinary local performer filter.
                    page.locator('#filter').select_option('adult')
                    assert page.evaluate('activeTab')=='performers'
                    assert page.locator('#filter').input_value()=='adult'
            assert panel.is_visible()
            assert not page.locator('#workshopSection').is_visible()
            assert page.evaluate("JSON.stringify({choices,model:$('promptModel').value,open:$('selectionDetails').open})")==state
        assert not errors,errors
        browser.close()

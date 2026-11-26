"""Compact masthead keeps all controls and dynamic status accessible."""
from pathlib import Path
import shutil
import pytest
pw=pytest.importorskip('playwright.sync_api')
from test_generator_session_browser import setup_js
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium missing')
def test_compact_header_responsive_and_live_status():
    with pw.sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1440,'height':820})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.set_content(HTML,wait_until='domcontentloaded')
        page.evaluate("$('catalogScanStatus').textContent='Last scan: 11/26/2026, 5:14:32 AM · 1349 files';setUXMode(false)")
        for width in [2048,1600,1440,1280,1024,850,760,570,390,320]:
            page.set_viewport_size({'width':width,'height':820})
            page.evaluate("renderAppearanceQueue(null)")
            assert page.locator('#appearanceActivity').is_hidden()
            for active in [False,True]:
                if active:
                    page.evaluate("renderAppearanceQueue({id:'test',state:'running',done:3,total:9,message:'Testing'});$('catalogScanStatus').textContent='Scanning 14500/20000 files…';setUXMode(true)")
                    assert page.locator('#appearanceActivity').is_visible()
                layout=page.evaluate('''() => {const h=$('studioHeader'),nav=$('navTabs');const r=e=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y,right:b.right,bottom:b.bottom,height:b.height,width:b.width}};return {header:r(h),nav:r(nav),items:[...h.querySelectorAll('button,.studio-status .note')].filter(e=>!e.hidden).map(r),width:document.documentElement.clientWidth}}''')
                for box in layout['items']:
                    assert box['x']>=-1 and box['right']<=layout['width']+1,(width,active,box,layout)
                    assert box['bottom']<=layout['header']['bottom']+1,(width,active,box)
                assert layout['nav']['y']>=layout['header']['bottom']-1
                if width>=1440 and not active:
                    assert layout['header']['height']<=90,(width,layout)
                    assert layout['nav']['height']<=65,(width,layout)
                if width>=1600 and not active:
                    assert layout['header']['height']<=70,(width,layout)
            page.evaluate("renderAppearanceQueue(null);setUXMode(false);$('catalogScanStatus').textContent='Last scan: 11/26/2026, 5:14:32 AM · 1349 files'")
        page.set_viewport_size({'width':1440,'height':820})
        page.locator('#uxMode').click()
        assert page.locator('body').evaluate("e=>e.classList.contains('ux-basic')")
        page.locator('#integrationButton').click()
        assert page.locator('#aboutModal').is_visible()
        assert 'v1.0.5' in page.locator('#aboutModal').inner_text()
        page.evaluate("$('aboutModal').classList.remove('open')")
        page.locator('#peopleMenuButton').click()
        assert page.locator('#peopleMenu').is_visible()
        page.locator('#peopleMenu [data-people-category=television]').click()
        assert page.locator('#peopleMenu').is_hidden()
        assert 'Television' in page.locator('#peopleSelectedLabel').inner_text()
        assert not errors,errors
        browser.close()

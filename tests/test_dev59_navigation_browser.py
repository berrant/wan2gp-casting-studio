"""dev5.9: sticky navigation must never need its own horizontal scrollbar."""
from pathlib import Path
import shutil
import pytest
playwright = pytest.importorskip('playwright.sync_api')
HTML = (Path(__file__).resolve().parents[1] / 'app/index.html').read_text()

@pytest.mark.parametrize('width,columns', [
    (390,2), (550,2), (570,2), (571,3), (850,3),
    (1120,3), (1121,6), (1440,6), (1920,6), (2048,6)
])
def test_all_navigation_tabs_fit_and_remain_sticky(width, columns):
    if not shutil.which('chromium'):
        pytest.skip('Chromium unavailable')
    with playwright.sync_playwright() as p:
        browser=p.chromium.launch(headless=True, executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':width,'height':760})
        page.set_content(HTML,wait_until='domcontentloaded')
        result=page.evaluate('''() => {
          const n=document.querySelector('#navTabs'), tabs=[...n.querySelectorAll('.nav-tab')];
          return {visible: tabs.map(b=>{const r=b.getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1&&r.width>0}),
                  count:tabs.length, scroll:n.scrollWidth,client:n.clientWidth,
                  columns:getComputedStyle(n).gridTemplateColumns.split(' ').length};
        }''')
        assert result['count']==6 and all(result['visible']),result
        assert result['scroll']<=result['client']+1,result
        assert result['columns']==columns,result
        page.evaluate('''() => {
            const extra=document.createElement('div');extra.style.height='1800px';document.body.append(extra);
            window.scrollTo(0,1000);
        }''')
        page.wait_for_timeout(50)
        assert abs(page.locator('#navTabs').bounding_box()['y'])<2
        browser.close()

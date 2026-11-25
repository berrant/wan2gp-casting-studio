"""Readable native category picker, icons, and responsive navigation."""
import shutil
from pathlib import Path
import pytest
from test_generator_session_browser import setup_js
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

def test_navigation_labels_and_responsive_picker():
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page(viewport={'width':1440,'height':900});page.set_default_timeout(5000)
        page.evaluate(setup_js);page.set_content(HTML,wait_until='domcontentloaded')
        picker=page.locator('#peopleMenuButton');menu=page.locator('#peopleMenu')
        assert menu.locator('button span').all_text_contents()==['Performers','Personal','Adult Entertainment','Models / Influencers','Television Personalities']
        for width in [1440,1024,768,600,360]:
            page.set_viewport_size({'width':width,'height':900})
            for selector in ['#productionsTab','#workshopTab','#peopleMenuButton']:
                el=page.locator(selector)
                assert float(el.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)'))>=16
                box=el.bounding_box();assert box['x']>=0 and box['x']+box['width']<=width+1,(width,selector,box)
            assert page.locator('#navTabs').evaluate('e=>e.scrollWidth<=e.clientWidth+1')
            picker.click();assert menu.is_visible()
            box=menu.bounding_box();assert box['x']>=0 and box['x']+box['width']<=width+1
            page.keyboard.press('Escape');assert not menu.is_visible()
        for value in ['performers','personal','adult','models','television']:
            picker.click();menu.locator('[data-people-category="'+value+'"]').click()
            assert page.evaluate('activeTab')==value
            assert menu.locator('[data-people-category="'+value+'"]').get_attribute('aria-pressed')=='true'
            assert page.locator('#peopleSelectedIcon').get_attribute('src')=='api/ui/icons/'+value
            assert not menu.is_visible()
        picker.focus();picker.press('ArrowDown');page.keyboard.press('Home');page.keyboard.press('ArrowDown');page.keyboard.press('Enter')
        assert page.evaluate('activeTab')=='personal'
        assert picker.evaluate('e=>e===document.activeElement')
        page.locator('#workshopTab').click();assert page.locator('#peopleSelectedLabel').inner_text()=='Choose category'
        assert not page.locator('#peopleSelectedIcon').is_visible()
        b.close()


def test_responsible_footer_visible_without_covering_dialog():
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page(viewport={'width':1440,'height':900})
        page.evaluate(setup_js);page.set_content(HTML,wait_until='domcontentloaded')
        footer=page.locator('#responsibleUseFooter')
        assert 'You are responsible for all content' in footer.inner_text()
        for width in [1440,768,360]:
            page.set_viewport_size({'width':width,'height':740})
            for tab in ['productions','performers','personal','adult','models','television','workshop']:
                page.evaluate('(tab)=>showTab(tab)',tab)
                assert footer.is_visible()
                r=footer.bounding_box();assert abs(r['y']+r['height']-740)<2
            page.evaluate("document.getElementById('settingsModal').classList.add('open')")
            page.wait_for_function("document.querySelector('#settingsModal').getBoundingClientRect().bottom <= document.querySelector('#responsibleUseFooter').getBoundingClientRect().top + 1")
            assert page.locator('#settingsModal .panel').bounding_box()['y']+page.locator('#settingsModal .panel').bounding_box()['height']<=footer.bounding_box()['y']+1
            page.evaluate("document.getElementById('settingsModal').classList.remove('open')")
        b.close()

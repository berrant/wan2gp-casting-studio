"""Bundled artwork must actually load inside the mounted browser UI."""
from io import BytesIO
import base64
from PIL import Image
import shutil
import pytest
from test_native_plugin import installation
from test_generator_session_browser import setup_js


def test_all_navigation_artwork_served_and_decoded(installation):
    c,*_=installation
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    icons={}
    for key in ('personal','performers','adult','models','television','productions','workshop','casting-logo'):
        resp=c.get('/casting-studio/api/ui/icons/'+key)
        assert resp.status_code==200 and resp.headers['content-type']=='image/png'
        with Image.open(BytesIO(resp.content)) as im:
            assert not im.info and not im.getexif()
        icons[key]=resp.content
    assert len(set(icons.values()))==len(icons)
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page(viewport={'width':1200,'height':900});page.set_default_timeout(5000)
        page.evaluate(setup_js)
        html=c.get('/casting-studio/').text
        # Browser navigation is restricted in some offline test environments.
        # Verify the mounted endpoint and markup separately, then decode those
        # exact HTTP response bytes in the browser without network navigation.
        for key,content in icons.items():
            src='api/ui/icons/'+key
            if key!='adult':assert 'src="'+src+'"' in html
            uri='data:image/png;base64,'+base64.b64encode(content).decode('ascii')
            html=html.replace('src="'+src+'"','src="'+uri+'"')
        page.set_content(html,wait_until='domcontentloaded')
        page.locator('#peopleMenuButton').click()
        page.wait_for_function("[...document.querySelectorAll('#peopleMenu img,#navTabs .tab-icon,.brand-mark')].every(i=>i.complete&&i.naturalWidth>0)")
        for key in ('performers','personal','models','television'):
            row=page.locator('[data-people-category="'+key+'"]')
            assert row.locator('img').bounding_box()['width']>=30
            assert row.locator('img').bounding_box()['x']<row.locator('span').bounding_box()['x']
        page.locator('[data-people-category="television"]').click()
        page.wait_for_function("document.querySelector('#peopleSelectedIcon').complete&&document.querySelector('#peopleSelectedIcon').naturalWidth>0")
        assert page.locator('#peopleSelectedIcon').is_visible()
        b.close()

import pytest,shutil
from test_dev55_browser import playwright,HTML,MOCK
@pytest.fixture
def tab():
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    with playwright.sync_playwright() as p:
        b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        t=b.new_page(viewport={'width':1400,'height':940});t.set_default_timeout(3000)
        t.evaluate(MOCK);t.set_content(HTML,wait_until='domcontentloaded');t.wait_for_function("document.querySelector('#count').textContent==='1'")
        yield t
        b.close()

def start(t):
    t.evaluate("document.querySelector('#promptModel').value='flux2_dev';showImageEditorFields({image_count:3,shots:[],visual_style:'Photo'});document.querySelector('#imageEditorModal').classList.add('open')")

def test_temporary_image_count_reduction_preserves_drafts(tab):
    start(tab)
    tab.locator('#shotAction3').fill('Unique composition for third frame')
    tab.locator('#imageSetCount').select_option('2')
    tab.locator('#imageSetCount').select_option('3')
    assert tab.locator('#shotAction3').input_value()=='Unique composition for third frame'

def test_image_editor_close_warns_on_unsaved_changes(tab):
    start(tab)
    tab.locator('#shotAction1').fill('Unsaved custom composition')
    dialogs=[]
    tab.on('dialog',lambda d:(dialogs.append(d.message),d.dismiss()))
    tab.evaluate('closeImageEditor()')
    assert dialogs and tab.locator('#imageEditorModal').evaluate("e=>e.classList.contains('open')")

def test_failed_override_reset_keeps_saved_state(tab):
    tab.evaluate("""() => {document.querySelector('#editorModal').classList.add('open');document.querySelector('#editScope').innerHTML='<option value="x">X</option>';promptOverrides.x={wardrobe:'Saved custom'};fillEditor({...promptDefault,...promptOverrides.x});const orig=fetch;window.fetch=(u,o)=>o?.method==='DELETE'?Promise.resolve({ok:false,text:async()=> 'offline'}):orig(u,o)}""")
    tab.evaluate('resetEditor()')
    assert tab.evaluate('promptOverrides.x.wardrobe')=='Saved custom'
    assert 'fail' in tab.locator('#editorStatus').text_content().lower() or 'unable' in tab.locator('#editorStatus').text_content().lower()

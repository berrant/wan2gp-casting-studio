"""Single root settings and native model-library isolation."""
import importlib,json,shutil
import pytest
from test_native_plugin import installation
API='/casting-studio/api'

def test_root_defaults_legacy_upgrade_and_no_model_writes(installation):
    c,p,root,_=installation;srv=importlib.import_module('cb_under_test.app.server')
    library=root/'refmods';paths=c.get(API+'/settings/paths').json()
    assert paths['refmod_root']==paths['default_root']==str(library)
    assert paths['paths']=={'public_h3':str(library/'minimax_h3/celebs'),'public_flux':str(library/'flux2'),'personal_h3':str(library/'minimax_h3/personal'),'personal_flux':str(library/'flux2/personal')}
    old=dict(paths['paths']);alt=library/'minimax_h3/celebs/alternate';alt.mkdir();old['public_h3']=str(alt)
    srv.PATHS_FILE.write_text(json.dumps(old));assert c.get(API+'/settings/paths').json()==paths
    assert json.loads(srv.PATHS_FILE.read_text())==old
    for name in ['celebs/Public','Legacy','personal/Private']:
        (library/'flux2'/f'{name}.safetensors').write_bytes(b'fixture')
    snapshot={f:f.read_bytes() for f in library.rglob('*.safetensors')}
    assert c.put(API+'/settings/paths',json={'refmod_root':str(library)}).status_code==200
    assert json.loads(srv.PATHS_FILE.read_text())=={'refmod_root':str(library)}
    assert {m['path'] for m in srv.scan(force=True)}=={'Ada_Test_H3.safetensors','flux2/celebs/Public.safetensors','flux2/Legacy.safetensors'}
    assert {m['path'] for m in srv.personal_refmod_inventory()}=={'personal/Private_Test_H3.safetensors','flux2/personal/Private.safetensors'}
    assert snapshot=={f:f.read_bytes() for f in library.rglob('*.safetensors')}

def test_alias_and_wrong_mount_rejected(installation):
    c,p,root,_=installation;srv=importlib.import_module('cb_under_test.app.server')
    native=root/'refmods';alias=root/'linked models';other=root/'unmounted models';other.mkdir()
    try:alias.symlink_to(native,target_is_directory=True)
    except OSError:pytest.skip('Directory links unavailable')
    assert c.put(API+'/settings/paths',json={'refmod_root':str(alias)}).status_code==200
    raw=srv.PATHS_FILE.read_bytes()
    for wrong in [str(other),str(native/'minimax_h3'),str(root/'missing'),'.','']:
        assert c.put(API+'/settings/paths',json={'refmod_root':wrong}).status_code==422
        assert srv.PATHS_FILE.read_bytes()==raw
    assert c.put(API+'/settings/paths',json={'refmod_root':str(native),'personal_h3':str(other)}).status_code==422
    (native/'flux2/personal').rmdir()
    assert c.put(API+'/settings/paths',json={'refmod_root':str(native)}).status_code==200
    assert not (native/'flux2/personal').exists()

def test_separately_linked_families(installation):
    c,p,root,_=installation;srv=importlib.import_module('cb_under_test.app.server')
    native=root/'refmods';external=root/'model storage';external.mkdir()
    for family in ['minimax_h3','flux2']:
        (native/family).rename(external/family)
        try:(native/family).symlink_to(external/family,target_is_directory=True)
        except OSError:pytest.skip('Directory links unavailable')
    r=c.put(API+'/settings/paths',json={'refmod_root':str(external)})
    assert r.status_code==200,r.text
    assert r.json()['refmod_root']==str(external)
    assert r.json()['paths']['public_h3']==str(external/'minimax_h3/celebs')
    assert p.adapter.validate_refmod(relative_path='Ada_Test_H3.safetensors',family='minimax_h3')==external/'minimax_h3/celebs/Ada_Test_H3.safetensors'
    assert srv.scan(force=True)[0]['path']=='Ada_Test_H3.safetensors'

def test_single_root_browser(installation):
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js,HTML
    c,_,root,_=installation;data=c.get(API+'/settings/paths').json()
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page(viewport={'width':900,'height':760});page.set_default_timeout(5000)
        page.evaluate(setup_js)
        page.evaluate('''data=>{const original=window.fetch;window.rootRequests=[];window.fetch=async(url,opts={})=>{if(url==='api/settings/paths'){if(opts.method==='PUT')window.rootRequests.push(JSON.parse(opts.body));return {ok:true,json:async()=>data}}return original(url,opts)}}''',data)
        page.set_content(HTML,wait_until='domcontentloaded');page.evaluate('openLocalSettings()')
        page.wait_for_function("document.getElementById('path_refmod_root').value!==''")
        assert page.locator('#pathsForm input').count()==1
        assert page.locator('#path_refmod_root').input_value()==str(root/'refmods')
        page.locator('summary').filter(has_text='Detected subfolders').click()
        assert 'Personal H3' in page.locator('#pathReadonly').inner_text()
        page.locator('#path_refmod_root').fill('wrong');page.get_by_role('button',name='Use detected root').click()
        page.wait_for_function("document.getElementById('pathStatus').textContent.includes('filled in')")
        page.locator('#saveRootButton').click();page.wait_for_function('window.rootRequests.length===1')
        assert page.evaluate('window.rootRequests')==[{'refmod_root':str(root/'refmods')}]
        b.close()

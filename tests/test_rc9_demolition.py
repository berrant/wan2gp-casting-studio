"""Destructive tests: corrupt catalog, hostile stale temporary file, failed write."""
import io,json,sqlite3
from PIL import Image
import pytest
from test_native_plugin import installation,_create_public_selection
from test_rc2_jackhammer import server,API


def test_corrupt_categories_do_not_crash_catalog(installation):
    c,_,_,_=installation;s=server()
    with s.connect() as db:
        db.execute('INSERT INTO profile_categories VALUES (?,?)',('Ada Test','null'))
        db.execute('INSERT INTO public_profiles(name_key,categories) VALUES (?,?)',('adatest','{'))
    assert c.get(API+'/catalog').status_code==200
    assert c.get(API+'/profiles/categories').json()=={}
    assert c.get(API+'/productions',params={'q':'test'}).status_code==200
    with s.connect() as db:
        assert db.execute('SELECT categories FROM profile_categories').fetchone()==('null',)
        assert db.execute('SELECT categories FROM public_profiles').fetchone()==('{',)


def test_corrupt_cast_rows_preserved_and_valid_rows_available(installation):
    c,_,_,_=installation;s=server()
    assert c.post(API+'/productions/cast',json={'production':'Example Show','actress':'Ada Test','character':'Pilot','year':2020}).status_code==200
    with s.connect() as db:
        db.executemany('INSERT INTO production_cast VALUES (?,?)',[('broken','{'),('null','null'),('wrong','{"actress":[]}')])
    assert c.get(API+'/catalog').status_code==200
    result=c.get(API+'/productions/cast',params={'production':'Example Show'}).json()
    assert [x['character'] for x in result['cast']]==['Pilot']
    with s.connect() as db:assert db.execute("SELECT payload FROM production_cast WHERE key='broken'").fetchone()==('{',)


def test_stale_settings_temp_link_cannot_overwrite_other_file(installation):
    c,_,root,_=installation;s=server();sentinel=root/'unrelated.txt';sentinel.write_bytes(b'unchanged')
    tmp=s.PATHS_FILE.with_suffix('.json.tmp')
    try:tmp.symlink_to(sentinel)
    except OSError:pytest.skip('Symlinks unavailable')
    settings=c.get(API+'/settings/paths').json()
    assert c.put(API+'/settings/paths',json={'refmod_root':settings['refmod_root']}).status_code==200
    assert sentinel.read_bytes()==b'unchanged'
    assert not s.PATHS_FILE.is_symlink()


def test_failed_artwork_database_write_preserves_old_image_and_no_orphan(installation):
    c,_,_,_=installation;s=server()
    buf=io.BytesIO();Image.new('RGB',(120,120),'blue').save(buf,format='PNG')
    def upload():return c.post(API+'/images/upload',params={'key':'actress|synthetic'},content=buf.getvalue(),headers={'content-type':'image/png'})
    assert upload().status_code==200
    before=set(s.PHOTO_DIR.iterdir());mapping=c.get(API+'/images/saved').json()
    with s.connect() as db:db.execute("CREATE TRIGGER reject_image BEFORE INSERT ON images BEGIN SELECT RAISE(ABORT,'simulated write failure'); END")
    # Actual SQLite trigger failure, not a mocked response.
    r=upload()
    assert r.status_code==503
    assert set(s.PHOTO_DIR.iterdir())==before
    assert c.get(API+'/images/saved').json()==mapping


def test_interrupted_settings_rename_preserves_previous_state(installation,monkeypatch):
    c,_,_,_=installation;s=server();from pathlib import Path
    settings=c.get(API+'/settings/paths').json();payload={'refmod_root':settings['refmod_root']}
    assert c.put(API+'/settings/paths',json=payload).status_code==200
    old=s.PATHS_FILE.read_bytes();before=set(s.DATA.iterdir());replace=Path.replace
    def interrupt(self,target):
        if target==s.PATHS_FILE:raise OSError('simulated interrupted rename')
        return replace(self,target)
    monkeypatch.setattr(Path,'replace',interrupt)
    assert c.put(API+'/settings/paths',json=payload).status_code==503
    assert s.PATHS_FILE.read_bytes()==old
    assert set(s.DATA.iterdir())==before


def test_scan_history_does_not_follow_stale_links(installation):
    c,_,root,_=installation;s=server();sentinel=root/'unrelated.txt';sentinel.write_bytes(b'unchanged')
    for target in (s.CATALOG_SCAN_INFO,s.WORKSHOP_SCAN_HISTORY):
        try:target.with_suffix('.tmp').symlink_to(sentinel)
        except OSError:pytest.skip('Symlinks unavailable')
    assert c.post(API+'/catalog/rescan').status_code==200
    assert c.get(API+'/workshop/mods?force=true').status_code==200
    assert sentinel.read_bytes()==b'unchanged'
    for target in (s.CATALOG_SCAN_INFO,s.WORKSHOP_SCAN_HISTORY):
        assert target.is_file() and not target.is_symlink()
        assert isinstance(json.loads(target.read_text()),dict)


def test_browser_reports_damaged_catalog_on_default_workspace():
    import shutil
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js,HTML
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page();page.set_default_timeout(5000);errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.evaluate('''()=>{const base=window.fetch;window.fetch=async(url,opts={})=>String(url)==='api/catalog'?{ok:true,json:async()=>({people:[],roles:[],models:[],meta:{damaged_records:4}})}:base(url,opts)}''')
        page.set_content(HTML,wait_until='domcontentloaded')
        page.wait_for_function("!$('catalogRecoveryWarning').hidden")
        assert '4 damaged catalog' in page.locator('#catalogRecoveryWarning').text_content()
        page.evaluate("catalog.meta.damaged_records=0;render()")
        assert page.locator('#catalogRecoveryWarning').is_hidden() and not errors,errors
        b.close()

"""Passive local legal documents and distribution integrity."""
import importlib.util
from pathlib import Path
import zipfile
from test_native_plugin import installation
from test_dev55_browser import page
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_privacy_check',ROOT/'check_release_privacy.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)

def test_local_documents(installation,monkeypatch,tmp_path):
    c,_,_,_=installation
    for url,name in [('license','LICENSE'),('notice','NOTICE.md')]:
        r=c.get('/casting-studio/api/legal/'+url)
        assert r.status_code==200 and r.content==(ROOT/name).read_bytes()
        assert r.headers['content-type'].startswith('text/plain')
        assert r.headers['x-content-type-options']=='nosniff'
    for url in ['plugin.py','%2e%2e%2fplugin.py','unknown','LICENSE']:
        assert c.get('/casting-studio/api/legal/'+url).status_code==404
    import sys
    server=sys.modules['cb_under_test.app.server']
    empty=tmp_path/'fake'/'app';empty.mkdir(parents=True)
    monkeypatch.setattr(server,'ROOT',empty)
    assert c.get('/casting-studio/api/legal/license').status_code==404

def test_about_links(page):
    tab,errors=page
    tab.evaluate("$('aboutModal').classList.add('open')")
    dialog=tab.locator('#aboutModal')
    for name,url in [('License','api/legal/license'),('Notices','api/legal/notice')]:
        link=dialog.get_by_role('link',name=name,exact=True)
        assert link.is_visible() and link.get_attribute('href')==url
        assert link.get_attribute('rel')=='noopener noreferrer'
    tab.keyboard.press('Escape')
    assert not dialog.is_visible() and not errors

def test_archive_legal_gate(tmp_path):
    for source in [True,False]:
        archive=tmp_path/('source.zip' if source else 'install.zip')
        required=guard.FILES|guard.ICONS|(guard.GITHUB_FILES if source else set())
        def write(omitted=None,altered=None):
            with zipfile.ZipFile(archive,'w') as z:
                for name in sorted(required):
                    if name==omitted:continue
                    info=zipfile.ZipInfo(name if source else guard.ROOT+'/'+name,(2020,1,1,0,0,0))
                    info.create_system=3;info.external_attr=0o100644<<16
                    z.writestr(info,b'tampered' if name==altered else (ROOT/name).read_bytes())
            return guard.audit(archive)[0]
        assert write()==[]
        for name in ['LICENSE','NOTICE.md','CONTRIBUTING.md']:
            assert 'Missing release file: '+name in write(omitted=name)
        assert 'License file changed; verify terms' in write(altered='LICENSE')
        assert 'Required copyright notice missing or changed' in write(altered='NOTICE.md')

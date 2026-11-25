"""Release identity and clean installation are isolated from the beta."""
import importlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from io import BytesIO
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_native_plugin import installation

ROOT=Path(__file__).resolve().parents[1]

def test_release_identity_and_icon(installation):
    c,p,_,_=installation
    meta=json.loads((ROOT/'plugin_info.json').read_text())
    assert meta['name']==p.name=='Casting Studio for WanGP'
    assert meta['version']==p.version
    assert meta['app_url']==p.web_apps[0][0]=='/casting-studio'
    assert meta['app_tab']==p.tabs[0]['tab_id']=='casting_studio'
    assert p.tabs[0]['label']=='Casting Studio'
    svg=ET.fromstring(p.tabs[0]['icon'])
    assert svg.attrib['viewBox']=='0 0 64 64'
    assert len(svg.findall('{http://www.w3.org/2000/svg}path'))==3
    html=c.get('/casting-studio/').text
    assert '<title>Casting Studio for WanGP</title>' in html
    assert 'v'+p.version in html and 'Discover. Cast. Create.' in html
    assert 'casting-studio:generator:session:v1' in html
    assert 'casting-studio:global-loras:v1' in html
    assert 'casting-studio:monitor:v2' in html
    assert 'refmod-casting-board:' not in html
    r=c.get('/casting-studio/api/ui/icons/casting-logo')
    assert r.status_code==200 and r.headers['content-type']=='image/png'
    with Image.open(BytesIO(r.content)) as im:
        assert im.size==(256,256) and not im.info and not im.getexif()
    assert r.content!=(ROOT/'app/icons/workshop.png').read_bytes()
    status=c.get('/casting-studio/api/integration/status').json()
    assert status['casting_studio']==p.version


def test_fresh_namespace_leaves_beta_and_models_untouched(installation,monkeypatch):
    _,p,root,_=installation
    legacy=root/'data'/'refmod-casting-board'
    legacy.mkdir(parents=True)
    (legacy/'casting.sqlite3').write_bytes(b'unchanged beta sentinel')
    (legacy/'local_paths.json').write_text('{}')
    legacy_snapshot={x:x.read_bytes() for x in legacy.iterdir()}
    models={x:x.read_bytes() for x in (root/'refmods').rglob('*.safetensors')}
    monkeypatch.delenv('CASTING_STUDIO_DATA_DIR',raising=False)
    # An obsolete beta override or generic DATA_DIR must not redirect RC1.
    monkeypatch.setenv('CASTING_BOARD_DATA_DIR',str(legacy))
    monkeypatch.setenv('DATA_DIR',str(legacy))
    srv=importlib.import_module('cb_under_test.app.server')
    # Real process imports server after setting the new default. Reload emulates it.
    new=root/'data'/'casting-studio'
    # Fixture has already imported server. Reload at the point the real host would import it.
    def init():
        importlib.reload(srv)
        srv.startup()
    monkeypatch.setattr(srv,'startup',init)
    app=p.create_web_app()
    host=FastAPI();host.mount('/casting-studio',app);c=TestClient(host)
    assert srv.DATA==new and (new/'casting.sqlite3').is_file()
    assert c.get('/casting-studio/api/personal').json()==[]
    assert c.get('/casting-studio/api/choices').json()==[]
    assert c.get('/casting-studio/api/productions').json()==[]
    assert any(x['path']=='Ada_Test_H3.safetensors' for x in c.get('/casting-studio/api/catalog').json()['models'])
    assert {x:x.read_bytes() for x in legacy.iterdir()}==legacy_snapshot
    assert {x:x.read_bytes() for x in models}==models

"""Empty distribution, external data and resumable reference collection."""
import importlib,io,json,os,time
import pytest
from PIL import Image
from test_native_plugin import installation
API='/casting-studio/api'

def test_empty_catalog_and_external_state(installation):
    c,p,root,_=installation;srv=importlib.import_module('cb_under_test.app.server')
    seed=json.loads((srv.ROOT/'casting_db.json').read_text())
    assert not any(seed[k] for k in ('people','roles','productions','creditSuggestions'))
    assert not any((srv.KNOWN_IDENTITIES,srv.CURATED_ROLE_DATA,srv.CURATED_CHARACTER_TRAITS,srv.GAME_WORLD_DEFAULTS))
    for file in (root/'refmods').rglob('*.safetensors'):file.unlink()
    srv.scan(force=True)
    assert not c.get(API+'/catalog').json()['people']
    assert not c.get(API+'/productions?q=example').json()
    assert not c.get(API+'/personal').json() and not c.get(API+'/choices').json()
    assert not c.get(API+'/workshop/sources').json()['sources']
    assert srv.DATA==root/'user_data' and not srv.DATA.is_relative_to(srv.ROOT.parent)
    with pytest.raises(RuntimeError):srv.external_data_path(srv.ROOT/'private-data')
    link=root/'bad-data'
    try:link.symlink_to(srv.ROOT,target_is_directory=True)
    except OSError:pass
    else:
        with pytest.raises(RuntimeError):srv.external_data_path(link/'private-data')
    assert c.post(API+'/productions/cast',json={'actress':'Example Anchor','production':'Example News','character':'Anchor','year':2025}).status_code==200
    assert c.post(API+'/personal',json={'name':'Example Private','consent':False}).status_code==200
    srv.startup()
    with srv.connect() as db:
        assert db.execute('SELECT count(*) FROM production_cast').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM personal_profiles').fetchone()[0]==1
    assert srv.list_productions('Example News')[0]['name']=='Example News'

@pytest.fixture
def photo_setup(installation,monkeypatch):
    c,p,root,_=installation;srv=importlib.import_module('cb_under_test.app.server')
    monkeypatch.setattr(srv,'analyze_reference_image',lambda im:{'width':im.width,'height':im.height,'sharpness':100,'face_count':1,'fingerprint':'0123456789abcdef','hard_reasons':[],'review_reasons':[]})
    raw=io.BytesIO();Image.new('RGB',(800,800),'gray').save(raw,format='PNG')
    return c,srv,root,raw.getvalue()

def test_resume_and_cross_collection_upload(photo_setup):
    c,srv,root,raw=photo_setup
    def upload(prod):
        r=c.post(API+'/reference-images/upload',params={'person':'Example Anchor','production':prod},headers={'Content-Type':'image/png'},content=raw)
        assert r.status_code==200,r.text
        return r.json()
    first=upload('Example News');second=upload('Example News')
    assert second['duplicate'] and second['id']==first['id']
    other=upload('Different Program');assert other['id']!=first['id']
    assert upload('example news (2025)')['id']==first['id']
    assert len(c.get(API+'/workshop/photos',params={'person':'Example Anchor','production':'Example News'}).json()['photos'])==1
    assert len(c.get(API+'/workshop/sources').json()['sources'])==2
    row=c.get(API+'/reference-images',params={'person':'Example Anchor','production':'Example News'}).json()[0]
    (srv.REFERENCE_DIR/row['filename']).unlink()
    assert c.get(API+'/reference-images',params={'person':'Example Anchor','production':'Example News'}).json()[0]['quality_status']=='missing'
    restored=upload('Example News');assert restored['id']==first['id'] and not restored.get('duplicate')
    assert len(c.get(API+'/workshop/photos',params={'person':'Example Anchor','production':'Example News'}).json()['photos'])==1
    assert c.delete(API+'/reference-images/'+first['id']).status_code==200
    assert c.get(API+'/reference-images/file/'+other['id']).status_code==200

def test_reuse_url_without_network(photo_setup,monkeypatch):
    c,srv,root,raw=photo_setup
    import httpx
    original=httpx.Client;calls=[]
    def handler(req):
        calls.append(str(req.url));return httpx.Response(200 if len(calls)==1 else 403,headers={'Content-Type':'image/png'},content=raw)
    monkeypatch.setattr(srv,'validate_public_url',lambda url:'93.184.216.34')
    monkeypatch.setattr(srv.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    body={'person':'Example Anchor','production':'Example News','image_url':'https://example.org/portrait.png'}
    first=c.post(API+'/reference-images',json=body);assert first.status_code==200,first.text
    def offline(url):raise RuntimeError('Network unavailable')
    monkeypatch.setattr(srv,'validate_public_url',offline)
    second=c.post(API+'/reference-images',json={**body,'production':'Different Program'});assert second.status_code==200,second.text
    assert second.json()['reused_local'] and second.json()['id']!=first.json()['id'] and len(calls)==1
    assert c.post(API+'/reference-images',json=body).json()['duplicate']

def test_cleanup_only_recognized_old_temps(photo_setup):
    c,srv,root,raw=photo_setup;old=time.time()-90000
    files=[srv.DATA/'local_paths.json.tmp',srv.REFERENCE_DIR/('a'*24+'.jpg.tmp'),srv.PHOTO_DIR/('b'*64+'.jpg.'+'c'*32+'.tmp')]
    keep=[srv.REFERENCE_DIR/('d'*24+'.jpg'),srv.REFERENCE_DIR/'other.tmp',srv.PHOTO_DIR/('e'*64+'.jpg.tmp')]
    for f in files+keep:f.write_bytes(b'test')
    for f in files+keep[:2]:os.utime(f,(old,old))
    target=root/'private-file';target.write_bytes(b'keep')
    try:(srv.REFERENCE_DIR/('f'*24+'.jpg.tmp')).symlink_to(target)
    except OSError:pass
    assert c.get(API+'/settings/temporary-files').json()['count']==3
    assert all(f.exists() for f in files)
    assert c.post(API+'/settings/temporary-files/cleanup').json()['removed']==3
    assert not any(f.exists() for f in files) and all(f.exists() for f in keep) and target.read_bytes()==b'keep'
    assert c.post(API+'/settings/temporary-files/cleanup').json()['removed']==0

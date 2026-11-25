"""dev5.3 tests. All writes stay inside pytest's temporary model/data trees."""
import io
import json
from pathlib import Path
from PIL import Image
import pytest
from test_native_plugin import installation

API='/casting-studio/api'


def test_branding_and_changelog(installation):
    c,*_=installation
    page=c.get('/casting-studio/').text
    assert 'Casting Studio for WanGP' in page
    assert 'generatorResolutionCategory' in page
    assert 'photoLightbox' in page
    assert 'workshopModSearch' in page
    for asset in ('casting-logo','workshop'):
        resp=c.get(API+'/ui/icons/'+asset)
        assert resp.status_code==200
        assert resp.headers['content-type'].startswith('image/png')
    assert 'v6.9.0-dev5.3' in c.get(API+'/changelog').text


def test_local_paths_are_bounded_and_persistent(installation):
    c,plugin,root,_=installation
    d=c.get(API+'/settings/paths').json()
    assert set(d['paths'])=={'public_h3','public_flux','personal_h3','personal_flux'}
    assert c.put(API+'/settings/paths',json={'refmod_root':str(root)}).status_code==422
    assert not (root/'user_data'/'local_paths.json').exists()
    assert c.put(API+'/settings/paths',json={'refmod_root':d['refmod_root']}).status_code==200
    assert (root/'user_data'/'local_paths.json').exists()
    assert c.get(API+'/settings/paths').json()==d
    assert all('Private_Test' not in m['filename'] for m in c.get(API+'/catalog').json()['models'])

def test_workshop_filters_truncated_or_invalid_safetensors(installation):
    c,plugin,root,_=installation
    public=root/'refmods'/'minimax_h3'/'celebs'
    (public/'zero.safetensors').write_bytes(b'')
    (public/'broken.safetensors').write_bytes(b'no header')
    (public/'should-ignore.txt').write_text('hello')
    header={'__metadata__':{'refmod_meta':json.dumps({'name':'valid','kind':'identity','mode':'encode'})}}
    raw=json.dumps(header).encode()
    (public/'valid.safetensors').write_bytes(len(raw).to_bytes(8,'little')+raw+b'\x00'*32)
    r=c.get(API+'/workshop/mods')
    assert r.status_code==200,r.text
    v=r.json();names=[x['filename'] for x in v['mods']]
    assert names==['valid.safetensors']
    assert {'Ada_Test_H3.safetensors','broken.safetensors','zero.safetensors'}<={x['filename'] for x in v['skipped']}


def test_local_picture_upload(installation):
    c,plugin,root,_=installation
    photo=Image.new('RGB',(150,200),'#aabbee')
    blob=io.BytesIO();photo.save(blob,format='PNG')
    r=c.post(API+'/images/upload?key=actress%7Cada',content=blob.getvalue(),headers={'Content-Type':'image/png'})
    assert r.status_code==200,r.text
    url=r.json()['url']
    assert url.startswith('api/photos/')
    assert c.get('/casting-studio/'+url).status_code==200
    assert c.get(API+'/images/saved').json()['actress|ada']==url
    bad=c.post(API+'/images/upload?key=actress%7Cada',content=b'nonsense',headers={'Content-Type':'application/octet-stream'})
    assert bad.status_code==415


def test_reference_upload_rejects_low_quality(installation):
    c,plugin,root,_=installation
    # Low resolution image is technically unsuitable regardless of identity.
    img=Image.new('RGB',(100,100),'white');tmp=io.BytesIO();img.save(tmp,format='PNG')
    r=c.post(API+'/reference-images/upload?person=Test%20Actor',content=tmp.getvalue(),headers={'Content-Type':'image/png'})
    assert r.status_code==422,r.text
    assert not list((root/'user_data'/'reference_images').glob('*.jpg'))

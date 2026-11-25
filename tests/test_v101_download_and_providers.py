"""Network boundary tests use synthetic DNS and HTTP responses, never live providers."""
import socket
from importlib import import_module
import httpx
import pytest
from test_native_plugin import installation
API='/casting-studio/api'

@pytest.mark.parametrize('addresses',[['127.'+'0.0.1'],['93.184.216.34','127.'+'0.0.1'],['::1'],['::ffff:127.0.0.1']])
def test_private_or_mixed_dns_rejected(installation,monkeypatch,addresses):
    s=import_module('cb_under_test.app.server')
    monkeypatch.setattr(s.socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443)) for ip in addresses])
    with pytest.raises(ValueError):s.validate_public_url('https://example.com/photo.png')

@pytest.mark.parametrize('address',['93.184.216.34','2606:4700:4700::1111'])
def test_pinned_connection_keeps_tls_and_host(installation,monkeypatch,address):
    s=import_module('cb_under_test.app.server');calls=[]
    monkeypatch.setattr(s.socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443))])
    url='https://example.com/photo.png?q=1'
    def handler(request):
        calls.append(request)
        assert request.url.host==address
        assert request.headers['host']=='example.com'
        assert request.extensions['sni_hostname']=='example.com'
        assert request.headers['accept-encoding']=='identity'
        assert request.url.path=='/photo.png' and request.url.query==b'q=1'
        return httpx.Response(200,content=b'test')
    with httpx.Client(transport=httpx.MockTransport(handler),trust_env=False,follow_redirects=False) as client:
        with s.pinned_image_request(client,url,s.validate_public_url(url)) as response:assert response.read()==b'test'
    assert len(calls)==1

@pytest.mark.parametrize('installation',[False],indirect=True)
def test_saved_photo_and_reference_export_require_ack(installation):
    c,*_=installation
    assert c.put(API+'/images/saved',json={'key':'actress|example','url':'https://example.com/image.png'}).status_code==403
    assert c.get(API+'/reference-images/export',params={'person':'Synthetic Person'}).status_code==403
    assert c.post(API+'/photos/archive-existing').status_code==403

def test_exact_private_names_in_other_search_fields_blocked(installation):
    c,*_=installation
    name='Synthetic Private'
    assert c.post(API+'/personal',json={'name':name,'consent':False}).status_code==200
    for path,params in [('/images/search',{'actress':'Synthetic Public','character':name}),('/images/search',{'actress':'Synthetic Public','production':name}),('/productions/lookup',{'q':name}),('/productions/artwork',{'name':name}),('/productions/cast-suggestions',{'production':name})]:
        assert c.get(API+path,params=params).status_code==403,path
    assert c.post(API+'/television/research',json={'name':'Synthetic Public','station':name}).status_code==403

def test_private_public_artwork_mapping_and_writes_are_blocked(installation):
    c,*_=installation;s=import_module('cb_under_test.app.server')
    key='actress|syntheticprivate'
    with s.connect() as db:db.execute('INSERT INTO images VALUES (?,?)',(key,'https://example.com/photo.png'))
    assert c.post(API+'/personal',json={'name':'Synthetic Private','consent':False}).status_code==200
    assert key not in c.get(API+'/images/cached').json()
    assert c.put(API+'/images/saved',json={'key':key,'url':'https://example.com/photo.png'}).status_code==403
    assert c.post(API+'/images/upload',params={'key':key},content=b'fake',headers={'content-type':'image/png'}).status_code==403
    with s.connect() as db:assert db.execute('SELECT url FROM images WHERE key=?',(key,)).fetchone() is not None

def test_cast_source_persists_after_bulk_save(installation):
    c,*_=installation
    entry={'production':'Synthetic Production','actress':'Synthetic Performer','character':'Synthetic Character','source':'TVMaze','source_url':'https://www.tvmaze.com/shows/12345'}
    assert c.post(API+'/productions/cast/bulk',json={'production':entry['production'],'members':[entry]}).status_code==200
    item=c.get(API+'/productions/cast',params={'production':entry['production']}).json()['cast'][0]
    assert item['source']==entry['source'] and item['source_url']==entry['source_url']


def test_archive_existing_excludes_private_keys(installation,monkeypatch):
    c,*_=installation;s=import_module('cb_under_test.app.server')
    assert c.post(API+'/personal',json={'name':'Synthetic Private','consent':False}).status_code==200
    with s.connect() as db:
        db.execute('INSERT INTO images VALUES (?,?)',('actress|syntheticprivate','https://example.com/private.png'))
        db.execute('INSERT INTO images VALUES (?,?)',('actress|syntheticpublic','https://example.com/public.png'))
    seen=[];monkeypatch.setattr(s,'download_image',seen.append)
    s.prefetch_stop.clear();s.archive_existing_worker()
    assert seen==['https://example.com/public.png']

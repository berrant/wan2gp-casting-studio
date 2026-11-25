"""Malformed API input storm: no invalid request may create a queue job."""
from concurrent.futures import ThreadPoolExecutor
import random
from test_native_plugin import installation
from test_rc2_jackhammer import server,API


def test_malformed_request_storm(installation):
    c,p,*_=installation;s=server()
    rng=random.Random(821)
    endpoints=[('POST','/personal'),('PUT','/choices'),('POST','/generator/preview'),('POST','/generator/batch/preview'),('POST','/workshop/create'),('PUT','/settings/paths')]
    payloads=[b'null',b'[]',b'"invalid"',b'{}',b'{',b'42',b'true',b'{"name":[],"choice_key":[],"refmod_root":[]}',b'{"name":"", "choice_key":"", "refmod_root":false}']
    work=[(*rng.choice(endpoints),rng.choice(payloads)) for _ in range(120)]
    def send(item):
        method,url,body=item
        return c.request(method,API+url,content=body,headers={'Content-Type':'application/json'}).status_code
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(send,work))
    assert all(400<=r<500 for r in results),results
    assert not p.queue_bridge._pending and c.get(API+'/choices').json()==[] and c.get(API+'/personal').json()==[]
    with s.connect() as db:assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)


def test_nonfinite_numeric_input_is_controlled(installation):
    c,p,*_=installation
    for value in ('NaN','Infinity','-Infinity','1e999'):
        raw='{"choice_key":"synthetic","strength":'+value+'}'
        r=c.post(API+'/generator/preview',content=raw,headers={'Content-Type':'application/json'})
        assert 400<=r.status_code<500
    assert not p.queue_bridge._pending


def test_profile_markers_are_not_preseeded(installation):
    c,_,_,_=installation;s=server()
    assert s.ADULT_SEED==set()
    assert c.get(API+'/profiles/markers').json()=={}
    assert c.put(API+'/profiles/markers',json={'name':'Ada Test','adult':True}).status_code==200
    assert c.get(API+'/profiles/markers').json()=={'Ada Test':True}
    assert c.put(API+'/profiles/markers',json={'name':'Ada Test','adult':False}).status_code==200
    assert c.get(API+'/profiles/markers').json()=={}

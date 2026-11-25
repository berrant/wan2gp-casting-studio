"""Four independent clean-round probes, using deterministic fixtures and seeds."""
import io
import random
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS
import httpx
from PIL import Image
from test_native_plugin import installation
from test_rc2_jackhammer import server, API
from test_beta5217_chaos import browser_page
from test_rc12_nuclear import photo_transport


def test_round_network_response_boundaries(installation,monkeypatch):
    s=server();cases={};calls=[]
    class Large(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(9):yield b'x'*(1024*1024)
    cases.update({
        '/redirect':lambda:httpx.Response(302,headers={'Location':'https://example.com/target'}),
        '/wrong-mime':lambda:httpx.Response(200,headers={'Content-Type':'text/html'},content=b'<html>'),
        '/bad-length':lambda:httpx.Response(200,headers={'Content-Type':'image/png','Content-Length':'invalid'},content=b'broken'),
        '/large-length':lambda:httpx.Response(200,headers={'Content-Type':'image/png','Content-Length':str(9*1024*1024)},content=b'broken'),
        '/large-stream':lambda:httpx.Response(200,headers={'Content-Type':'image/png'},stream=Large()),
        '/broken-image':lambda:httpx.Response(200,headers={'Content-Type':'image/png'},content=b'not an image'),
    })
    def handler(req):calls.append(req.url.path);return cases[req.url.path]()
    photo_transport(s,monkeypatch,handler)
    for path in cases:assert s.download_image('https://example.com'+path)==''
    assert calls==list(cases) and not list(s.PHOTO_DIR.iterdir())
    with s.connect() as db:assert db.execute('SELECT count(*) FROM photo_files').fetchone()==(0,)


def test_round_extended_concurrent_terminal_history(installation):
    _,p,*_=installation;b=p.queue_bridge
    total=2048;keys=[f'test-{i}' for i in range(total)];rng=random.Random(12042);rng.shuffle(keys)
    b._jobs.update({key:{'id':key,'state':'running','files':[]} for key in keys})
    b._jobs['active']={'id':'active','state':'running'}
    def complete(key):
        b._change(key,state='completed',progress=100)
        b._change(key,state='running',progress=0) # late callback must not revive it
        state=b.status(key)
        assert state is None or (state['state']=='completed' and state['progress']==100)
        assert b.status('active')['state']=='running'
    with ThreadPoolExecutor(max_workers=12) as pool:list(pool.map(complete,keys))
    assert len(b._jobs)==101 and len(b._previews)<=8
    assert all(x['state']=='completed' for k,x in b._jobs.items() if k!='active')
    b._change('active',state='completed');assert len(b._jobs)==100 and b.status('active')['state']=='completed'


def test_round_database_contention_and_recovery(installation,monkeypatch):
    import sqlite3
    s=server();photo_transport(s,monkeypatch);url='https://example.com/contention.png'
    original=s.connect
    # A real competing SQLite write lock; shorten only the fixture's busy timeout.
    blocker=original();blocker.execute('BEGIN IMMEDIATE')
    def short_connect():
        db=original();db.execute('PRAGMA busy_timeout=20');return db
    monkeypatch.setattr(s,'connect',short_connect)
    try:
        assert s.download_image(url)==''
        assert not list(s.PHOTO_DIR.iterdir())
    finally:
        blocker.rollback();blocker.close()
    result=s.download_image(url);assert result.startswith('api/photos/')
    with original() as db:assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)
    assert len(list(s.PHOTO_DIR.iterdir()))==1


def test_round_browser_seeded_resize_and_navigation(browser_page):
    page,errors=browser_page;rng=random.Random(12043)
    tabs=['productions','personal','performers','models','adult','television','workshop']
    for i in range(180):
        if i%15==0:page.set_viewport_size({'width':rng.choice([390,768,1024,1440,1920]),'height':rng.choice([600,800,950])})
        page.evaluate('(t)=>showTab(t)',rng.choice(tabs))
        page.evaluate('(v)=>{$("monitorToggle").open=v}',bool(rng.getrandbits(1)))
        assert page.evaluate("$('castingSelectionsPanel').hidden===(activeTab==='workshop')")
        assert page.locator('#gpuTemperature').is_visible()
    assert page.evaluate('choices.length')==2
    assert not errors,errors

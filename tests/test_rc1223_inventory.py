"""Cold inventory requests share one scan; invalidation survives a concurrent scan."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import importlib
from test_native_plugin import installation


def test_concurrent_cold_catalog_requests_share_scan(installation, monkeypatch):
    s=importlib.import_module('cb_under_test.app.server')
    entered=Event(); second_scan=Event(); resume=Event(); second_started=Event(); calls=[]
    original=s.picture_conversion_source
    def probe(path):
        calls.append(path)
        if len(calls)==1:
            entered.set()
            assert resume.wait(5)
        else:
            second_scan.set()
        return original(path)
    monkeypatch.setattr(s,'picture_conversion_source',probe)
    s.catalog_cache['until']=0
    def second():
        second_started.set()
        return s.scan()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(s.scan)
        try:
            assert entered.wait(5)
            b=pool.submit(second)
            assert second_started.wait(5)
            assert not second_scan.wait(0.5), 'second request started a duplicate scan'
            assert s.catalog_scan_status()['running'] is True
        finally:
            resume.set()
        assert a.result(timeout=5)==b.result(timeout=5)
    assert len(calls)==1
    assert s.catalog_scan_status()['running'] is False
    s.scan(force=True)
    assert len(calls)==2  # explicit rescan still works


def test_private_registration_during_scan_invalidates_cache(installation, monkeypatch):
    c,*_=installation
    s=importlib.import_module('cb_under_test.app.server')
    entered=Event(); resume=Event()
    original=s.picture_conversion_source
    def probe(path):
        if path.name=="Ada_Test_H3.safetensors":
            entered.set()
            assert resume.wait(5)
        return original(path)
    monkeypatch.setattr(s,'picture_conversion_source',probe)
    s.catalog_cache['until']=0
    with ThreadPoolExecutor(max_workers=1) as pool:
        f=pool.submit(s.scan)
        try:
            assert entered.wait(5)
            r=c.post('/casting-studio/api/personal',json={'name':'Ada Test','consent':False})
            assert r.status_code==200,r.text
        finally:
            resume.set()
        assert not f.result(timeout=5), 'scan exposed a newly private identity'
    assert s.catalog_cache['until']==0, 'scan swallowed concurrent invalidation'
    assert not s.scan()


def test_scan_failure_releases_owner_and_cached_reads_remain_available(installation, monkeypatch):
    import pytest
    s=importlib.import_module('cb_under_test.app.server')
    baseline=s.scan()
    original=s.picture_conversion_source
    entered=Event(); resume=Event()
    def fail(path):
        entered.set()
        assert resume.wait(5)
        raise OSError('synthetic inventory read failure')
    monkeypatch.setattr(s,'picture_conversion_source',fail)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(s.scan,True)
        try:
            assert entered.wait(5)
            assert pool.submit(s.scan).result(timeout=2)==baseline
            assert s.catalog_scan_status()['running'] is True
        finally:
            resume.set()
        with pytest.raises(OSError,match='synthetic'):a.result(timeout=5)
    assert s.catalog_scan_status()['running'] is False
    monkeypatch.setattr(s,'picture_conversion_source',original)
    assert s.scan(force=True)==baseline

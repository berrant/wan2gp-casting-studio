"""GPU temperature telemetry is independent of CUDA and active jobs."""
import importlib,shutil,subprocess
from types import SimpleNamespace
import pytest
from test_native_plugin import installation
API='/casting-studio/api/telemetry/gpu-temperature'

def test_sensor_cache_bands_and_invalid_rows(installation,monkeypatch):
    c,*_=installation;srv=importlib.import_module('cb_under_test.app.server');calls=[]
    monkeypatch.setattr(srv.shutil,'which',lambda name:'nvidia-smi')
    def run(args,**kw):
        calls.append((args,kw));return SimpleNamespace(stdout='0, 74\n1, 75\n2, 84\n3, 85\n4, N/A\n5, -1\n6, 999\nmalformed\n')
    monkeypatch.setattr(srv.subprocess,'run',run)
    result=c.get(API).json();assert result['available']
    assert [(g['celsius'],g['band']) for g in result['gpus']]==[(74,'normal'),(75,'warm'),(84,'warm'),(85,'hot')]
    assert c.get(API).json()==result and len(calls)==1
    assert calls[0][1]['timeout']==2 and calls[0][1]['check']
    assert calls[0][0][1]=='--query-gpu=index,temperature.gpu'
    srv._gpu_temp_cache['until']=0
    def timeout(*a,**k):raise subprocess.TimeoutExpired(a[0],2)
    monkeypatch.setattr(srv.subprocess,'run',timeout)
    assert c.get(API).json()=={'gpus':[],'available':False}

def test_missing_sensor(installation,monkeypatch):
    c,*_=installation;srv=importlib.import_module('cb_under_test.app.server')
    monkeypatch.setattr(srv.shutil,'which',lambda n:None)
    assert c.get(API).json()=={'gpus':[],'available':False}

def test_gpu_numbers_visible_collapsed_and_expanded():
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js,HTML
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page(viewport={'width':800,'height':700});page.evaluate(setup_js);page.set_content(HTML,wait_until='domcontentloaded')
        page.evaluate("renderGpuTemperature({gpus:[{index:0,celsius:74},{index:1,celsius:80},{index:2,celsius:85}]})")
        for opened in [False,True,False]:
            page.evaluate('(opened)=>document.getElementById(\'monitorToggle\').open=opened',opened)
            assert page.locator('#gpuTemperature').is_visible()
            assert page.locator('#gpuTemperatureValues .normal').inner_text()=='#0 74°C'
            assert page.locator('#gpuTemperatureValues .warm').inner_text()=='#1 80°C'
            assert page.locator('#gpuTemperatureValues .hot').inner_text()=='#2 85°C'
        page.evaluate('renderGpuTemperature(null)');assert page.locator('#gpuTemperatureValues').inner_text()=='N/A'
        b.close()

from pathlib import Path
from types import SimpleNamespace
import shutil
import pytest
from test_native_plugin import installation
API='/casting-studio/api'
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

def test_preview_interest_and_burst_throttle(installation,monkeypatch):
    import importlib
    from PIL import Image
    c,p,_,_=installation; b=p.queue_bridge
    module=importlib.import_module(b.__class__.__module__);clock=[100.0]
    monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    jid='performance-job'; b._jobs[jid]={'id':jid,'state':'running','batch':True,'total_tasks':2,'task_index':1}
    frame=Image.new('RGB',(640,360),'blue');update=SimpleNamespace(image=frame,task_index=1)
    c.get(API+'/generator/jobs/'+jid+'?live_preview=false')
    for _ in range(100):b._store_preview(jid,update)
    assert b.preview(jid) is None
    c.get(API+'/generator/jobs/'+jid+'?live_preview=true')
    for _ in range(100):b._store_preview(jid,update)
    assert b.status(jid)['preview_rev']==1
    clock[0]+=2;b._store_preview(jid,update);assert b.status(jid)['preview_rev']==2
    b._advance_batch_task(jid,2,2);b._store_preview(jid,SimpleNamespace(image=frame,task_index=2))
    assert b.status(jid)['preview_rev']==1 and b.preview(jid,1) is None
    c.get(API+'/generator/jobs/'+jid+'?live_preview=false');assert b.preview(jid) is None
    c.get(API+'/generator/jobs/'+jid+'?live_preview=true');clock[0]+=11
    b._store_preview(jid,SimpleNamespace(image=frame,task_index=2));assert b.preview(jid) is None

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium unavailable')
def test_large_catalog_cached_index_and_collapsed_monitor():
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    from test_dev57_status_lite_browser import HOST
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page(viewport={'width':1400,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content('<div id="lite-host"></div><iframe name="casting" style="width:1350px;height:850px" src="about:blank"></iframe>')
        frame=page.frame(name='casting');frame.evaluate(setup_js);frame.set_content(HTML,wait_until='domcontentloaded');frame.wait_for_function('choices.length===2')
        page.locator('#lite-host').evaluate('(el,html)=>el.innerHTML=html',HOST)
        metrics=frame.evaluate('''() => {
          catalog={models:Array.from({length:1500},(_,i)=>({name:'Person '+String(i).padStart(4,'0'),family:'minimax_h3',path:'Person_'+i+'.safetensors'})),people:[],roles:Array.from({length:20000},(_,i)=>({actress:'Person '+String(i%1500).padStart(4,'0'),character:'Role '+i,production:'Show '+i}))};
          choices=[];const t=performance.now();showTab('performers');const cold=performance.now()-t;
          const rows=personRows(),first=$('list').firstElementChild;const t2=performance.now();
          for(let i=0;i<5;i++){showTab('productions');showTab('performers')}
          const warm=(performance.now()-t2)/5;
          const same=rows===personRows()&&first===$('list').firstElementChild;
          const count=$('list').children.length;const all=personRows().length;
          $('monitorToggle').open=false;syncStatusLiteTelemetry();const stage=$('slmStages').firstChild;
          for(let i=0;i<100;i++){syncStatusLiteTelemetry();renderGenerationMonitor({id:'perfjob',state:'running',current_step:i,preview_rev:i+1,preview_kind:'image'})}
          const hiddenNoMedia=!$('monitorLiveImage').hasAttribute('src')&&!$('monitorLiveVideo').hasAttribute('src');
          const stableStage=stage===$('slmStages').firstChild;
          const request=monitorJobURL('perfjob');$('monitorToggle').open=true;
          renderGenerationMonitor({id:'perfjob',state:'running',preview_rev:101,preview_kind:'image'});
          const expandedMedia=$('monitorLiveImage').hasAttribute('src');
          const expandedRequest=monitorJobURL('perfjob');$('monitorToggle').open=false;
          catalog={models:[{name:'New Person',family:'minimax_h3',path:'new.safetensors'}],people:[],roles:[]};
          const updated=personRows().length===1&&!!modFor('New Person');
          return {cold,warm,same,count,all,hiddenNoMedia,stableStage,request,expandedMedia,expandedRequest,updated};
        }''')
        print('synthetic catalog timings:',metrics)
        assert metrics['same'] and metrics['count']==20 and metrics['all']==1500 and metrics['updated']
        assert metrics['hiddenNoMedia'] and metrics['stableStage'] and metrics['expandedMedia']
        assert 'live_preview=false' in metrics['request'] and 'live_preview=true' in metrics['expandedRequest']
        assert not errors,errors;b.close()

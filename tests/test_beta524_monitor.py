from pathlib import Path
from types import SimpleNamespace
import shutil
import pytest
from test_native_plugin import installation
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()
API='/casting-studio/api'

def test_preview_task_identity_and_late_callbacks(installation):
    from PIL import Image
    client,plugin,_,_=installation
    b=plugin.queue_bridge; jid='preview-task-test'
    b._jobs[jid]={'id':jid,'state':'running','batch':True,'total_tasks':3,'task_index':1}
    def frame(i):return SimpleNamespace(image=Image.new('RGB',(20,20),'blue'),task_index=i)
    b._store_preview(jid,frame(1))
    assert client.get(API+f'/generator/jobs/{jid}/preview?task=1&rev=1').status_code==200
    b._observe_batch_status(jid,'Prompt 2/3 - Encoding')
    assert b.preview(jid) is None
    b._store_preview(jid,frame(1))
    assert b.preview(jid) is None
    b._store_preview(jid,frame(2))
    assert b.status(jid)['preview_rev']==1
    assert client.get(API+f'/generator/jobs/{jid}/preview?task=1&rev=1').status_code==404
    assert client.get(API+f'/generator/jobs/{jid}/preview?task=2&rev=1').status_code==200
    b._change(jid,state='completed');b._store_preview(jid,frame(2))
    assert b.status(jid)['preview_rev']==1
    assert client.get(API+f'/generator/jobs/{jid}/preview?task=2').status_code==404

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium unavailable')
def test_collapsed_telemetry_and_preview_resets():
    from playwright.sync_api import sync_playwright
    from test_dev57_status_lite_browser import HOST
    from test_generator_session_browser import setup_js
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1400,'height':950})
        page.set_content('<div id="lite-host"></div><iframe name="casting" style="width:1350px;height:850px" src="about:blank"></iframe>')
        frame=page.frame(name='casting');frame.evaluate(setup_js)
        frame.set_content(HTML,wait_until='domcontentloaded')
        page.locator('#lite-host').evaluate('(el,html)=>el.innerHTML=html',HOST)
        frame.evaluate('syncStatusLiteTelemetry()')
        assert not frame.locator('#monitorToggle').evaluate('(el)=>el.open')
        assert frame.locator('#slmLive').is_visible()
        assert frame.locator('#slmStages .current').is_visible()
        assert frame.locator('#monitorLiveContainer').is_hidden()
        assert frame.locator('#integrationButton svg.about-icon').count()==1
        assert frame.locator('.selection-actions button').filter(has_text='JSON').count()==0
        assert frame.locator('.selection-actions button').filter(has_text='CSV').count()==0
        frame.evaluate("document.querySelector('#monitorToggle').open=true")
        assert frame.locator('#slmSteps').is_visible()
        result=frame.evaluate('''() => {
          const render=(id,task,rev,state='running')=>renderGenerationMonitor({id,batch:true,task_index:task,preview_task_index:task,preview_rev:rev,preview_kind:'image',state});
          const img=$('monitorLiveImage');render('batch1',1,1);const first=img.dataset.version;const src1=img.getAttribute('src');
          render('batch1',2,1);const second=img.dataset.version;const src2=img.getAttribute('src');
          render('batch1',3,0);const empty=img.style.display==='none'&&!img.hasAttribute('src')&&$('monitorLiveVideo').style.display==='none';
          render('batch1',3,1);render('batch1',3,1,'completed');const terminal=img.style.display==='none'&&!img.hasAttribute('src');
          render('old-job',1,4);trackGeneratorJob('new-job');const queued=img.style.display==='none'&&!img.hasAttribute('src')&&$('monitorProgress').value===0;
          return {first,second,src1,src2,empty,terminal,queued};
        }''')
        assert result['first']!=result['second'] and 'task=1' in result['src1'] and 'task=2' in result['src2']
        assert result['empty'] and result['terminal'] and result['queued']
        result=frame.evaluate('''async () => {const original=window.fetch;let resolve;window.fetch=()=>new Promise(r=>resolve=r);trackGeneratorJob('old');const pending=pollGenerator();trackGeneratorJob('new');resolve({ok:true,json:async()=>({id:'old',state:'running',preview_rev:9,preview_kind:'image'})});await pending;window.fetch=original;return $('monitorTitle').textContent;}''')
        assert 'new' in result and 'old' not in result
        browser.close()

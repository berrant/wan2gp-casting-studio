"""Preview identity follows native media, not editable generator selection."""
from test_native_plugin import reviewed_submit
from pathlib import Path
import shutil
import pytest
from PIL import Image
from types import SimpleNamespace as NS
from test_native_plugin import installation, _mock_fork, _create_public_selection
from test_dev512_image_sets import _image_session, _set_image_template
API='/casting-studio/api'
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

def test_native_batch_metadata_tracks_exact_output(installation):
    c,p,root,_=installation;_mock_fork(root);session=_image_session();b=p.queue_bridge
    b.api_session=session;b.dispatch_mode='gradio';key=_create_public_selection(c);_set_image_template(c,count=2)
    paths=[]
    for i in range(2):
        f=root/f'identity-{i}.png';Image.new('RGB',(120,120),(i,10,100)).save(f);paths.append(str(f))
    def submit(settings,callbacks=None):
        def result():
            for i in (1,2):
                callbacks.on_progress(NS(task_index=i,task_count=2,task_id=f'c{i}',phase='inference',current_step=1,total_steps=8,progress=50,status=f'Prompt {i}/2 - Denoising'))
                state=b.status(jid);meta=state['task_details'];assert meta['person'] and meta['scene']==i and meta['prompt']==settings[i-1]['prompt']
                if i==2:assert state['last_result']['task_details']['scene']==1
                callbacks.on_output({'client_id':f'c{i}','path':paths[i-1]})
                assert b.status(jid)['last_result']['task_details']==meta
            return NS(success=True,generated_files=paths,errors=[],cancelled=False)
        return NS(result=result,cancel=lambda:None,webui_client_ids=['c1','c2'])
    session.submit_manifest=submit
    response=reviewed_submit(c,API+'/generator/batch/submit',json={'task':{'choice_key':key,'model':'h3_image_pruned','model_type':'h3_image_pruned_checkpoint'},'scope':'selection:'+key,'scene_mode':'all'})
    assert response.status_code==200,response.text;jid=response.json()['id'];b.process_pending_in_gradio(session)
    state=b.status(jid);assert state['state']=='completed',state
    assert state['last_result']['task_details']['scene']==2
    b._jobs['next']={'id':'next','state':'queued'}
    assert b.status('next')['last_result']['task_details']['scene']==2
    assert 'task_details' not in b.status('next')

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium unavailable')
def test_browser_preview_metadata_not_editor_or_new_job():
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page();page.evaluate(setup_js);page.set_content(HTML,wait_until='domcontentloaded');page.wait_for_function('choices.length===2')
        result=page.evaluate('''() => {
          $('monitorToggle').open=true;monitorPrefs={mode:'retain',percent:50};
          const old={person:'Ada',character:'Role 1',production:'Test',scene:1,kind:'image',prompt:'Submitted Ada prompt'};
          const next={person:'Bella',character:'Role 2',production:'Test',scene:2,kind:'image',prompt:'Submitted Bella prompt'};
          $('generatorChoice').value='b';$('generatorPreview').value='UNRELATED EDITOR DRAFT';
          const last={id:'old-output',job_id:'old',task_index:1,kind:'image',task_details:old};
          const base={id:'new',batch:true,state:'running',task_index:2,preview_task_index:2,task_details:next,last_result:last,preview_kind:'image',preview_rev:1,preview_total_steps:8,preview_step:1};
          renderGenerationMonitor(base);
          const retained=$('monitorState').textContent.includes('Ada')&&!$('monitorState').textContent.includes('Bella')&&$('monitorPrompt').textContent===old.prompt;
          renderGenerationMonitor({...base,preview_rev:2,preview_step:4});
          const live=$('monitorState').textContent.includes('Bella')&&$('monitorPrompt').textContent===next.prompt;
          $('generatorChoice').value='a';$('generatorPreview').value='ANOTHER DRAFT';renderGenerationMonitor({...base,preview_rev:3,preview_step:5});
          const stable=$('monitorState').textContent.includes('Bella')&&$('monitorPrompt').textContent===next.prompt;
          monitorPrefs={mode:'static',percent:0};renderGenerationMonitor({id:'third',state:'queued'});
          const empty=!$('monitorState').textContent.includes('Ada')&&!$('monitorState').textContent.includes('Bella')&&!$('monitorPrompt').textContent.includes('DRAFT');
          monitorPrefs={mode:'retain',percent:0};renderGenerationMonitor({id:'third',state:'queued',last_result:{...last,id:'unknown',task_details:null}});
          const unknown=!$('monitorState').textContent.includes('Ada')&&!$('monitorState').textContent.includes('Bella')&&$('monitorPrompt').textContent==='Submitted prompt unavailable for this output.';
          return {retained,live,stable,empty,unknown};
        }''')
        browser.close();assert all(result.values()),result

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium unavailable')
def test_monitor_compact_layout_and_prompt_visibility():
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1360,'height':900});page.evaluate(setup_js);page.set_content(HTML,wait_until='domcontentloaded');page.wait_for_function('choices.length===2')
        page.evaluate('''() => {$('monitorToggle').open=true;renderMonitorDetails({person:'Example performer',character:'Example character',production:'Example production (2026)',kind:'image',scene:2,prompt:'A'.repeat(12000)},true);setText('monitorActiveState','Generating another task');setText('monitorPercent','38%');$('monitorProgress').value=38;}''')
        assert page.locator('#monitorPerson').inner_text()=='Example performer'
        assert page.locator('#monitorRole').inner_text()=='Example character'
        assert page.locator('#monitorProduction').inner_text()=='Example production (2026)'
        assert page.locator('#monitorPrompt').is_hidden()
        assert page.locator('#monitorActiveState').inner_text()=='Generating another task'
        page.locator('#monitorPromptDetails summary').click()
        assert page.locator('#monitorPrompt').is_visible()
        assert page.locator('#monitorPrompt').bounding_box()['height']<=155
        page.set_viewport_size({'width':700,'height':900})
        assert page.locator('.monitor-info').evaluate('(el)=>el.scrollWidth<=el.clientWidth')
        page.evaluate('renderMonitorDetails(null)')
        assert page.locator('#monitorPromptDetails').is_hidden()
        assert page.locator('#monitorRole').is_hidden()
        assert page.locator('#monitorPerson').inner_text()=='No preview yet'
        browser.close()

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium unavailable')
def test_completed_video_requires_manual_play_but_live_video_autoplays():
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page();page.evaluate(setup_js);page.set_content(HTML,wait_until='domcontentloaded');page.wait_for_function('choices.length===2')
        result=page.evaluate('''() => {
          const v=$('monitorLiveVideo');let plays=0,pauses=0,loads=0;
          v.play=()=>{plays++;return Promise.resolve()};v.pause=()=>{pauses++};v.load=()=>{loads++};
          const initial=!v.autoplay&&v.controls;
          $('monitorToggle').open=true;monitorPrefs={mode:'retain',percent:0};
          const live={id:'batch',batch:true,state:'running',task_index:1,preview_task_index:1,preview_kind:'video',preview_rev:1};
          renderGenerationMonitor(live);const livePlays=v.autoplay&&plays===1;
          const completed={...live,state:'completed',last_result:{id:'clip1',job_id:'batch',task_index:1,kind:'video'}};
          renderGenerationMonitor(completed);const completedPaused=!v.autoplay&&plays===1&&v.controls&&v.dataset.version==='result:clip1';
          v.play();const before=[plays,pauses,loads];renderGenerationMonitor(completed);
          const pollingPreservesManualPlayback=before.every((n,i)=>n===[plays,pauses,loads][i]);
          renderGenerationMonitor({id:'next',state:'queued',last_result:completed.last_result});
          const retainedPaused=!v.autoplay&&plays===2&&v.dataset.version==='result:clip1';
          renderGenerationMonitor({...live,id:'next',preview_rev:2,last_result:completed.last_result});
          const nextLive=v.autoplay&&plays===3;
          renderGenerationMonitor({...live,id:'next',state:'completed',last_result:{id:'clip2',job_id:'next',task_index:1,kind:'video'}});
          const secondCompleted=!v.autoplay&&plays===3&&v.dataset.version==='result:clip2';
          return {initial,livePlays,completedPaused,pollingPreservesManualPlayback,retainedPaused,nextLive,secondCompleted};
        }''')
        browser.close();assert all(result.values()),result

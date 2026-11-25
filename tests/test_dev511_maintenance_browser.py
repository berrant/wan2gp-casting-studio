"""Main-screen active-job banner, and tab navigation with no automatic research."""
import shutil
from pathlib import Path
import pytest
pw=pytest.importorskip('playwright.sync_api')
from test_generator_session_browser import setup_js
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium is optional')
def test_activity_indicator_and_no_performer_autoresearch():
    with pw.sync_playwright() as p:
        b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page(viewport={'width':1440,'height':820})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.evaluate('''() => {
           const prior=window.fetch;
           window.researchCalls=[];
           window.fakeJobs=[];
           window.fetch=async(url,opt)=>{
              const v=String(url);
              if(v.includes('profiles/link?')||v.includes('images/auto?'))window.researchCalls.push(v);
              if(v.includes('maintenance/activity'))return {ok:true,json:async()=>({running:!!window.fakeJobs.length,count:window.fakeJobs.length,jobs:window.fakeJobs}),status:200};
              if(v==='api/catalog')return {ok:true,json:async()=>({people:[{name:'Ada Test',credits:['Test Show'],type:'Actor'}],roles:[{actress:'Ada Test',character:'Hero',production:'Test Show'}],models:[{name:'Ada Test',filename:'Ada_Test_H3.safetensors',path:'celebs/Ada_Test_H3.safetensors',family:'minimax_h3'}],meta:{}}),status:200};
              return prior(url,opt);
           }
        }''')
        page.set_content(HTML,wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('#maintenanceHeaderStatus').textContent.includes('idle')")
        page.evaluate("showTab('performers')")
        page.wait_for_timeout(250)
        assert page.locator('#list .card').count()==1
        assert page.evaluate('window.researchCalls')==[]
        assert page.locator('#maintenanceBanner').is_hidden()
        page.evaluate('''() => {window.fakeJobs=[{label:'Screen-role synchronization',done:24,total:387,detail:'Ming Ching'}]}''')
        page.evaluate('pollMaintenanceActivity()')
        assert page.locator('#maintenanceBanner').is_visible()
        assert '24/387' in page.locator('#maintenanceActivityText').inner_text()
        page.locator('#maintenanceBanner button').click()
        assert page.locator('#settingsModal').is_visible()
        assert page.locator('#backgroundTools').evaluate('(el)=>el.open')
        page.evaluate('window.fakeJobs=[];pollMaintenanceActivity()')
        page.wait_for_function("document.querySelector('#maintenanceBanner').hidden")
        assert not errors,errors
        b.close()

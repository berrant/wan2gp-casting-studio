"""dev5.4 browser: scan and decompile gallery are available inside Casting Studio."""
import shutil
from pathlib import Path
import pytest
sync_playwright=pytest.importorskip('playwright.sync_api').sync_playwright
from test_generator_session_browser import setup_js
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()


def test_workshop_scan_and_inline_reconstructed_media_viewer():
    if not shutil.which('chromium'):pytest.skip('Chromium not installed')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1360,'height':900})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.evaluate('''() => {
           const original=window.fetch;
           window.fetch=async (url,options={})=>{
             const route=String(url);
             let data=null;
             if(route.startsWith('api/workshop/scan-status'))data={running:false,last_scanned:1795520000,valid:1343,invalid:0,checked:1343,total:1343,phase:'Scan complete'};
             else if(route.startsWith('api/workshop/decompiled?'))data={files:[
               {filename:'001.png',media_type:'image/png',size:23455,url:'api/workshop/decompiled/file?name=x&file=001.png'},
               {filename:'clip.mp4',media_type:'video/mp4',size:33555,url:'api/workshop/decompiled/file?name=x&file=clip.mp4'},
               {filename:'audio.wav',media_type:'audio/wav',size:10000,url:'api/workshop/decompiled/file?name=x&file=audio.wav'}]};
             if(data)return {ok:true,json:async()=>data,status:200};
             return original(url,options);
           }
        }''')
        page.set_content(HTML,wait_until='domcontentloaded')
        page.evaluate("showTab('workshop')")
        page.evaluate("workshopUpdateScanStatus()")
        page.wait_for_function("document.querySelector('#workshopScanText').textContent.includes('1343 valid')")
        assert 'Last completed scan:' in page.locator('#workshopScanLast').text_content()
        page.evaluate("workshopShowResults('celebs/Abby_H3')")
        page.wait_for_function("document.querySelectorAll('#workshopResultGallery .decompiled-card').length===3")
        assert page.locator('#workshopResults').is_visible()
        assert page.locator('#workshopResultGallery img').count()==1
        assert page.locator('#workshopResultGallery video').count()==1
        assert page.locator('#workshopResultGallery audio').count()==1
        assert not errors,errors
        browser.close()

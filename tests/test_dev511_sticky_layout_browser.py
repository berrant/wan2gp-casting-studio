"""Visible navigation, activity and selection toolbars must never collide."""
from pathlib import Path
import pytest, shutil
pw=pytest.importorskip('playwright.sync_api')
from test_generator_session_browser import setup_js
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium missing')
def test_sticky_bands_no_overlap_across_responsive_widths():
    with pw.sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        for width in [390,570,850,1120,1440,2048]:
            page=browser.new_page(viewport={'width':width,'height':820})
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.evaluate(setup_js)
            page.evaluate('''() => {
               window.fakeJobs=[{label:'Screen-role synchronization',done:24,total:387,detail:'Ming Ching'}];
               const old=window.fetch;
               window.fetch=(url,opts)=>String(url).includes('maintenance/activity')?
                 Promise.resolve({ok:true,json:async()=>({running:window.fakeJobs.length>0,count:window.fakeJobs.length,jobs:window.fakeJobs})}):old(url,opts)
             }''')
            page.set_content(HTML,wait_until='domcontentloaded')
            # Ensure there's enough scroll depth for the selections toolbar to become sticky.
            page.evaluate("showTab('performers');document.querySelector('#browseSection').insertAdjacentHTML('beforeend',`<div style='height:2800px'></div>`)")
            page.evaluate('pollMaintenanceActivity()')
            page.wait_for_function("!document.querySelector('#maintenanceBanner').hidden")
            page.evaluate('window.scrollTo(0, 1350)')
            assert page.evaluate('window.scrollY')>600
            page.wait_for_timeout(130)
            positions=page.evaluate('''() => {
              const ids=['navTabs','maintenanceBanner'];
              const r=x=>{let b=x.getBoundingClientRect();return {top:b.top,bottom:b.bottom,left:b.left,right:b.right,height:b.height}};
              return {nav:r(document.querySelector('#navTabs')),banner:r(document.querySelector('#maintenanceBanner')),selections:r(document.querySelector('main>.sidebar'))}
            }''')
            nav,banner,selections=positions['nav'],positions['banner'],positions['selections']
            assert banner['top']>=nav['bottom']-2,(width,positions)
            assert selections['top']>=banner['bottom']-2,(width,positions)
            assert not errors,(width,errors)
            # Complete the current job: selections must move up below tabs, without colliding.
            page.evaluate('window.fakeJobs=[];pollMaintenanceActivity()')
            page.wait_for_function("document.querySelector('#maintenanceBanner').hidden")
            page.wait_for_timeout(130)
            positions=page.evaluate('''() => {const a=document.querySelector('#navTabs').getBoundingClientRect(); const b=document.querySelector('main>.sidebar').getBoundingClientRect();return {navBottom:a.bottom,sideTop:b.top}}''')
            assert positions['sideTop']>=positions['navBottom']-2,(width,positions)
            page.close()
        browser.close()

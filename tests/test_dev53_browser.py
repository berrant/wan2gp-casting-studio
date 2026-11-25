import shutil
import pytest
from pathlib import Path
sync_playwright=pytest.importorskip('playwright.sync_api').sync_playwright
from test_generator_session_browser import setup_js
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()


def test_image_inspector_refmod_filter_and_split_resolution_picker():
    if not shutil.which('chromium'):pytest.skip('Chromium not installed')
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page(viewport={'width':1280,'height':840});page.set_default_timeout(6000)
        print('page created',flush=True)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.evaluate('''() => {
          const orig=window.fetch;
          window.fetch=async (url,options={})=>{
            const r=await orig(url,options);
            if(String(url).includes('generator/model-details')){
              const data=await r.json();data.resolutions.push({label:'704x1280 (9:16)',value:'704x1280'});
              return {...r,json:async()=>data};
            }
            return r;
          }
        }''')
        page.set_content(HTML,wait_until='domcontentloaded')
        page.evaluate('openLightbox("https://example.com/image.png","source page","1200 × 800",false)')
        assert 'open' in page.locator('#photoLightbox').get_attribute('class')
        assert page.locator('#lightboxImage').get_attribute('src')=='https://example.com/image.png'
        assert not page.locator('#lightboxUse').is_visible()
        page.locator('#photoLightbox button').first.click()
        assert not page.locator('#photoLightbox').is_visible()
        page.evaluate("showTab('workshop')")
        page.evaluate('''() => {workshopMods=[
          {name:'celebs/Grace_H3',filename:'Grace_H3.safetensors',bytes:5500,metadata:{kind:'identity'}},
          {name:'celebs/Leia_H3',filename:'Leia_H3.safetensors',bytes:15000,metadata:{kind:'identity'}}
        ];workshopFilterMods();}''')
        page.locator('#workshopModSearch').fill('Leia')
        assert page.locator('#workshopMod option').count()==1
        assert page.locator('#workshopMod option').first.text_content().startswith('celebs/Leia_H3')
        page.evaluate('openGenerator()')
        page.wait_for_function('document.querySelector("#generatorLoraStatus").textContent.includes("installed for this model")')
        assert '480p' in page.locator('#generatorResolutionCategory option').all_text_contents()
        assert '720p' in page.locator('#generatorResolutionCategory option').all_text_contents()
        page.locator('button[data-workspace=model]').click()
        page.locator('#generatorResolutionCategory').select_option('720p')
        assert page.locator('#generatorResolution').input_value()=='704x1280'
        page.locator('#generatorResolutionCategory').select_option('480p')
        assert page.locator('#generatorResolution').input_value() in ('','832x480')
        assert not errors,errors
        b.close()

"""User changing H3/FLUX selector reconciles saved selections and on-screen counts."""
import shutil
from pathlib import Path
import pytest
pw=pytest.importorskip('playwright.sync_api')
from test_dev55_browser import MOCK
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium unavailable')
def test_switch_h3_to_flux_prunes_and_relinks_in_ui():
    with pw.sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1300,'height':850})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(MOCK)
        page.set_content(HTML,wait_until='domcontentloaded')
        page.wait_for_function('document.querySelector("#count").textContent==="1"')
        page.evaluate('''() => {
          window.mockChoices=[
            {key:'zoiepalmer|theandroid|darkmatter',person:'Zoie Palmer',character:'The Android',production:'Dark Matter',refmod:'Zoie_Palmer_H3.safetensors'},
            {key:'alicebraga|amandalucas|darkmatter',person:'Alice Braga',character:'Amanda Lucas',production:'Dark Matter',refmod:'Alice_Braga_H3.safetensors'}
          ];
          choices=window.mockChoices.slice();
          catalog.models.push({name:'Alice Braga',path:'Alice_Braga_FLUX.safetensors',family:'flux2'});
          window.productionData.cast[1].refmod_families.flux2='Alice_Braga_FLUX.safetensors';
          const previous=window.fetch;
          window.fetch=async(url,options={})=>{
             if(String(url).includes('api/choices/reconcile')){
                const body=JSON.parse(options.body);
                if(body.family==='flux2'){
                  const keep={...window.mockChoices[1],refmod:'Alice_Braga_FLUX.safetensors'};
                  window.mockChoices=[keep];
                  return {ok:true,status:200,json:async()=>({family:'flux2',choices:[keep],removed:[{key:'zoiepalmer|theandroid|darkmatter',person:'Zoie Palmer'}],switched:[{key:keep.key,person:keep.person,refmod:keep.refmod}],remaining:1})};
                }
             }
             return previous(url,options);
          };
          render();
        }''')
        page.locator('#promptModel').select_option('flux2_dev')
        page.wait_for_function('document.querySelector("#count").textContent==="1" && document.querySelector("#modelSwitchStatus").textContent.includes("1 incompatible")')
        assert page.locator('#modelSwitchStatus').inner_text().startswith('1 incompatible selection removed')
        assert '1 RefMod switched' in page.locator('#modelSwitchStatus').inner_text()
        assert page.evaluate('choices[0].refmod')=='Alice_Braga_FLUX.safetensors'
        assert not errors,errors
        browser.close()

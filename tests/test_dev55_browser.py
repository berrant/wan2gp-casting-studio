"""dev5.5 user-workflow regressions: single-source casting choices from both tabs."""
import shutil
from pathlib import Path
import pytest
playwright=pytest.importorskip('playwright.sync_api')
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

MOCK=r'''(() => {
 const person = (name, ref) => ({name, path:ref, family:'minimax_h3'});
 const record = (actress, character, production, ref) => ({actress,character,production,refmod_families:ref?{minimax_h3:ref}:{}});
 const others={key:'other|outside|differentshow',person:'Other',character:'Outside',production:'Different Show',refmod:'Other_H3.safetensors'};
 window.mockChoices=[others];
 window.mockWrites=[];
 window.mockFails=[];
 window.responses=[];
 window.productionData={production:'Dark Matter',cast:[
  record('Zoie Palmer','The Android','Dark Matter','Zoie_Palmer_H3.safetensors'),
  record('Alice Braga','Amanda Lucas','Dark Matter','Alice_Braga_H3.safetensors'),
  record('Missing','Missing Character','Dark Matter',null)
 ]};
 window.fetch=async (url,opts={})=>{
  const path=String(url).replace(/^api\//,'').split('?')[0];
  const verb=opts.method||'GET';
  const json=(data,ok=true)=>({ok,status:ok?200:500,json:async()=>data,text:async()=>typeof data==='string'?data:JSON.stringify(data)});
  if(path==='catalog')return json({people:[],roles:[{actress:'Zoie Palmer',character:'The Android',production:'Dark Matter'},{actress:'Alice Braga',character:'Amanda Lucas',production:'Dark Matter'}],models:[person('Zoie Palmer','Zoie_Palmer_H3.safetensors'),person('Alice Braga','Alice_Braga_H3.safetensors'),person('Other','Other_H3.safetensors')]});
  if(path==='choices'){
    if(verb==='PUT'){
      let v=JSON.parse(opts.body);
      window.mockWrites.push(v);
      if(window.mockFails.includes(v.key))return json('Simulated save error',false);
      window.mockChoices=window.mockChoices.filter(c=>c.key!==v.key).concat(v);
      return json({saved:true});
    }
    return json(window.mockChoices.slice());
  }
  if(path.startsWith('choices/')){
    const k=decodeURIComponent(path.slice(8));
    if(window.mockFails.includes(k))return json('Simulated delete error',false);
    window.mockChoices=window.mockChoices.filter(c=>c.key!==k);
    return json({deleted:true});
  }
  if(path==='discovery/people')return json([]);
  if(path==='productions')return json([{name:'Dark Matter',kind:'series',year:2015}]);
  if(path==='productions/cast')return json(window.productionData);
  if(path==='images/cached')return json({});
  if(path==='profiles/categories')return json({});
  if(path==='prompts/template')return json({video_count:2});
  if(path==='prompts/overrides')return json({});
  if(path==='identities')return json({known:{},overrides:{}});
  if(path==='profiles/markers')return json({});
  if(path==='profiles/gender')return json({});
  if(path==='personal')return json([]);
  if(path==='personal/refmods')return json([]);
  if(path==='generator/models')return json({models:[{model_type:'h3_ref2va_pruned_checkpoint',name:'H3',ready:true}]});
  if(path==='generator/model-details')return json({model_type:'h3_ref2va_pruned_checkpoint',resolution_default:'832x480',resolutions:[{label:'832x480 (16:9)',value:'832x480'}],loras:[],lora_supported:true,default_loras:[]});
  if(path==='generator/preview')return json({refmod_filename:'H3.safetensors',prompt:'Prompt'});
  if(path==='generator/submit'){
    window.responses.push(JSON.parse(opts.body));
    return json({id:'123456789abc'});
  }
  if(path.startsWith('generator/jobs/'))return json({id:'123456789abc',state:'completed',message:'ok',files:[]});
  if(path==='integration/status')return json({casting_studio:'v6.9.0-dev5.6',refmod_fork:{}});
  if(path==='prefetch/status')return json({running:false,done:0,total:0});
  if(path==='enrichment/status')return json({running:false,done:0,total:0});
  if(path==='credits/status')return json({running:false,done:0,total:0});
  return json({});
 };
})()'''

@pytest.fixture
def page():
 if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
 with playwright.sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
  page=browser.new_page(viewport={'width':1400,'height':940})
  page.set_default_timeout(4000)
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.evaluate(MOCK)
  page.set_content(HTML,wait_until='domcontentloaded')
  page.wait_for_function("typeof choices !== 'undefined' && choices.length === 1 && document.querySelector('#count').textContent === '1'")
  page.evaluate("showTab('productions')")
  page.locator('#productionQuery').fill('Dark Matter')
  page.wait_for_function("document.querySelector('#productionMatches').textContent.includes('Dark Matter')")
  page.evaluate("openProduction('Dark Matter')")
  page.wait_for_function("document.querySelectorAll('#productionCast .cast-row').length===3")
  yield page,errors
  browser.close()

def test_role_selection_is_identical_between_production_and_performers(page):
 tab,errors=page
 assert tab.locator('#productionCast .cast-row').nth(0).get_by_role('button', name='Select', exact=True).count()==1
 tab.locator('#productionCast .cast-row').nth(0).get_by_role('button', name='Select', exact=True).click()
 tab.wait_for_function("document.querySelector('#productionCast').textContent.includes('Selected · Remove')")
 assert tab.locator('#productionCast .cast-row').nth(0).get_by_role('button',name='✓ Selected · Remove').get_attribute('aria-pressed')=='true'
 tab.evaluate("showTab('performers')")
 assert tab.locator('#list .role button.selected').count()==1
 tab.evaluate("showTab('productions')")
 tab.wait_for_function("document.querySelector('#productionMatches').textContent.includes('Dark Matter')")
 tab.evaluate("openProduction('Dark Matter')")
 tab.wait_for_function("document.querySelector('#productionCast').textContent.includes('Selected · Remove')")
 assert tab.locator('#productionCast .cast-row').nth(0).get_by_role('button',name='✓ Selected · Remove').count()==1
 tab.locator('#productionCast .cast-row').nth(0).get_by_role('button',name='✓ Selected · Remove').click()
 tab.wait_for_function("!document.querySelector('#productionCast').textContent.includes('Selected · Remove')")
 assert len(tab.evaluate('window.mockChoices'))==1 # unrelated show never removed
 assert not errors,errors

def test_select_all_is_idempotent_and_missing_refmod_is_never_queued(page):
 tab,errors=page
 tab.locator('#selectProductionAll').click()
 tab.wait_for_function("document.querySelector('#productionSelectionStatus').textContent.includes('2 of 2')")
 assert tab.locator('#productionCast .cast-row button.selected').count()==2
 assert len(tab.evaluate('window.mockChoices'))==3
 assert tab.locator('#selectProductionAll').is_disabled()
 tab.locator('#queueProductionButton').click()
 tab.wait_for_function("document.querySelector('#generatorScopeStatus').textContent.includes('2 casting tasks')")
 assert tab.locator('#generatorScope').input_value()=='production:darkmatter'
 assert tab.locator('#generatorChoice option').count()==2
 assert 'Other' not in tab.locator('#generatorChoice').inner_text()
 tab.wait_for_function("document.querySelector('#generatorSubmitNext').disabled===false")
 tab.evaluate('submitGenerator(true)')
 tab.wait_for_function('window.responses.length===1')
 assert tab.evaluate('window.responses[0].choice_key') in ['zoiepalmer|theandroid|darkmatter','alicebraga|amandalucas|darkmatter']
 assert tab.locator('#generatorChoice').input_value()==tab.evaluate("window.responses[0].choice_key") or tab.locator('#generatorChoice').input_value() in ['zoiepalmer|theandroid|darkmatter','alicebraga|amandalucas|darkmatter']
 tab.evaluate('closeGenerator()')
 tab.once('dialog',lambda d:d.accept())
 tab.locator('#clearProductionSelections').click()
 tab.wait_for_function("document.querySelector('#productionSelectionStatus').textContent.includes('0 of 2')")
 assert len(tab.evaluate('window.mockChoices'))==1
 assert tab.evaluate('window.mockChoices[0].production')=='Different Show'
 assert not errors,errors

def test_failure_keeps_selected_state_and_global_scope_still_works(page):
 tab,errors=page
 k='zoiepalmer|theandroid|darkmatter'
 tab.evaluate("k=>window.mockFails.push(k)",k)
 tab.once('dialog',lambda d:d.accept())
 tab.locator('#productionCast .cast-row').nth(0).get_by_role('button',name='Select',exact=True).click()
 tab.wait_for_timeout(150)
 assert len(tab.evaluate('window.mockChoices'))==1
 assert tab.locator('#productionCast .cast-row button.selected').count()==0
 tab.evaluate('window.mockFails=[]')
 tab.locator('#productionCast .cast-row').nth(0).get_by_role('button',name='Select',exact=True).click()
 tab.wait_for_function("document.querySelector('#productionCast').textContent.includes('Selected · Remove')")
 tab.evaluate('openGenerator()')
 tab.wait_for_function("document.querySelector('#generatorScopeStatus').textContent.includes('2 casting tasks')")
 assert tab.locator('#generatorScope').input_value()=='all'
 tab.locator('#generatorChoice option').count()==2
 tab.locator('#generatorScope').select_option('production:darkmatter')
 assert tab.locator('#generatorChoice option').count()==1
 tab.locator('#generatorScope').select_option('all')
 assert tab.locator('#generatorChoice option').count()==2
 assert not errors,errors

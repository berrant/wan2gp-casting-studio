import json
from pathlib import Path
import shutil
import pytest
playwright=pytest.importorskip('playwright.sync_api')
sync_playwright=playwright.sync_playwright
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()
setup_js=r'''(() => {
 const prefs = {};
 Object.defineProperty(window,'sessionStorage',{configurable:true,value:{getItem:k=>prefs[k]??null,setItem:(k,v)=>prefs[k]=String(v),removeItem:k=>delete prefs[k]}});
 window.responses=[];
 window.fetch = async (url, options={})=>{
  const path=String(url).replace(/^api\//,'').split('?')[0];
  let data={};
  if(path==='catalog')data={people:[],roles:[],models:[]};
  else if(path==='choices')data=[{key:'a',person:'Ada',character:'Role 1',production:'Test',refmod:'Ada.safetensors'},{key:'b',person:'Bella',character:'Role 2',production:'Test',refmod:'Bella.safetensors'}];
  else if(path==='personal')data=[];
  else if(path==='generator/models')data={models:[{model_type:'h3_ref2va_pruned_checkpoint',name:'MiniMax H3 Ref2VA Pruned 20B',ready:true},{model_type:'h3_alternate',name:'MiniMax H3 alternate',ready:true}]};
  else if(path==='generator/model-details')data={model_type:new URLSearchParams(String(url).split('?')[1]).get('model_type'),resolution_default:'832x480',resolutions:[{label:'832x480 (16:9)',value:'832x480'},{label:'480x832 (9:16)',value:'480x832'}],loras:['Turbo.safetensors','MMH3-RealismSlider-V1.safetensors','Other.safetensors'],lora_supported:true,default_loras:['Turbo.safetensors'],default_multipliers:'1'};
  else if(path==='generator/preview')data={refmod_filename:'Ada.safetensors',prompt:'Test prompt'};
  else if(path==='generator/submit'){window.responses.push(JSON.parse(options.body));data={id:'01234567abcdf'.repeat(2)}}
  else if(path.startsWith('generator/jobs/'))data={id:'01234567abcdf',state:'completed',message:'Done',files:['done.mp4']};
  else if(path==='prefetch/status')data={running:false,done:0,total:0};
  else if(path==='enrichment/status')data={running:false,done:0,total:0};
  return {ok:true,json:async()=>data,text:async()=>JSON.stringify(data),status:200};
 };
})()'''
def test_generator_settings_survive_cast_switch_model_switch_and_reload():
 if not shutil.which('chromium'):
  pytest.skip('Chromium is optional for UI tests')
 with sync_playwright() as p:
  b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
  page=b.new_page(viewport={'width':1300,'height':950})
  page.on('pageerror',lambda e:print('PAGE ERROR',e))
  page.evaluate(setup_js)
  page.set_content(HTML,wait_until='domcontentloaded')
  page.evaluate('openGenerator()')
  page.wait_for_function("document.querySelector('#generatorLoraStatus').textContent.includes('installed for this model')")
  page.locator('#generatorSteps').fill('8')
  page.locator('#generatorStrength').fill('1.3')
  page.locator('#generatorResolution').select_option('480x832')
  page.locator('.generator-lora-row input').first.fill('0.75')
  page.locator('#generatorAddLora').click()
  page.locator('.generator-lora-row select').last.select_option('MMH3-RealismSlider-V1.safetensors')
  page.locator('.generator-lora-row input').last.fill('1.5')
  assert page.locator('.generator-lora-row select').evaluate_all('(els)=>els.map(e=>e.value)')==['Turbo.safetensors','MMH3-RealismSlider-V1.safetensors']
  assert page.locator('#generatorSteps').input_value()=='8'
  page.evaluate('closeGenerator()')
  page.evaluate('openGenerator()')
  page.wait_for_function("document.querySelector('#generatorLoraStatus').textContent.includes('installed for this model')")
  assert page.locator('.generator-lora-row input').evaluate_all('(els)=>els.map(e=>e.value)')==['0.75','1.5']
  assert page.locator('#generatorResolution').input_value()=='480x832'
  # check current model and next model isolation
  page.locator('#generatorSessionPanel summary').first.click() if not page.locator('#generatorSessionPanel').evaluate('(e)=>e.open') else None
  page.locator('#generatorModelType').select_option('h3_alternate')
  page.wait_for_function("document.querySelector('#generatorLoraStatus').textContent.includes('installed for this model')")
  assert page.locator('#generatorSteps').input_value()==''
  page.locator('#generatorModelType').select_option('h3_ref2va_pruned_checkpoint')
  page.wait_for_function("document.querySelector('#generatorSteps').value==='8'")
  page.locator('#generatorChoice').select_option('a')
  page.evaluate('submitGenerator(true)')
  page.wait_for_function('window.responses.length===1')
  payload=page.evaluate('window.responses[0]')
  assert payload['loras']==[{'name':'Turbo.safetensors','multiplier':0.75},{'name':'MMH3-RealismSlider-V1.safetensors','multiplier':1.5}]
  assert page.locator('#generatorChoice').input_value()=='b'
  page.evaluate('submitGenerator(false)')
  page.wait_for_function('window.responses.length===2')
  second=page.evaluate('window.responses[1]')
  assert second['choice_key']=='b'
  assert second['loras']==payload['loras']
  assert 'Bella' not in page.evaluate("sessionStorage.getItem('casting-studio:generator:session:v1')")
  # Simulate a fresh page with the same browser tab session preferences.
  saved=page.evaluate("sessionStorage.getItem('casting-studio:generator:session:v1')")
  page.close()
  page=b.new_page(viewport={'width':1300,'height':950})
  page.on('pageerror',lambda e:print('PAGE ERROR on new page',e))
  page.evaluate(setup_js)
  page.evaluate("v => sessionStorage.setItem('casting-studio:generator:session:v1',v)",saved)
  page.set_content(HTML,wait_until='domcontentloaded')
  page.evaluate('openGenerator()')
  page.wait_for_function("document.querySelector('#generatorSteps').value==='8'")
  assert page.locator('.generator-lora-row input').evaluate_all('(els)=>els.map(e=>e.value)')==['0.75','1.5']
  # Existing session's removed LoRA cannot be silently omitted from future jobs.
  saved_obj=json.loads(page.evaluate("sessionStorage.getItem('casting-studio:generator:session:v1')"))
  saved_obj['modelSettings']['h3_video::h3_ref2va_pruned_checkpoint']['loras'].append({'name':'Deleted-LoRA.safetensors','multiplier':1.2})
  page.close()
  page=b.new_page(viewport={'width':1300,'height':950})
  page.evaluate(setup_js)
  page.evaluate("v => sessionStorage.setItem('casting-studio:generator:session:v1',v)",json.dumps(saved_obj))
  page.set_content(HTML,wait_until='domcontentloaded')
  page.evaluate('openGenerator()')
  page.wait_for_function("document.querySelectorAll('.generator-lora-row').length===3")
  assert page.locator('#generatorSubmit').is_disabled()
  assert 'no longer installed' in page.locator('#generatorLoraStatus').text_content()
  page.locator('#generatorSessionPanel summary').first.click() if not page.locator('#generatorSessionPanel').evaluate('(e)=>e.open') else None
  page.locator('.generator-lora-row button').last.click()
  assert page.locator('#generatorSubmit').is_enabled()
  # Explicit reset restores model defaults without touching the casting selections.
  page.on('dialog',lambda dialog:dialog.accept())
  page.evaluate('resetGeneratorSession()')
  page.wait_for_function("document.querySelector('#generatorSteps').value==='' && document.querySelectorAll('.generator-lora-row').length===1")
  assert page.locator('.generator-lora-row input').first.input_value()=='1'
  b.close()


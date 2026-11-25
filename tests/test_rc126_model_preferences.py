"""Fine-tune settings independent of browser origin."""
import json
from test_native_plugin import installation
from test_persona_power import tab
API='/casting-studio/api/settings/model-preferences'

def test_server_preferences_roundtrip(installation):
    c,*_=installation
    assert c.get(API).json()=={'preferences':None}
    data={'generator':{'version':1,'boardModel':'h3_video','lastImageBoard':'h3_image','selectedModels':{'h3_video':'prism'},'modelSettings':{'h3_video::prism':{'steps':'8','resolution':'480x832','skip_global_loras':True},'h3_video::other':{'steps':'12'}}},'global_loras':{'version':2,'profiles':{},'legacy':{}}}
    assert c.put(API,json=data).json()=={'saved':True}
    assert c.get(API).json()['preferences']==data
    bad=json.loads(json.dumps(data));bad['generator']['modelSettings']['h3_video::prism']['__proto__']={}
    assert c.put(API,json=bad).status_code==422
    assert c.get(API).json()['preferences']==data

def test_model_settings_isolated_and_restored(tab):
    tab.evaluate('''() => {
      const old=fetch;window.persisted=[];modelPrefsServerReady=true;modelPrefsLastSent='';
      const ok=data=>({ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)});
      window.fetch=(u,o={})=>{const path=String(u).split('?')[0];
        if(path==='api/settings/model-preferences'&&o.method==='PUT'){persisted.push(JSON.parse(o.body));return Promise.resolve(ok({saved:true}));}
        if(path==='api/generator/models')return Promise.resolve(ok({models:[{model_type:'prism',name:'PRISM',ready:true},{model_type:'alternate',name:'Alternate',ready:true}]}));
        if(path==='api/generator/model-details')return Promise.resolve(ok({resolution_default:'832x480',resolutions:[{label:'832x480',value:'832x480'},{label:'480x832',value:'480x832'}],loras:['One','Two'],lora_supported:true,default_loras:[],steps_default:12,sliding_window_supported:true}));
        return old(u,o);
      };return openGenerator();
    }''')
    tab.wait_for_function("$('generatorModelType').value==='prism'&&generatorDetails&&!generatorRestoring")
    tab.evaluate("$('generatorSteps').value='8';$('generatorStrength').value='1.4';$('generatorSeed').value='456';generatorBuildResolutionChoices('480x832');$('generatorSkipGlobalLoras').checked=true;addGeneratorLora('One',1.5);addGeneratorLora('Two',0.7);generatorSaveCurrentSettings()")
    tab.evaluate('modelPrefsWrite')
    tab.evaluate("$('generatorModelType').value='alternate';updateGeneratorModel()")
    assert tab.evaluate("$('generatorSteps').value")=='12'
    assert not tab.evaluate("$('generatorSkipGlobalLoras').checked")
    tab.evaluate("$('generatorSteps').value='18';generatorSaveCurrentSettings();$('generatorModelType').value='prism';updateGeneratorModel()")
    assert tab.evaluate("$('generatorSteps').value")=='8'
    assert tab.evaluate("$('generatorStrength').value")=='1.4'
    assert tab.evaluate("$('generatorSeed').value")=='456'
    assert tab.evaluate("$('generatorResolution').value")=='480x832'
    assert tab.evaluate("$('generatorSkipGlobalLoras').checked")
    assert tab.evaluate('collectGeneratorLoras()')==[{'name':'One','multiplier':1.5},{'name':'Two','multiplier':0.7}]
    tab.evaluate('modelPrefsWrite')
    assert tab.evaluate("persisted.at(-1).generator.modelSettings['h3_video::alternate'].steps")=='18'
    assert len(tab.evaluate("persisted.at(-1).generator.modelSettings['h3_video::prism'].loras"))==2
    tab.evaluate('closeGenerator()');tab.evaluate('openGenerator()');tab.wait_for_function("generatorDetails&&!generatorRestoring&&$('generatorSteps').value==='8'")
    assert tab.evaluate("$('generatorSkipGlobalLoras').checked")


def test_fresh_browser_loads_server_preferences_without_local_storage():
    import shutil,pytest
    from test_dev55_browser import HTML,MOCK,playwright
    if not shutil.which('chromium'):pytest.skip('Chromium unavailable')
    data={'generator':{'version':1,'boardModel':'h3_video','lastImageBoard':'h3_image','selectedModels':{'h3_video':'prism'},'modelSettings':{'h3_video::prism':{'steps':'8','strength':'1.4','seed':'42','resolution':'480x832','loras':[{'name':'One','multiplier':1.5}],'skip_global_loras':True}}},'global_loras':{'version':2,'profiles':{},'legacy':{}}}
    with playwright.sync_playwright() as p:
        b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        for _ in range(2):
            t=b.new_page();t.set_default_timeout(5000)
            # Combined initialization ensures wrapper is registered after mock.
            t.evaluate(MOCK+';'+'''(() => {const old=fetch;const ok=data=>({ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)});window.fetch=(u,o={})=>{const path=String(u).split('?')[0];if(path==='api/settings/model-preferences')return Promise.resolve(ok(o.method==='PUT'?{saved:true}:{preferences:DATA}));if(path==='api/generator/models')return Promise.resolve(ok({models:[{model_type:'prism',name:'PRISM',ready:true}]}));if(path==='api/generator/model-details')return Promise.resolve(ok({resolution_default:'832x480',resolutions:[{label:'832x480',value:'832x480'},{label:'480x832',value:'480x832'}],loras:['One'],lora_supported:true,default_loras:[],steps_default:12,sliding_window_supported:true}));return old(u,o);};})()'''.replace('DATA',json.dumps(data)))
            t.set_content(HTML,wait_until='domcontentloaded');t.wait_for_function("choices.length===1&&modelPrefsServerReady")
            t.evaluate('openGenerator()');t.wait_for_function("generatorDetails&&!generatorRestoring")
            assert t.locator('#generatorSteps').input_value()=='8'
            assert t.locator('#generatorResolution').input_value()=='480x832'
            assert t.locator('#generatorSkipGlobalLoras').is_checked()
            assert t.evaluate('collectGeneratorLoras()')==[{'name':'One','multiplier':1.5}]
            t.close()
        b.close()

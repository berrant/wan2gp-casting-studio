"""Chromium checks for large-batch UI and editable character-specific identity."""
from test_dev55_browser import page


def test_review_bulk_queuing_and_character_identity(page):
    tab, errors = page
    tab.locator('#selectProductionAll').click()
    tab.wait_for_function("document.querySelector('#productionSelectionStatus').textContent.includes('2 of 2')")
    tab.evaluate("""() => {
       window.reviewedRequests=[];window.batchSubmissions=[];window.identityWrites=[];
       const orig=window.fetch;
       window.fetch=async(url,opt={})=>{
        const path=String(url).replace(/^api\\//,'').split('?')[0];
        const response=data=>({ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)});
        if(path==='characters/identity'){
          if(opt.method==='PUT'){
            const data=JSON.parse(opt.body);window.identityWrites.push(data);
            return response({saved:true,traits:data.traits});
          }
          return response({source:'curated',traits:'Blue metallic face markings',default:'Blue metallic face markings'});
        }
        if(path==='generator/batch/preflight')return response({count:2,ready:2,blocked:0,relay_ready:true,model_type:'H3',resolution:'832x480',steps:8,loras:[],issues:[]});
        if(path==='generator/batch/preview'){
          const req=JSON.parse(opt.body);window.reviewedRequests.push(req);
          return response({review_token:"test-review",count:2,selections:2,model_type:req.task.model_type,tasks:[
           {person:'Zoie Palmer',character:'The Android',production:'Dark Matter (2015)',scene:1,prompt:'Zoie Palmer appears in Dark Matter (2015) as The Android'},
           {person:'Alice Braga',character:'Amanda Lucas',production:'Dark Matter (2015)',scene:1,prompt:'Alice Braga appears in Dark Matter (2015) as Amanda Lucas'}
          ]});
        }
        if(path==='generator/batch/submit'){
          window.batchSubmissions.push(JSON.parse(opt.body));
          return response({id:'123456789abc',task_count:2,selections:2,state:'queued'});
        }
        return orig(url,opt);
       };
    }""")
    tab.locator('#queueProductionButton').click()
    tab.wait_for_function("document.querySelector('#generatorScope').value==='production:darkmatter'")
    tab.wait_for_function("document.querySelector('#generatorModelType').value==='h3_ref2va_pruned_checkpoint'")
    tab.locator('button[data-workspace=batch]').click()
    tab.locator('#generatorReviewBatch').click()
    tab.wait_for_function("document.querySelector('#generatorBatchStatus').textContent.includes('Ready: 2 unique')")
    assert tab.locator('#generatorSubmitBatch').is_enabled()
    assert tab.evaluate('window.reviewedRequests[0].scope')=='production:darkmatter'
    assert tab.locator('#generatorBatchManifest summary').filter(has_text='Zoie Palmer').count()==1
    assert tab.locator('#generatorBatchManifest pre').count()==2
    assert tab.locator('#generatorBatchManifest details[open]').count()==2
    tab.locator('#generatorSubmitBatch').click()
    tab.wait_for_function('window.batchSubmissions.length===1')
    assert tab.evaluate('window.batchSubmissions[0].scene_mode')=='first'
    # Scope change must invalidate the reviewed prompt manifest.
    tab.locator('#generatorScope').select_option('all')
    assert tab.locator('#generatorSubmitBatch').is_disabled()
    assert not errors,errors


def test_character_identity_editor_updates_when_switching_cast(page):
    tab, errors=page
    tab.locator('#selectProductionAll').click()
    tab.wait_for_function("document.querySelector('#productionSelectionStatus').textContent.includes('2 of 2')")
    tab.evaluate("""() => {
       const orig=window.fetch;
       window.savedTraits=[];
       window.fetch=async(url,opt={})=>{
        if(String(url).startsWith('api/characters/identity')){
          const response=data=>({ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)});
          if(opt.method==='PUT'){
            const v=JSON.parse(opt.body);window.savedTraits.push(v);
            return response({saved:true,traits:v.traits});
          }
          const key=new URLSearchParams(String(url).split('?')[1]).get('character');
          return response({source:'curated',traits:key==='The Android'?'Silver irises and polished facial pattern':'Natural face',default:''});
        }
        return orig(url,opt);
       };
    }""")
    tab.locator('#queueProductionButton').click()
    tab.wait_for_function("document.querySelector('#generatorCharacterTraits').value.length>0")
    tab.locator('button[data-workspace=identity]').click()
    assert tab.locator('#generatorCharacterPanel').is_visible()
    tab.locator('#generatorCharacterPanel summary').click() if not tab.locator('#generatorCharacterPanel').evaluate('(e)=>e.open') else None
    tab.locator('#generatorCharacterTraits').fill('Permanent luminous silver irises.')
    # Normal editing no longer requires a manual save action.
    tab.wait_for_function("window.savedTraits.length===1 && $('generatorCharacterStatus').textContent.includes('Saved automatically')")
    assert tab.evaluate('window.savedTraits[0].character')=='The Android'
    tab.locator('#generatorChoice').select_option('alicebraga|amandalucas|darkmatter')
    tab.wait_for_function("document.querySelector('#generatorCharacterTraits').value==='Natural face'")
    assert not errors,errors

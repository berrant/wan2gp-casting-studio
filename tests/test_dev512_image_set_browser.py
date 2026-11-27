"""Chromium regression: the image-set form drives real multi-job requests."""
from test_dev55_browser import page


def test_image_set_count_fields_and_single_click_multi_image_queue(page):
    tab, errors=page
    tab.locator('#selectProductionAll').click()
    tab.wait_for_function("document.querySelector('#productionSelectionStatus').textContent.includes('2 of 2')")
    tab.evaluate("""() => {
       window.testImageTemplate={image_count:5,shots:[],visual_style:'Photo studio'};
       window.testImageSubmits=[];window.testImagePreviews=[];
       const orig=window.fetch;
       const answer=(data)=>({ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)});
       window.fetch=async(url,opt={})=>{
          const path=String(url).replace(/^api\\//,'').split('?')[0];
          if(path==='prompts/image-template'){
             if(opt.method==='PUT'){window.testImageTemplate=JSON.parse(opt.body);return answer({saved:true,image_count:window.testImageTemplate.image_count})}
             return answer(window.testImageTemplate);
          }
          if(path==='generator/batch/submit'){
             window.testImageSubmits.push(JSON.parse(opt.body));
             return answer({id:'ffffffffffffffff',task_count:window.testImageTemplate.image_count,state:'queued'});
          }
          if(path==='generator/batch/preview'){
             window.testImagePreviews.push(JSON.parse(opt.body));
             return answer({count:window.testImageTemplate.image_count,selections:1,tasks:[],model_type:'h3_ref2va_pruned_checkpoint'});
          }
          return orig(url,opt);
       }
    }""")
    tab.locator('#promptModel').select_option('h3_image_pruned')
    tab.wait_for_function("document.querySelector('#imageEditBtn').style.display!=='none'")
    tab.locator('#imageEditBtn').click()
    tab.wait_for_function("document.querySelectorAll('[id^=shotWardrobe]').length===5")
    tab.locator('input[name=shotWardrobe1Mode][value=custom]').check()
    tab.locator('#shotWardrobe1').fill('EXPLICIT wardrobe first')
    tab.locator('#shotAction1').fill('EXPLICIT action first')
    tab.locator('#imageSetCount').select_option('3')
    assert tab.locator('#shotWardrobe1').input_value()=='EXPLICIT wardrobe first'
    assert tab.locator('#shotAction1').input_value()=='EXPLICIT action first'
    assert tab.locator('[id^=shotWardrobe]').count()==3
    tab.locator('input[name=shotWardrobe2Mode][value=custom]').check()
    tab.locator('#shotWardrobe2').fill('EXPLICIT wardrobe second')
    tab.locator('#shotAction2').fill('EXPLICIT action second')
    tab.locator('#shotFraming2').fill('Portrait vertical framing')
    tab.locator('#imageEditorModal').get_by_role('button',name='Save image template').click()
    tab.wait_for_function("document.querySelector('#imageEditorStatus').textContent.includes('Saved 3')")
    value=tab.evaluate('window.testImageTemplate')
    assert value['image_count']==3
    assert value['shots'][0]['wardrobe']=='EXPLICIT wardrobe first'
    assert value['shots'][1]['action']=='EXPLICIT action second'
    assert value['shots'][1]['framing']=='Portrait vertical framing'
    assert tab.locator('#promptCount').text_content()=='9'  # 3 saved casting roles x 3 images
    tab.evaluate('closeImageEditor()')
    tab.evaluate('openGenerator()')
    tab.wait_for_function("document.querySelector('#generatorModelType').value==='h3_ref2va_pruned_checkpoint'")
    assert tab.locator('#generatorSubmit').text_content().strip()=='▶ Queue 3 images & next (3 left)'
    assert tab.locator('#generatorBatchMode').input_value()=='all'
    assert 'All 3 configured images' in tab.locator('#generatorBatchMode option[value=all]').text_content()
    tab.locator('#generatorSubmit').click()
    tab.wait_for_function('window.testImageSubmits.length===1')
    req=tab.evaluate('window.testImageSubmits[0]')
    assert req['scene_mode']=='all'
    assert req['scope'].startswith('selection:')
    assert req['task']['model']=='h3_image_pruned'
    assert not errors,errors


def test_copy_wardrobe_only_preserves_other_actions(page):
    tab,errors=page
    tab.evaluate("document.querySelector('#promptModel').value='flux2_dev';showImageEditorFields({image_count:2,shots:[{wardrobe:'First',action:'Stand'},{wardrobe:'Second',action:'Kneel'}],visual_style:'Photo'})")
    tab.locator('#imageEditorModal').evaluate('(e)=>e.classList.add("open")')
    tab.locator('#shotWardrobe1').fill('Copied clothing')
    tab.evaluate("imageSetCopy('wardrobe')")
    assert tab.locator('#shotWardrobe2').input_value()=='Copied clothing'
    assert tab.locator('#shotAction2').input_value()=='Kneel'
    assert not errors,errors

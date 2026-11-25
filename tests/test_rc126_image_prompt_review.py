"""Review all image prompts directly from one queue dialog."""
from test_persona_power import tab


def setup(tab):
    tab.evaluate('''() => {
        const orig=fetch;window.edits={};window.submits=[];window.failScene=0;
        const key=t=>[t.choice_key,t.model_type,t.scene].join('|');
        const answer=(data,ok=true)=>({ok,status:ok?200:500,json:async()=>data,text:async()=>JSON.stringify(data)});
        window.fetch=async (u,o={})=>{
            const p=String(u).split('?')[0];
            if(p==='api/generator/preview'){
                const t=JSON.parse(o.body);if(t.scene===window.failScene)return answer('preview unavailable',false);
                return answer({refmod_filename:'Test.safetensors',editable_prompt:window.edits[key(t)]||'Default image prompt '+t.scene,edited:!!window.edits[key(t)]});
            }
            if(p==='api/generator/prompt-edit'){
                const {task,prompt}=JSON.parse(o.body);if(window.failSaveScene===task.scene)return answer('save failed',false);
                if(prompt===null)delete window.edits[key(task)];else window.edits[key(task)]=prompt;
                return answer({saved:prompt!==null});
            }
            if(p==='api/generator/batch/submit'){
                const r=JSON.parse(o.body);window.submits.push({request:r,edits:{...window.edits}});return answer({id:'ffff0000abcdef01',task_count:5});
            }
            return orig(u,o);
        };
        $('promptModel').value='h3_image_pruned';imageTemplateCounts.h3_image_pruned=5;
        openGenerator();
    }''')
    tab.wait_for_function("$('generatorPromptGrid').querySelectorAll('textarea').length===5&&!$('generatorSubmit').disabled")


def test_five_editable_prompts_save_before_queue(tab):
    setup(tab)
    assert tab.locator('#generatorPreviewPanel').evaluate('(e)=>e.open')
    assert tab.locator('#generatorPromptGrid textarea').evaluate_all('(els)=>els.map(e=>e.value)')==[f'Default image prompt {i}' for i in range(1,6)]
    for i in (1,3,5):
        tab.get_by_role('textbox',name=f'Image {i} final prompt',exact=True).fill(f'Unique edited prompt for image {i}')
    tab.locator('#generatorSubmit').click()
    tab.wait_for_function('window.submits.length===1')
    assert sorted(tab.evaluate('Object.values(window.submits[0].edits)'))==[f'Unique edited prompt for image {i}' for i in (1,3,5)]
    assert tab.evaluate('window.submits[0].request.scene_mode')=='all'
    tab.evaluate('previewGenerator()');tab.wait_for_function("!$('generatorSubmit').disabled")
    assert tab.get_by_role('textbox',name='Image 5 final prompt').input_value()=='Unique edited prompt for image 5'
    tab.once('dialog',lambda d:d.accept())
    tab.locator('[data-scene="3"] button').click()
    tab.wait_for_function("!$('generatorSubmit').disabled&&$('generatorPromptGrid').querySelector('[data-scene=\"3\"] textarea').value==='Default image prompt 3'")
    assert tab.get_by_role('textbox',name='Image 5 final prompt').input_value()=='Unique edited prompt for image 5'


def test_missing_preview_and_save_failure_prevent_queue(tab):
    setup(tab)
    tab.evaluate('window.failScene=4;previewGenerator()')
    tab.wait_for_function("$('generatorPreviewInfo').textContent==='Preview unavailable'")
    assert tab.locator('#generatorSubmit').is_disabled()
    assert tab.locator('#generatorSubmitNext').is_disabled()
    tab.evaluate('submitGenerator()');assert tab.evaluate('window.submits.length')==0
    tab.evaluate('window.failScene=0;previewGenerator()');tab.wait_for_function("!$('generatorSubmit').disabled")
    tab.evaluate('window.failSaveScene=4')
    tab.get_by_role('textbox',name='Image 4 final prompt').fill('An edited prompt that fails to save')
    tab.locator('#generatorSubmit').click()
    tab.wait_for_function("$('generatorStatus').textContent.includes('save failed')")
    assert tab.evaluate('window.submits.length')==0
    assert tab.get_by_role('textbox',name='Image 4 final prompt').input_value()=='An edited prompt that fails to save'
    tab.evaluate('window.failSaveScene=0');tab.locator('#generatorSubmit').click()
    tab.wait_for_function('window.submits.length===1')


def test_switching_single_image_focus_preserves_all_scene_edits(tab):
    setup(tab)
    tab.get_by_role('textbox',name='Image 2 final prompt').fill('Distinct second image edited prompt')
    tab.get_by_role('textbox',name='Image 5 final prompt').fill('Distinct fifth image edited prompt')
    tab.locator('#generatorScene').select_option('5')
    tab.wait_for_function("!$('generatorSubmit').disabled&&$('generatorFocusedLabel').textContent==='Image 5'")
    assert tab.locator('#generatorPreview').input_value()=='Distinct fifth image edited prompt'
    assert tab.get_by_role('textbox',name='Image 2 final prompt').input_value()=='Distinct second image edited prompt'
    assert tab.locator('#generatorPromptGrid textarea').evaluate_all('(els)=>els.map(e=>e.getAttribute("aria-label"))')==[f'Image {i} final prompt' for i in range(1,6)]

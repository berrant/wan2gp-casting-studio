"""Fault-injection regressions found during RC12.6 UX review."""
from test_rc126_image_prompt_review import tab,setup


def batch_mock(tab, delayed=False):
    tab.evaluate('''(delayed) => {
      const orig=fetch;window.batchPreviewWaiting=false;
      const ok=data=>({ok:true,json:async()=>data,text:async()=>JSON.stringify(data)});
      window.fetch=async(u,o={})=>{
        if(String(u)==='api/generator/batch/preflight')return ok({count:1,ready:1,blocked:0,relay_ready:true,issues:[],loras:[]});
        if(String(u)==='api/generator/batch/preview'){
          if(delayed){window.batchPreviewWaiting=true;await new Promise(r=>window.releaseBatchPreview=r)}
          return ok({count:1,selections:1,tasks:[{person:'Example',character:'Example Role',scene:1,kind:'image',prompt:'Old reviewed prompt'}]});
        }
        return orig(u,o);
      };
    }''',delayed)


def test_changed_prompt_cannot_reapprove_stale_inflight_batch(tab):
    setup(tab);batch_mock(tab,True)
    tab.evaluate('window.reviewPromise=reviewGeneratorBatch();null')
    tab.wait_for_function('window.batchPreviewWaiting')
    tab.get_by_role('textbox',name='Image 2 final prompt').fill('New draft while batch preview in flight')
    tab.evaluate('window.releaseBatchPreview();window.reviewPromise')
    assert tab.locator('#generatorSubmitBatch').is_disabled()
    assert tab.locator('#generatorBatchManifest').text_content()==''


def test_invalidated_batch_clears_old_manifest(tab):
    setup(tab);batch_mock(tab)
    tab.evaluate('reviewGeneratorBatch()')
    assert 'Old reviewed prompt' in tab.locator('#generatorBatchManifest').text_content()
    tab.evaluate('invalidateGeneratorBatch()')
    assert tab.locator('#generatorBatchManifest').text_content()==''
    assert tab.locator('#generatorBatchCount').text_content()==''
    assert tab.locator('#generatorSubmitBatch').is_disabled()


def test_failed_reset_preserves_unsaved_draft(tab):
    setup(tab)
    tab.evaluate('''() => {
      window.confirm=()=>true;window.failSaveScene=3;
      const card=$('generatorPromptGrid').querySelector('[data-scene="3"]');
      const field=card.querySelector('textarea');field.value='Keep this unsaved draft';field.dispatchEvent(new Event('input'));
      card.querySelector('button').click();
    }''')
    tab.wait_for_function("$('generatorPromptSaveStatus').textContent.includes('Reset failed')")
    assert tab.evaluate('Array.from(promptEditPending.values()).some(x=>x.prompt==="Keep this unsaved draft")')
    assert not tab.locator('#generatorDiscardDraft').evaluate('e=>e.hidden')
    tab.evaluate('window.failSaveScene=0;savePromptNow()')
    assert 'Keep this unsaved draft' in tab.evaluate('Object.values(window.edits)')


def test_individual_prompt_status_tracks_successful_save(tab):
    setup(tab)
    tab.get_by_role('textbox',name='Image 2 final prompt').fill('Revised second image')
    tab.evaluate('savePromptNow()')
    assert tab.locator('[data-scene="2"] header .note').text_content()=='Custom prompt saved'


def test_queue_waits_for_prompt_reset_to_finish(tab):
    setup(tab)
    tab.evaluate('''() => {
      const orig=fetch;window.confirm=()=>true;window.resetWaiting=false;
      window.fetch=async(u,o={})=>{
        if(String(u)==='api/generator/prompt-edit'&&JSON.parse(o.body).prompt===null){window.resetWaiting=true;await new Promise(r=>window.releaseReset=r)}
        return orig(u,o);
      };
      $('generatorPromptGrid').querySelector('[data-scene="3"] button').click();
    }''')
    tab.wait_for_function('window.resetWaiting')
    assert tab.locator('#generatorSubmit').is_disabled()
    assert tab.locator('#generatorSubmitNext').is_disabled()
    tab.evaluate('window.releaseReset()')
    tab.wait_for_function("!$('generatorSubmit').disabled")
    assert not tab.evaluate('window.submits.length')

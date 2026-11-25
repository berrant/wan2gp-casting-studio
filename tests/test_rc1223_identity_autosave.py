"""Manual appearance autosave must not cross portrayals or approve AI drafts."""
from test_dev55_browser import page
from test_rc1223_appearance_navigation import MOCK

MOCK_SAVE = '''()=>{const prior=fetch;window.identityWrites=[];window.failSave=false;window.pauseSave=false;window.releaseSave=null;window.fetch=async(u,o={})=>{if(String(u).startsWith('api/characters/identity')){const json=d=>({ok:true,json:async()=>d,text:async()=>JSON.stringify(d)});if(o.method==='PUT'){const body=JSON.parse(o.body);identityWrites.push(body);if(pauseSave)await new Promise(resolve=>releaseSave=resolve);if(failSave)return {ok:false,status:503,text:async()=> 'Offline'};return json({saved:true,traits:body.traits});}return json({traits:'Original traits',source:'custom'});}return prior(u,o);};}'''


def setup(page, scope):
    tab,errors=page
    tab.evaluate(MOCK)
    tab.evaluate(MOCK_SAVE)
    tab.evaluate('''scope=>{if(scope==='card'){cardIdentityOriginal='Original traits';$('cardIdentityTraits').value=cardIdentityOriginal;return;}$('cardIdentityModal').classList.remove('open');if(scope==='image'){$('imageEditorModal').classList.add('open');showImageEditorFields({image_count:1,shots:[]});const picker=$('imageIdentityChoice');picker.replaceChildren(new Option('First','a'),new Option('Second','b'));picker.value='a';return loadImageSetIdentity();}const picker=$('generatorChoice');picker.replaceChildren(new Option('First','a'),new Option('Second','b'));picker.value='a';return loadGeneratorCharacterIdentity();}''',scope)
    return tab,errors


def test_card_autosave_debounced_and_flush_on_close(page):
    tab,errors=setup(page,'card')
    tab.locator('#cardIdentityTraits').fill('First draft')
    tab.locator('#cardIdentityTraits').fill('Final traits')
    tab.wait_for_function("identityWrites.length===1 && $('cardIdentityStatus').textContent.includes('Saved automatically')")
    assert tab.evaluate('identityWrites[0].traits')=='Final traits'
    tab.locator('#cardIdentityTraits').fill('Closing draft')
    tab.locator('#cardIdentityModal button.modal-pinned-close').click()
    tab.wait_for_function("!$('cardIdentityModal').classList.contains('open')")
    assert tab.evaluate('identityWrites.at(-1).traits')=='Closing draft'
    assert not errors,errors


def test_failed_autosave_blocks_close_and_preserves_draft(page):
    tab,errors=setup(page,'card')
    tab.evaluate('failSave=true')
    tab.locator('#cardIdentityTraits').fill('Retain this edit')
    tab.wait_for_function("$('cardIdentityStatus').textContent.includes('not saved')")
    tab.locator('#cardIdentityModal button.modal-pinned-close').click()
    tab.wait_for_function("!identityAutosave.card.pending")
    assert tab.locator('#cardIdentityModal').is_visible()
    assert tab.locator('#cardIdentityTraits').input_value()=='Retain this edit'
    tab.evaluate('failSave=false')
    tab.locator('#cardIdentitySave').click()
    tab.wait_for_function("$('cardIdentityStatus').textContent.includes('Saved automatically')")
    tab.locator('#cardIdentityModal button.modal-pinned-close').click()
    assert not tab.locator('#cardIdentityModal').is_visible()
    assert not errors,errors


def test_empty_draft_does_not_delete_profile(page):
    tab,errors=setup(page,'card')
    tab.locator('#cardIdentityTraits').fill('')
    tab.wait_for_function("$('cardIdentityStatus').textContent.includes('Empty draft')")
    assert tab.evaluate('identityWrites.length')==0
    tab.locator('#cardIdentityTraits').fill('New traits')
    tab.wait_for_function('identityWrites.length===1')
    assert tab.evaluate('identityWrites[0].traits')=='New traits'
    assert not errors,errors


def test_image_switch_flushes_to_old_portrayal(page):
    tab,errors=setup(page,'image')
    tab.locator('#imageIdentityTraits').fill('First character edit')
    tab.locator('#imageIdentityChoice').select_option('b')
    tab.wait_for_function("imageIdentityLoaded==='b' && !imageIdentityBusy")
    assert tab.evaluate('identityWrites')==[{'person':'Ada Test','character':'First Alien','production':'Example','year':2023,'traits':'First character edit'}]
    assert tab.locator('#imageIdentityTraits').input_value()=='Original traits'
    assert not errors,errors


def test_generator_switch_flushes_to_old_portrayal(page):
    tab,errors=setup(page,'generator')
    tab.evaluate("$('generatorCharacterTraits').value='Video character edit';$('generatorCharacterTraits').dispatchEvent(new Event('input'));$('generatorChoice').value='b';generatorChoiceChanged()")
    tab.wait_for_function("generatorIdentityRole?.key==='b' && !characterIdentityPending")
    assert tab.evaluate('identityWrites')==[{'person':'Ada Test','character':'First Alien','production':'Example','year':2023,'traits':'Video character edit'}]
    assert not errors,errors


def test_inflight_newer_edit_not_overwritten_and_ai_waits(page):
    tab,errors=setup(page,'card')
    tab.evaluate('pauseSave=true')
    tab.locator('#cardIdentityTraits').fill('First write')
    tab.wait_for_function('!!releaseSave')
    tab.locator('#cardIdentityTraits').fill('Newest write')
    tab.locator('#cardIdentityAI').click()
    assert not tab.locator('#appearanceModal').is_visible()
    tab.evaluate('pauseSave=false;releaseSave()')
    tab.wait_for_function("$('appearanceModal').classList.contains('open') && !appearanceBusy")
    assert tab.evaluate('identityWrites.map(x=>x.traits)')==['First write','Newest write']
    assert tab.locator('#cardIdentityTraits').input_value()=='Newest write'
    assert not errors,errors

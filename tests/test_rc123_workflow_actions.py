"""Additional browser coverage for RC12.3 workflow controls."""
from test_persona_power import tab
from test_dev55_browser import page


def test_basic_mode_single_image_uses_one_submit(tab):
    tab.evaluate("$('promptModel').value='h3_image_pruned';setUXMode(true);openGenerator()")
    tab.wait_for_function('!!generatorDetails&&!generatorRequestInProgress&&!$("uxSingleJob").disabled')
    tab.locator('#uxSingleJob').click()
    tab.wait_for_function('window.responses.length===1')
    assert tab.evaluate('window.responses[0].model')=='h3_image_pruned'
    assert tab.evaluate('window.responses[0].scene')==1


def test_production_removal_is_undoable(page):
    tab,errors=page
    tab.locator('#selectProductionAll').click()
    tab.wait_for_function("document.querySelector('#productionSelectionStatus').textContent.includes('2 of 2')")
    tab.once('dialog',lambda d:d.accept())
    tab.locator('#clearProductionSelections').click()
    tab.wait_for_function("document.querySelector('#productionSelectionStatus').textContent.includes('0 of 2')")
    assert len(tab.evaluate('window.mockChoices'))==1
    tab.locator('#uxUndo').click()
    tab.wait_for_function('window.mockChoices.length===3')
    assert '2 of 2' in tab.locator('#productionSelectionStatus').text_content()
    assert not errors,errors


def test_keyboard_shortcut_does_not_intercept_editing(tab):
    tab.evaluate('openGenerator()');tab.wait_for_function('!!generatorDetails&&!generatorRequestInProgress&&!$("generatorSubmitNext").disabled')
    tab.evaluate("$('generatorPreviewPanel').open=true")
    tab.locator('#generatorPreview').focus();tab.keyboard.press('Alt+n')
    assert tab.evaluate('window.responses.length')==0
    tab.locator('#generatorSubmitNext').focus();tab.keyboard.press('Alt+n')
    tab.wait_for_function('window.responses.length===1')


def test_history_only_offers_explicit_retries(tab):
    tab.evaluate("""() => {const orig=fetch;window.fetch=(u,o)=>String(u)==='api/generator/history'?Promise.resolve({ok:true,json:async()=>({jobs:[{id:'synthetic-failed',state:'failed',retry_count:2,task_count:3,output_count:1,updated:0,settings:{steps:8}},{id:'synthetic-cancelled',state:'cancelled',retry_count:0,task_count:1,updated:0}]})}):orig(u,o)}""")
    tab.evaluate('openUXHistory()');tab.wait_for_function('$("uxHistoryRows").children.length===2')
    assert tab.locator('#uxHistoryRows button').count()==1
    assert 'Retry 2 confirmed failed' in tab.locator('#uxHistoryRows button').inner_text()

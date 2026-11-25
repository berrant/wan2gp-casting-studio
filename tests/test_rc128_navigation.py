"""Public cast identity navigation, including missing references and retained choices."""
from test_dev55_browser import page


def test_cast_to_exact_people_and_back(page):
    tab,errors=page
    tab.locator('#productionCast .cast-row').nth(0).get_by_role('button',name='Select',exact=True).click()
    tab.wait_for_function("choices.some(c=>c.person==='Zoie Palmer')")
    tab.locator('#productionCast').get_by_role('button',name='Zoie Palmer',exact=True).click()
    assert tab.evaluate('activeTab')=='performers'
    assert tab.locator('#list article.card').count()==1
    assert tab.locator('#list h2').inner_text().startswith('Zoie Palmer')
    assert tab.locator('#list .role button.selected').count()==1
    tab.locator('#list .role').get_by_role('button',name='Dark Matter',exact=True).click()
    tab.wait_for_function("activeTab==='productions' && activeProduction==='Dark Matter' && document.querySelector('#productionCast').textContent.includes('Zoie Palmer')")
    assert len(tab.evaluate('choices'))==2
    assert not errors,errors


def test_missing_refmod_direct_profile_and_clear(page):
    tab,errors=page
    tab.locator('#productionCast').get_by_role('button',name='Missing',exact=True).click()
    assert tab.locator('#list article.card').count()==1
    assert tab.locator('#list h2').inner_text().startswith('Missing')
    assert 'RefMod missing' in tab.locator('#list').inner_text()
    assert tab.locator('#list .role').get_by_role('button',name='Collect reference photos').count()==1
    assert tab.locator('#list .role').get_by_role('button',name='+ Choose').count()==0
    tab.locator('#list .role').get_by_role('button',name='Dark Matter',exact=True).click()
    tab.wait_for_function("activeTab==='productions' && activeProduction==='Dark Matter' && document.querySelector('#productionCast').textContent.includes('Missing Character')")
    tab.locator('#productionCast').get_by_role('button',name='Missing',exact=True).click()
    tab.locator('#browseSection').get_by_role('button',name='Clear',exact=True).click()
    assert tab.locator('#list article.card').count()==3
    assert not errors,errors


def test_monitor_navigation_never_links_private_identity(page):
    tab,errors=page
    tab.evaluate("$('monitorToggle').open=true;renderMonitorDetails({person:'Zoie Palmer',character:'The Android',production:'Dark Matter'},true)")
    tab.locator('#monitorPerson').get_by_role('button',name='Zoie Palmer').click()
    assert tab.evaluate('activeTab')=='performers'
    tab.evaluate("renderMonitorDetails({person:'Private profile',production:'Private',personal:true},true)")
    assert tab.locator('#monitorPerson button').count()==0
    assert tab.locator('#monitorProduction button').count()==0
    tab.evaluate("renderMonitorDetails(null,true)")
    assert tab.locator('#monitorPerson').inner_text()=='Identity unavailable'
    assert not errors,errors

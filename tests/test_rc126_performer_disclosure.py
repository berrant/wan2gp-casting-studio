"""Performer role disclosure is local UI state, independent of casting choices."""
from test_dev55_browser import page


def card(tab,name):
    return tab.locator('#list article.card').filter(has=tab.get_by_role('heading',name=name,exact=False))


def test_collapsed_by_default_independent_and_preserved(page):
    tab,errors=page
    tab.evaluate("showTab('performers')")
    zoie=card(tab,'Zoie Palmer');alice=card(tab,'Alice Braga')
    assert tab.locator('#list .role').count()==0
    z=zoie.locator('.performer-roles-toggle');a=alice.locator('.performer-roles-toggle')
    assert z.get_attribute('aria-expanded')=='false'
    assert '1 role' in z.inner_text()
    z.click()
    assert z.get_attribute('aria-expanded')=='true'
    assert zoie.locator('.role').count()==1
    assert a.get_attribute('aria-expanded')=='false'
    assert alice.locator('.role').count()==0
    assert z.evaluate('e=>document.activeElement===e')
    a.click()
    assert zoie.locator('.role').count()==1 and alice.locator('.role').count()==1
    zoie.get_by_role('button',name='+ Choose',exact=True).click()
    tab.wait_for_function("choices.some(c=>c.person==='Zoie Palmer')")
    assert '1 selected' in z.inner_text()
    assert zoie.locator('.role button.selected').count()==1
    z.click()
    assert zoie.locator('.role').count()==0 and '1 selected' in z.inner_text()
    assert alice.locator('.role').count()==1
    tab.evaluate('render()')
    z.click()
    assert zoie.locator('.role button.selected').count()==1
    assert not errors,errors


def test_role_search_reveals_matches_and_retains_browsing_state(page):
    tab,errors=page
    tab.evaluate("showTab('performers')")
    zoie=card(tab,'Zoie Palmer');alice=card(tab,'Alice Braga')
    alice.locator('.performer-roles-toggle').click()
    tab.locator('#search').fill('The Android')
    tab.wait_for_function("document.querySelector('#list .role')?.textContent.includes('The Android')")
    assert zoie.locator('.performer-roles-toggle').get_attribute('aria-expanded')=='true'
    zoie.locator('.performer-roles-toggle').click()
    assert zoie.locator('.role').count()==0
    tab.locator('#search').fill('')
    tab.wait_for_function("document.querySelectorAll('#list article.card').length===3")
    assert alice.locator('.role').count()==1
    assert zoie.locator('.role').count()==0
    assert not errors,errors


def test_expand_does_not_start_research(page):
    tab,errors=page
    tab.evaluate("showTab('performers');window.disclosureRequests=[];const oldDisclosureFetch=fetch;window.fetch=(u,o)=>{disclosureRequests.push(String(u));return oldDisclosureFetch(u,o)}")
    card(tab,'Zoie Palmer').locator('.performer-roles-toggle').press('Enter')
    assert card(tab,'Zoie Palmer').locator('.role').count()==1
    assert tab.evaluate("disclosureRequests.filter(u=>/credits\\/refresh|images\\/search|profiles\\/link|prefetch\\/start/.test(u))")==[]
    assert not errors,errors

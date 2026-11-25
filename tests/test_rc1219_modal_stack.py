"""Live-reported nested collector stacking; real pointer and keyboard events."""
from test_dev55_browser import page
from test_rc1217_collection import open_test


def top_at(tab, selector):
    return tab.locator(selector).evaluate('''e=>{const r=e.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.closest('.modal')?.id}''')


def test_card_analysis_collection_is_clickable_over_parent(page):
    tab,errors=open_test(page)
    tab.keyboard.press('Escape')
    tab.evaluate("openCardIdentity('Ada Test',{character:'Alien',production:'Example',year:2023})")
    tab.wait_for_function('!cardIdentityBusy && !!cardIdentityRole')
    tab.locator('#cardIdentityAI').click()
    tab.wait_for_function('!appearanceBusy && appearanceLoaded.length===1')
    tab.locator('#appearanceEngine').select_option('4')
    tab.evaluate("$('appearanceResults').append(Object.assign(document.createElement('textarea'),{value:'unsaved draft'}))")
    for _ in range(2):
        tab.get_by_role('button',name='Collect more character images').click()
        assert tab.locator('#cardIdentityModal').is_visible()
        assert not tab.locator('#appearanceModal').is_visible()
        button=tab.get_by_role('button',name='Return to AI analysis')
        button.scroll_into_view_if_needed()
        assert top_at(tab,'#appearanceCollectionReturn button')=='modal'
        button.click()
        tab.wait_for_function('!appearanceBusy && !appearanceCollection')
        assert tab.locator('#appearanceEngine').input_value()=='4'
        assert tab.locator('#appearanceResults textarea').input_value()=='unsaved draft'
    tab.keyboard.press('Escape')
    assert tab.locator('#cardIdentityModal').is_visible()
    assert not tab.locator('#appearanceModal').is_visible()
    assert not errors,errors


def test_nested_lightbox_and_escape_follow_visible_order(page):
    tab,errors=open_test(page)
    tab.get_by_role('button',name='Inspect Portrait').click()
    assert top_at(tab,'#lightboxActual')=='photoLightbox'
    tab.locator('#lightboxActual').click()
    tab.keyboard.press('Escape')
    assert not tab.locator('#photoLightbox').is_visible()
    assert tab.locator('#appearanceModal').is_visible()
    assert top_at(tab,'#appearanceStart')=='appearanceModal'
    tab.keyboard.press('Escape')
    assert not tab.locator('#appearanceModal').is_visible()
    assert not errors,errors


def test_responsive_collector_close_restores_analysis_not_parent(page):
    tab,errors=open_test(page)
    tab.keyboard.press('Escape')
    tab.evaluate("openCardIdentity('Ada Test',{character:'Alien',production:'Example',year:2023})")
    tab.wait_for_function('!cardIdentityBusy && !!cardIdentityRole')
    tab.locator('#cardIdentityAI').click()
    tab.wait_for_function('!appearanceBusy && appearanceLoaded.length===1')
    tab.set_viewport_size({'width':420,'height':800})
    tab.get_by_role('button',name='Collect more character images').click()
    close=tab.locator('#modal .modal-pinned-close')
    close.scroll_into_view_if_needed()
    assert top_at(tab,'#modal .modal-pinned-close')=='modal'
    tab.evaluate('appearanceCollectionMutations=1')
    close.click()
    assert tab.locator('#modal').is_visible()
    assert not tab.locator('#appearanceModal').is_visible()
    tab.evaluate('appearanceCollectionMutations=0')
    close.click()
    tab.wait_for_function('!appearanceBusy && !appearanceCollection')
    assert tab.locator('#appearanceModal').is_visible()
    assert tab.locator('#cardIdentityModal').is_visible()
    assert not tab.locator('#modal').is_visible()
    assert tab.locator('#modal').evaluate('e=>e.style.zIndex')==''
    tab.get_by_role('button',name='Inspect Portrait').click()
    tab.keyboard.press('Escape')
    assert tab.locator('#appearanceModal').is_visible()
    assert tab.locator('#cardIdentityModal').is_visible()
    assert not errors,errors

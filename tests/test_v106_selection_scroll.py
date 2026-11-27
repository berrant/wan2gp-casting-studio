"""Selecting roles in a long performer card must preserve browsing context."""
from test_dev55_browser import page
from playwright.sync_api import expect


def test_long_performer_selection_keeps_scroll_focus_and_disclosure(page):
    tab, errors = page
    tab.evaluate('''() => {
      const name='Synthetic Long Filmography';
      catalog={...catalog,people:[{name,type:'Actor'}],models:[{name,path:'Synthetic_Long_H3.safetensors',family:'minimax_h3'}],roles:Array.from({length:32},(_,i)=>({actress:name,character:'Role '+String(i).padStart(2,'0'),production:'Synthetic Show',year:2020}))};
      showTab('performers');$('search').value=name;render();
    }''')
    tab.locator('#list .performer-roles-toggle').click()
    role=tab.locator('#list .role').filter(has_text='Role 24')
    role.scroll_into_view_if_needed()
    role.locator('summary').click()
    button=role.get_by_role('button',name='+ Choose',exact=True)
    button.scroll_into_view_if_needed()
    tab.evaluate('''() => {window.beforeRole=[...document.querySelectorAll('#list .role')].find(e=>e.innerText.includes('Role 24'));window.beforeY=window.scrollY;}''')
    assert tab.evaluate('beforeY')>500
    button.click()
    expect(role.get_by_role('button',name='✓ Selected',exact=True)).to_be_visible()
    assert tab.evaluate('beforeRole.isConnected'), 'Selecting a role replaced the existing card'
    assert abs(tab.evaluate('window.scrollY-beforeY'))<25
    assert role.locator('details').evaluate('e=>e.open')
    assert role.get_by_role('button',name='✓ Selected',exact=True).evaluate('e=>e===document.activeElement')
    expect(tab.locator('#list .role-selection-count')).to_have_text('1 selected')
    role.get_by_role('button',name='✓ Selected',exact=True).click()
    expect(button).to_be_visible()
    assert tab.evaluate('beforeRole.isConnected')
    assert abs(tab.evaluate('window.scrollY-beforeY'))<25
    assert role.locator('details').evaluate('e=>e.open')
    assert not errors,errors


def test_research_status_shows_persisted_history_after_restart(page):
    tab, errors=page
    tab.evaluate('''() => {const base=fetch;window.fetch=async (u,o={})=>{
      if(u==='api/credits/status')return {ok:true,json:async()=>({running:false,total:0,done:0,added:0,failed:0,history:{ok:{performers:13,credits:140},error:{performers:1,credits:0}}})};
      if(u==='api/enrichment/status')return {ok:true,json:async()=>({running:false,total:0,done:0,recorded_errors:0,history:{matched:9,ambiguous:2,unmatched:3}})};
      return base(u,o);
    }}''')
    tab.evaluate('Promise.all([pollCredits(),enrichmentStatus()])')
    expect(tab.locator('#creditsStatus')).to_contain_text('13 successful, 1 failed, 140 discovered credits')
    expect(tab.locator('#creditsStatus')).to_contain_text('7-day successful / 12-hour failed cooldown')
    expect(tab.locator('#enrichStatus')).to_contain_text('9 matched, 2 ambiguous, 3 unmatched (14 total)')
    assert not errors,errors


def test_variant_selection_and_removal_keep_existing_role_controls(page):
    tab,errors=page
    tab.evaluate('''() => {
      const name='Synthetic Variant Performer';
      catalog={...catalog,people:[{name,type:'Actor'}],models:['Variant A','Variant B'].map(x=>({name,path:x+'.safetensors',family:'minimax_h3'})),roles:[{actress:name,character:'Variant Role',production:'Synthetic Show'}]};
      showTab('performers');$('search').value=name;render();
    }''')
    tab.locator('#list .performer-roles-toggle').click()
    role=tab.locator('#list .role')
    picker=role.locator('select')
    tab.evaluate('window.originalPicker=document.querySelector("#list .role select")')
    picker.select_option('Variant B.safetensors')
    expect(role.locator('[data-performer-choice]')).to_have_text('✓ Selected')
    assert picker.input_value()=='Variant B.safetensors'
    assert tab.evaluate('originalPicker.isConnected')
    role.locator('[data-performer-choice]').click()
    expect(role.locator('[data-performer-choice]')).to_have_text('+ Choose')
    assert picker.input_value()==''
    assert tab.evaluate('originalPicker.isConnected')
    assert not errors,errors

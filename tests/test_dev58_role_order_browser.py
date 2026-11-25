"""Prominent/known credits win over newest-first actor role sorting."""
from test_dev55_browser import page


def test_highlighted_actor_roles_appear_before_new_minor_credit(page):
    tab, errors = page
    tab.evaluate("""() => {
      catalog.models.push({name:'Kate Mara',path:'Kate_Mara_H3.safetensors',family:'minimax_h3'});
      catalog.people.push({name:'Kate Mara',type:'Actor',credits:[
         'House of Cards','American Horror Story','A Teacher','Fantastic Four'
      ]});
      catalog.roles.push(
        {actress:'Kate Mara',character:'Recent minor cameo',production:'New Series',year:2026},
        {actress:'Kate Mara',character:'Sue Storm',production:'Fantastic Four',year:2015},
        {actress:'Kate Mara',character:'Claire Wilson',production:'A Teacher',year:2020},
        {actress:'Kate Mara',character:'Hayden McClaine',production:'American Horror Story',year:2011},
        {actress:'Kate Mara',character:'Zoe Barnes',production:'House of Cards (2013)',year:2013}
      );
      showTab('performers');$('search').value='Kate Mara';render();
    }""")
    tab.wait_for_function("document.querySelector('#list').textContent.includes('Zoe Barnes')")
    got=tab.locator('#list article.card .role .details strong').all_text_contents()
    assert got==['Zoe Barnes','Hayden McClaine','Claire Wilson','Sue Storm','Recent minor cameo'],got
    # Actor name search should show all relevant roles, but searching a particular
    # production should still narrow results to that title only.
    tab.locator('#search').fill('New Series')
    got=tab.locator('#list article.card .role .details strong').all_text_contents()
    assert got==['Recent minor cameo'],got
    assert not errors,errors


def test_role_sort_is_stable_when_no_highlighted_credits(page):
    tab, errors=page
    result=tab.evaluate("""() => sortPerformerRoles([
       {production:'Older',character:'Main Character',year:2014},
       {production:'Newest',character:'Cameo',year:2022},
       {production:'Middle',character:'Friend',year:2019}
    ],{credits:[]}).map(r=>r.production)""")
    assert result==['Newest','Middle','Older']
    assert not errors,errors

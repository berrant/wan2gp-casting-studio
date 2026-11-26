"""Local classification compatibility and visible source attribution."""
from test_native_plugin import installation
from test_dev55_browser import page
API='/casting-studio/api'


def test_old_marker_and_multicategory_edit_are_compatible(installation):
    c,*_=installation
    name='Ada Test'
    assert c.put(API+'/profiles/markers',json={'name':name,'adult':True}).status_code==200
    assert c.put(API+'/profiles/categories',json={'name':name,'categories':['Actor']}).status_code==200
    assert c.get(API+'/profiles/markers').json()[name] is True
    assert c.put(API+'/profiles/categories',json={'name':name,'categories':['Actor','Musician'],'adult':True}).status_code==200
    assert c.get(API+'/profiles/categories').json()[name]==['Actor','Musician']
    assert c.get(API+'/profiles/markers').json()[name] is True
    assert c.put(API+'/profiles/categories',json={'name':name,'categories':['Unknown'],'adult':False}).status_code==400
    assert c.get(API+'/profiles/markers').json()[name] is True
    assert c.put(API+'/profiles/categories',json={'name':name,'categories':['Actor','Musician'],'adult':False}).status_code==200
    assert name not in c.get(API+'/profiles/markers').json()
    assert c.get(API+'/profiles/categories').json()[name]==['Actor','Musician']


def test_private_profile_cannot_be_given_public_classification(installation):
    c,*_=installation
    name='Private Synthetic'
    assert c.post(API+'/personal',json={'name':name}).status_code==200
    assert c.put(API+'/profiles/categories',json={'name':name,'categories':['Actor'],'adult':True}).status_code==403
    assert name not in c.get(API+'/profiles/markers').json()
    assert name not in c.get(API+'/profiles/categories').json()


def test_classification_editor_preserves_crossover_and_legacy_navigation(page):
    tab,errors=page
    tab.evaluate('''() => {
      const old=fetch;window.savedCategory=null;
      window.fetch=async(u,o={})=>{if(u==='api/profiles/categories'&&o.method==='PUT'){savedCategory=JSON.parse(o.body);return {ok:true}}return old(u,o)};
      catalog={...catalog,people:[{name:'Synthetic Performer',type:'Actor'}],roles:[],models:[{name:'Synthetic Performer',path:'Synthetic_Performer_H3.safetensors',family:'minimax_h3'}]};performerIndexSnapshot=null;profileTypes['Synthetic Performer']=['Actor'];adultMarkers[canon('Synthetic Performer')]=true;
      showTab('adult');render();
    }''')
    assert tab.evaluate('activeTab')=='performers'
    assert tab.locator('#peopleMenu [data-people-category="adult"]').count()==0
    assert tab.locator('#filter').input_value()=='adult'
    card=tab.locator('#list article').filter(has_text='Synthetic Performer')
    assert 'Actor / Adult Entertainer' in card.inner_text()
    card.get_by_role('button',name='Edit categories').click()
    modal=tab.locator('#categoryModal')
    assert modal.get_by_label('Actor',exact=True).is_checked()
    assert modal.get_by_label('Adult Entertainer',exact=True).is_checked()
    modal.get_by_label('Musician',exact=True).check()
    modal.get_by_label('Adult Entertainer',exact=True).uncheck()
    modal.get_by_role('button',name='Save categories').click()
    tab.wait_for_function('savedCategory!==null && !$("categoryModal").classList.contains("open")')
    assert tab.evaluate('savedCategory')=={'name':'Synthetic Performer','categories':['Actor','Musician'],'adult':False}
    assert tab.locator('#list article').count()==0
    tab.locator('#filter').select_option('all')
    # The performer list uses content-visibility:auto. A newly inserted card
    # may not have completed its first layout/paint after the filter changes.
    from playwright.sync_api import expect
    card=tab.locator('#list article').filter(has_text='Synthetic Performer')
    card.scroll_into_view_if_needed()
    expect(card).to_be_visible()
    expect(card).to_contain_text('Actor / Musician',use_inner_text=True)
    assert not errors,errors


def test_provider_attribution_in_application(page):
    tab,errors=page
    tab.evaluate("$('aboutModal').classList.add('open')")
    dialog=tab.locator('#aboutModal')
    for name,url in [('TVMaze','https://www.tvmaze.com/api'),('Wikipedia reuse terms','https://en.wikipedia.org/wiki/Wikipedia:Reusing_Wikipedia_content'),('Wikidata licensing','https://www.wikidata.org/wiki/Wikidata:Licensing')]:
        a=dialog.get_by_role('link',name=name,exact=True)
        assert a.is_visible() and a.get_attribute('href')==url
        assert a.get_attribute('rel')=='noopener noreferrer'
    assert not errors,errors

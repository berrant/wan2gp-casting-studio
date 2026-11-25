"""Character-only collection round trips; no real network or GPU."""
from test_rc1213_appearance import app, stage
from test_native_plugin import installation
from test_dev55_browser import page
from PIL import Image


def test_character_metadata_and_portrayal_year_separation(app):
    c,p,s,b,n,roles=app
    with s.connect() as db:
        db.execute("UPDATE reference_images SET source_url='local-upload:1',quality_notes='Manual review' WHERE id='1'")
        for ident,prod,char in [('3','Example Series (2024)','Example Alien 1'),('4','Example Series (2023)',''),('5','Example Series','Example Alien 1')]:
            filename=f'{int(ident):024x}.jpg';Image.new('RGB',(640,800),'blue').save(s.REFERENCE_DIR/filename)
            db.execute('INSERT INTO reference_images (id,person,production,character,source_url,page_url,filename,width,height,quality_status) VALUES (?,?,?,?,?,?,?,?,?,?)',(ident,'Ada Test',prod,char,'https://example.org/photo','https://example.org/page',filename,640,800,'passed'))
        filename='a'*64+'.jpg';Image.new('RGB',(240,320),'green').save(s.PHOTO_DIR/filename)
        db.execute('INSERT INTO images (key,url) VALUES (?,?)',('role|'+roles[0]['choice_key'],'api/photos/'+filename))
    photos=c.get(p+'/appearance/references',params={'choice_key':roles[0]['choice_key']}).json()['photos']
    assert [x['id'] for x in photos][0]=='portrait'
    assert {x['id'] for x in photos}=={'portrait','1','5'}
    assert photos[0]['low_resolution'] and photos[0]['width']==240
    byid={x['id']:x for x in photos};assert byid['1']['source']=='Local upload' and byid['1']['quality_notes']=='Manual review'
    assert byid['5']['source']=='Collected from example.org' and not byid['5']['dated']
    assert 'path' not in byid['1']
    collection=c.get(p+'/reference-images',params={'person':'Ada Test','production':'Example Series (2023)','character':'Example Alien 1'}).json()
    assert {x['id'] for x in collection}=={'1','5'}
    assert '3' not in {x[0] for x in s.same_reference_collection('Ada Test','Example Series (2023)','Example Alien 1')}
    assert stage(app,[{**roles[0],'image_ids':['3']}]).status_code==400
    assert n.loads==0

MOCK='''()=>{window.collectionCalls=[];window.refreshFail=false;window.photosForTest=[{id:'portrait',label:'Portrait',source:'Local character portrait',width:200,height:300,low_resolution:true,dated:false,url:'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'}];const orig=fetch;window.fetch=async(u,o={})=>{const url=String(u);const json=d=>({ok:true,json:async()=>d,text:async()=>JSON.stringify(d)});if(url==='api/appearance/options')return json({ready:true,default:'3',models:[{id:'3',label:'Qwen 4B',backend:'int8'},{id:'4',label:'Qwen 9B',backend:'gguf'}]});if(url==='api/choices')return json([{key:'a',person:'Ada Test',character:'Alien',production:'Example',year:2023}]);if(url.startsWith('api/appearance/references?')){if(window.refreshFail)throw Error('offline');return json({role:{label:'Alien in Example (2023)',person:'Ada Test',character:'Alien',production:'Example',year:2023,profile_key:'a2023'},photos:window.photosForTest});}if(url.startsWith('api/images/search?')){collectionCalls.push(url);return json({query:'Alien',web_search:'https://example.org',images:[],has_more:false});}if(url.startsWith('api/reference-images?')){collectionCalls.push(url);return json([]);}return orig(u,o);};openAppearance('batch');}'''

def open_test(page, empty=False):
    tab,errors=page;tab.evaluate(MOCK)
    tab.wait_for_function('!appearanceBusy && appearanceLoaded.length===1')
    if empty:tab.evaluate('photosForTest=[];renderAppearancePhotos(appearanceLoaded[0],{role:appearanceLoaded[0].role,photos:[]});appearanceControls()')
    return tab,errors

def test_collection_roundtrip_preserves_selection_engine_and_draft(page):
    tab,errors=open_test(page)
    assert tab.locator('#appearanceStart').inner_text()=='Analyze 1 character image with AI'
    assert tab.get_by_text('Warning: analysis relies solely',exact=False).is_visible()
    assert tab.get_by_text('Local character portrait · 200 × 300 px',exact=False).is_visible()
    assert tab.evaluate('collectionCalls.length')==0
    tab.get_by_role('button',name='Inspect Portrait').click()
    assert tab.locator('#photoLightbox').is_visible() and not tab.locator('#lightboxUse').is_visible()
    tab.locator('#lightboxActual').click();assert tab.locator('#lightboxImage').evaluate("e=>e.dataset.actual")=='true'
    tab.keyboard.press('Escape');assert not tab.locator('#photoLightbox').is_visible()
    tab.locator('#appearanceEngine').select_option('4')
    tab.evaluate("$('appearanceResults').append(Object.assign(document.createElement('textarea'),{value:'unsaved draft'}));appearanceJob='previous';appearanceCurrentState='completed';")
    tab.get_by_role('button',name='Collect more character images').click()
    assert tab.locator('#appearanceCollectionReturn').is_visible() and not tab.locator('#castCollectionScope').is_visible()
    assert not tab.locator('#photoWorkshopButton').is_visible()
    assert tab.evaluate("activeImage.character==='Alien' && activeImage.production==='Example (2023)'")
    tab.evaluate("photosForTest.push({...photosForTest[0],id:'new',label:'New reference',source:'Local upload',dated:true,low_resolution:false})")
    tab.get_by_role('button',name='Return to AI analysis').click()
    tab.wait_for_function('!appearanceBusy && appearanceLoaded[0].selections.length===2')
    assert tab.locator('#appearanceEngine').input_value()=='4'
    assert tab.locator('#appearanceResults textarea').input_value()=='unsaved draft'
    assert not tab.get_by_role('checkbox',name='New reference').is_checked()
    tab.get_by_role('checkbox',name='New reference').check()
    assert tab.locator('#appearanceStart').inner_text()=='Analyze 2 character images with AI'
    assert not tab.get_by_text('Warning: analysis relies solely',exact=False).is_visible()
    assert not errors,errors

def test_empty_collection_and_refresh_failure_recover(page):
    tab,errors=open_test(page,True)
    assert tab.locator('#appearanceStart').is_disabled()
    tab.get_by_role('button',name='Collect more character images').click()
    tab.evaluate('refreshFail=true')
    tab.keyboard.press('Escape')
    tab.wait_for_function('!appearanceBusy && !appearanceCollection')
    assert 'Could not refresh' in tab.locator('#appearanceStatus').inner_text()
    assert tab.locator('#appearanceStart').is_disabled()
    tab.get_by_role('button',name='Collect more character images').click()
    tab.evaluate("refreshFail=false;photosForTest=[{id:'new',label:'New reference',source:'Local upload',dated:true,url:'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'}]")
    tab.evaluate('appearanceCollectionMutations=1;closeModal()')
    assert tab.locator('#modal').is_visible()
    tab.evaluate('appearanceCollectionMutations=0;closeModal()')
    tab.wait_for_function('!appearanceBusy && appearanceLoaded[0].selections.length===1')
    assert tab.locator('#appearanceStart').is_enabled()
    assert not errors,errors


def test_removed_selection_is_not_silently_replaced(page):
    tab,errors=open_test(page)
    tab.get_by_role('button',name='Collect more character images').click()
    tab.evaluate("photosForTest=[{...photosForTest[0],id:'different',label:'Different image',dated:true}]")
    tab.get_by_role('button',name='Return to AI analysis').click()
    tab.wait_for_function('!appearanceBusy && !appearanceCollection')
    assert not tab.get_by_role('checkbox',name='Different image').is_checked()
    assert tab.locator('#appearanceStart').is_disabled()
    assert 'no longer available' in tab.locator('#appearanceStatus').inner_text()
    tab.get_by_role('checkbox',name='Different image').check()
    assert tab.locator('#appearanceStart').is_enabled()
    assert not errors,errors


def test_corrupt_saved_portrait_does_not_displace_approved_refs(app):
    c,p,s,b,n,roles=app
    filename='b'*64+'.jpg';(s.PHOTO_DIR/filename).write_bytes(b'broken image')
    with s.connect() as db:
        db.execute('INSERT INTO images (key,url) VALUES (?,?)',('role|'+roles[0]['choice_key'],'api/photos/'+filename))
    photos=c.get(p+'/appearance/references',params={'choice_key':roles[0]['choice_key']}).json()['photos']
    assert [x['id'] for x in photos]==['1']

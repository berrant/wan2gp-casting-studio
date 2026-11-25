"""Local reference selection accepts batches without altering single-artwork semantics."""
from test_dev55_browser import page


def open_picker(tab, collect=True):
    tab.evaluate('''collect => {window.restartPhotoSearch=()=>{};window.collectionRefreshes=0;window.showReferenceCollection=async()=>{collectionRefreshes++};openPhoto('Synthetic Performer',{character:'Synthetic Role',production:'Synthetic Film'},'role',collect)}''', collect)


def test_batch_upload_handles_duplicates_invalid_files_and_review(page):
    tab, errors = page
    open_picker(tab)
    assert tab.locator('#localImageUpload').get_attribute('multiple') is not None
    tab.evaluate('''() => {const old=fetch;window.uploads=[];window.reviewDecisions=[];window.confirm=msg=>{reviewDecisions.push(msg);return msg.startsWith('approve.png')};window.fetch=async(u,o={})=>{if(!String(u).startsWith('api/reference-images/upload?'))return old(u,o);const q=new URLSearchParams(u.split('?')[1]);uploads.push([o.body.name,q.get('person'),q.get('production'),q.get('character'),q.get('accept_review')]);const name=o.body.name;const review=['approve.png','decline.png'].includes(name)&&q.get('accept_review')==='false';const fail=name==='reject.png';return {ok:!review&&!fail,status:review?409:fail?422:200,json:async()=>review?{detail:{status:'review',reasons:['inspect']}}:fail?{detail:{reasons:['invalid pixels']}}:{saved:true,duplicate:name==='duplicate.png',quality_status:'passed'}}}}''')
    names=['first.png','duplicate.png','approve.png','decline.png','reject.png','invalid.txt','last.png']
    tab.locator('#localImageUpload').set_input_files([{'name':n,'mimeType':'text/plain' if n.endswith('.txt') else 'image/png','buffer':b'fake pixels'} for n in names])
    tab.wait_for_function("$('manualPhotoStatus').textContent.includes('3 added · 1 already collected · 1 skipped · 2 rejected')")
    assert tab.evaluate('uploads.map(x=>[x[0],x[4]])')==[['first.png','false'],['duplicate.png','false'],['approve.png','false'],['approve.png','true'],['decline.png','false'],['reject.png','false'],['last.png','false']]
    assert all(x[1:4]==['Synthetic Performer','Synthetic Film','Synthetic Role'] for x in tab.evaluate('uploads'))
    assert tab.evaluate('reviewDecisions.length')==2
    assert 'reject.png: invalid pixels' in tab.locator('#manualPhotoStatus').inner_text()
    assert 'invalid.txt' in tab.locator('#manualPhotoStatus').inner_text()
    assert tab.evaluate('collectionRefreshes')==2
    assert tab.locator('#localImageUpload').input_value()==''
    assert tab.locator('#localImageUploadButton').is_enabled()
    assert not errors, errors


def test_batch_stops_on_navigation_without_overwriting_new_target(page):
    tab, errors=page
    open_picker(tab)
    tab.evaluate('''() => {const old=fetch;window.uploads=[];window.fetch=async(u,o={})=>{if(!String(u).startsWith('api/reference-images/upload?'))return old(u,o);uploads.push(o.body.name);return new Promise(resolve=>window.finishUpload=()=>resolve({ok:true,json:async()=>({saved:true})}))}}''')
    tab.locator('#localImageUpload').set_input_files([{'name':n,'mimeType':'image/png','buffer':b'x'} for n in ['first.png','second.png']])
    tab.wait_for_function('typeof finishUpload === "function"')
    assert tab.locator('#localImageUploadButton').is_disabled()
    tab.evaluate("closeModal();openPhoto('Another Performer',null,'actress',true);$('manualPhotoStatus').textContent='New collection';finishUpload()")
    tab.wait_for_function('photoSavePending.size===0')
    assert tab.evaluate('uploads')==['first.png']
    assert tab.locator('#manualPhotoStatus').inner_text()=='New collection'
    assert tab.locator('#localImageUploadButton').is_enabled()
    assert not errors, errors


def test_artwork_remains_single_file_and_picker_resets(page):
    tab, errors=page
    open_picker(tab)
    assert tab.locator('#localImageUpload').get_attribute('multiple') is not None
    open_picker(tab,False)
    assert tab.locator('#localImageUpload').get_attribute('multiple') is None
    tab.evaluate('''() => {const old=fetch;window.artworkUploads=[];window.fetch=async(u,o={})=>{if(!String(u).startsWith('api/images/upload?'))return old(u,o);artworkUploads.push(o.body.name);return {ok:true,json:async()=>({saved:true,url:'api/photos/synthetic.jpg'})}}}''')
    tab.evaluate("uploadLocalImage({files:[new File(['a'],'a.png',{type:'image/png'}),new File(['b'],'b.png',{type:'image/png'})],value:'fake'})")
    assert 'Choose just one image' in tab.locator('#manualPhotoStatus').inner_text()
    assert tab.evaluate('artworkUploads')==[]
    tab.locator('#localImageUpload').set_input_files({'name':'art.png','mimeType':'image/png','buffer':b'fake'})
    tab.wait_for_function('activeImage===null')
    assert tab.evaluate('artworkUploads')==['art.png']
    assert not errors, errors

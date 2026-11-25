from test_persona_power import tab,start

def test_failed_image_load_cannot_save_previous_models_template(tab):
    start(tab)
    tab.evaluate("""() => {document.querySelector('#imageEditorModal').classList.remove('open');document.querySelector('#promptModel').value='h3_image';window.writes=[];const orig=fetch;window.fetch=async(u,o)=>{if(String(u).includes('prompts/image-template')){if(o?.method==='PUT'){writes.push(JSON.parse(o.body));return {ok:true}}return {ok:false,text:async()=> 'offline'}}return orig(u,o)}}""")
    tab.evaluate('openImageEditor()')
    tab.evaluate('saveImageEditor()')
    assert tab.evaluate('writes.length')==0
    assert 'offline' in tab.locator('#imageEditorStatus').text_content()

def test_failed_image_reset_reports_error(tab):
    start(tab)
    tab.evaluate("""() => {const orig=fetch;window.fetch=(u,o)=>String(u).includes('image-template/reset')?Promise.resolve({ok:false,text:async()=> 'offline'}):orig(u,o)}""")
    tab.evaluate('resetImageEditor()')
    assert 'offline' in tab.locator('#imageEditorStatus').text_content()

def test_failed_video_load_cannot_overwrite_saved_template(tab):
    tab.evaluate("""() => {window.writes=[];const orig=fetch;window.fetch=async(u,o)=>{if(String(u).includes('prompts/template')){if(o?.method==='PUT'){writes.push(JSON.parse(o.body));return {ok:true}}return {ok:false,json:async()=>({detail:'offline'}),text:async()=> 'offline'}}return orig(u,o)}}""")
    tab.evaluate('openEditor()')
    tab.evaluate('saveEditor()')
    assert tab.evaluate('writes.length')==0
    assert 'load' in tab.locator('#editorStatus').text_content().lower()

"""dev5.4: numbered cast duplicates, scan timestamps/progress, safe in-app reconstructions."""
import json
from pathlib import Path
from test_native_plugin import installation

API='/casting-studio/api'


def make_refmod(folder, name):
    header={'__metadata__':{'refmod_meta':json.dumps({'name':name,'kind':'video','mode':'encode'})}}
    encoded=json.dumps(header).encode()
    (folder/(name+'.safetensors')).write_bytes(len(encoded).to_bytes(8,'little')+encoded+b'\0'*64)


def test_global_scan_status_and_workshop_scan_progress_persistence(installation):
    client,plugin,root,_=installation
    h3=root/'refmods'/'minimax_h3'/'celebs';make_refmod(h3,'Mackenzie_Davis_H3')
    api=client.get(API+'/catalog/scan-status');assert api.status_code==200
    assert 'last_scanned' in api.json()
    c=client.post(API+'/catalog/rescan');assert c.status_code==200
    status=client.get(API+'/catalog/scan-status').json()
    assert status['running'] is False and status['count']>=1
    assert status['total']>=status['checked']>=1
    scan=client.get(API+'/workshop/mods?force=true');assert scan.status_code==200,scan.text
    assert 'Mackenzie_Davis_H3.safetensors' in [x['filename'] for x in scan.json()['mods']]
    status=client.get(API+'/workshop/scan-status').json()
    assert status['last_scanned'] is not None
    assert status['checked']==status['total']
    assert status['valid']==len(scan.json()['mods'])
    assert status['invalid']==len(scan.json()['skipped'])
    assert (root/'user_data'/'workshop_last_scan.json').exists()
    assert (root/'user_data'/'catalog_last_scan.json').exists()


def test_decompile_gallery_lists_and_safely_streams_media(installation):
    client,plugin,root,_=installation
    folder=root/'refmods'/'decompiled'/'celebs'/'Abby_H3'
    folder.mkdir(parents=True)
    (folder/'001.png').write_bytes(b'pretend-image')
    (folder/'preview.mp4').write_bytes(b'pretend-video')
    (folder/'voice.wav').write_bytes(b'pretend-audio')
    (folder/'ignored.txt').write_text('not media')
    url=API+'/workshop/decompiled?name=celebs%2FAbby_H3'
    listing=client.get(url)
    assert listing.status_code==200, listing.text
    data=listing.json()['files']
    assert {x['filename'] for x in data}=={'001.png','preview.mp4','voice.wav'}
    for info in data:
        r=client.get('/casting-studio/'+info['url'])
        assert r.status_code==200 and r.headers['content-type'].startswith(info['media_type'])
        assert r.headers['cache-control']=='no-store'
    for illegal in ('../ignored.txt', 'ignored.txt', '../Abby_H3/001.png'):
        bad=client.get(API+'/workshop/decompiled/file',params={'name':'celebs/Abby_H3','file':illegal})
        assert bad.status_code in (400,404)
    assert client.get(API+'/workshop/decompiled?name=celebs%2F..%2Fpersonal').status_code==400
    (folder/'secret.png').symlink_to(root/'user_data'/'casting.sqlite3')
    files=client.get(url).json()['files']
    assert not any(x['filename']=='secret.png' for x in files)
    assert client.get(API+'/workshop/decompiled/file',params={'name':'celebs/Abby_H3','file':'secret.png'}).status_code==404


def test_legacy_numbered_cast_artifacts_suppressed_but_legitimate_roles_retained(installation):
    client,plugin,root,_=installation
    from importlib import import_module
    server=import_module(plugin.__class__.__module__.rsplit('.',1)[0]+'.app.server')
    (root/'refmods'/'minimax_h3'/'celebs'/'Alice_Braga_H3.safetensors').write_bytes(b'fake')
    server.catalog_cache['until']=0
    for role in ('Amanda Lucas','Amanda Lucas 2','Amanda Lucas 3','Amanda Lucas Jr.'):
        item={'actress':'Alice Braga','character':role,'production':'Dark Matter'}
        key=server.canonical_role_key('Alice Braga',role,'Dark Matter')
        with server.connect() as db:
            db.execute('INSERT INTO production_cast(key,payload) VALUES (?,?)',(key,json.dumps(item)))
    public=client.get(API+'/catalog').json()
    names=[x['character'] for x in public['roles'] if x['actress']=='Alice Braga' and x['production']=='Dark Matter']
    assert 'Amanda Lucas' in names
    assert 'Amanda Lucas 2' not in names and 'Amanda Lucas 3' not in names
    assert 'Amanda Lucas Jr.' in names
    cast=client.get(API+'/productions/cast',params={'production':'Dark Matter'}).json()['cast']
    names=[x['character'] for x in cast if x['actress']=='Alice Braga']
    assert 'Amanda Lucas' in names and 'Amanda Lucas Jr.' in names
    assert 'Amanda Lucas 2' not in names and 'Amanda Lucas 3' not in names
    # Source DB remains untouched, so restoring an intentionally distinct role is possible.
    with server.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM production_cast WHERE payload LIKE '%Amanda Lucas 2%'").fetchone()[0]==1


def test_native_tab_icon_and_ui_controls(installation):
    client,plugin,_,_=installation
    assert plugin.tabs[0]['icon'].startswith('<svg')
    html=client.get('/casting-studio/').text
    for token in ('workshopScanProgress','workshopResults','workshopResultGallery',
                  'workshopShowResults','catalogScanStatus','monitorLiveImage','monitorLiveVideo'):
        assert token in html


def test_live_wangp_preview_still_and_video_streaming(installation):
    from types import SimpleNamespace
    from PIL import Image
    client,plugin,root,_=installation
    bridge=plugin.queue_bridge
    jid='test-preview-001'
    bridge._jobs[jid]={'id':jid,'state':'running','files':[]}
    bridge._store_preview(jid,SimpleNamespace(image=Image.new('RGB',(640,360),'blue'),progress=35))
    st=client.get(API+'/generator/jobs/'+jid).json()
    assert st['preview_kind']=='image' and st['preview_rev']==1
    frame=client.get(API+'/generator/jobs/'+jid+'/preview')
    assert frame.status_code==200 and frame.headers['content-type'].startswith('image/jpeg')
    assert frame.content.startswith(b'\xff\xd8')
    bridge._store_preview(jid,SimpleNamespace(video=b'\x00\x00\x00\x14ftypisom' + b'\0'*16))
    st=client.get(API+'/generator/jobs/'+jid).json()
    assert st['preview_kind']=='video' and st['preview_rev']==2
    video=client.get(API+'/generator/jobs/'+jid+'/preview')
    assert video.status_code==200 and video.headers['content-type'].startswith('video/mp4')
    assert bridge.preview('other-job') is None
    assert client.get(API+'/generator/jobs/other-job/preview').status_code==404


def test_wangp_builtin_and_finetune_defaults_precedence(installation):
    client,plugin,root,_=installation
    (root/'defaults').mkdir();(root/'finetunes').mkdir()
    (root/'defaults'/'minimax_h3.json').write_text(json.dumps({'num_inference_steps':22,'resolution':'832x480','model':{'foo':'bar'}}))
    (root/'finetunes'/'custom_h3.json').write_text(json.dumps({'num_inference_steps':13,'resolution':'720x1280'}))
    bridge=plugin.queue_bridge
    result,sources=bridge._definition_sources('custom_h3',{'model_type':'custom_h3','architecture':'minimax_h3'})
    assert result['num_inference_steps']==13 and result['resolution']=='720x1280'
    assert 'model' not in result
    assert sources==['defaults/minimax_h3.json','finetunes/custom_h3.json']

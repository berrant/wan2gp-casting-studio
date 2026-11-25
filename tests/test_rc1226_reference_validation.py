"""Damaged local references must never displace usable images or stage vision work."""
import io
from contextlib import contextmanager
from PIL import Image
from test_rc1213_appearance import app, stage, run, approve
from test_native_plugin import installation


def photos(a):
    c,p,s,b,n,r=a
    response=c.get(p+'/appearance/references',params={'choice_key':r[0]['choice_key']})
    assert response.status_code==200
    return response.json()['photos']


def test_truncated_portrait_excluded_and_repaired_without_restart(app):
    c,p,s,b,n,r=app
    buf=io.BytesIO();Image.new('RGB',(640,800),'green').save(buf,format='JPEG')
    raw=buf.getvalue();filename='b'*64+'.jpg';path=s.PHOTO_DIR/filename
    path.write_bytes(raw[:1000])
    with Image.open(path) as im:assert im.size==(640,800)
    with s.connect() as db:db.execute('INSERT INTO images (key,url) VALUES (?,?)',('role|'+r[0]['choice_key'],'api/photos/'+filename))
    assert [x['id'] for x in photos(app)]==['1']
    assert stage(app,[{**r[0],'image_ids':['portrait']}]).status_code==400
    assert n.loads==0 and b.job is None
    path.write_bytes(raw)
    assert [x['id'] for x in photos(app)]==['portrait','1']
    assert stage(app,[{**r[0],'image_ids':['portrait']}]).status_code==200
    assert n.loads==0


def test_previously_approved_reference_corruption_preserves_profile_and_other_roles(app):
    c,p,s,b,n,r=app
    old=stage(app,[r[0]]).json()['id'];run(app,old);assert approve(app,old).status_code==200
    role=s.appearance_role(r[0]['choice_key']);before=s.exact_identity_snapshot(role['profile_key'])
    path=s.REFERENCE_DIR/f'{1:024x}.jpg';path.write_bytes(b'not a JPEG')
    assert photos(app)==[]
    assert stage(app,[r[0]]).status_code==400 and n.loads==1
    assert s.exact_identity_snapshot(role['profile_key'])==before
    job=stage(app,[r[1]]).json()['id'];assert run(app,job)['state']=='completed'
    Image.new('RGB',(120,160),'blue').save(path)
    assert [x['id'] for x in photos(app)]==['1']


def test_actual_selected_bytes_revalidated_despite_stale_listing(app,monkeypatch):
    c,p,s,b,n,r=app;real=s.appearance_source_bytes
    def changed(task):
        raw,fp=real(task);return [b'broken image'],fp
    monkeypatch.setattr(s,'appearance_source_bytes',changed)
    res=stage(app,[r[0]])
    assert res.status_code==422 and 'damaged' in res.json()['detail']
    assert n.loads==0 and b.job is None


def test_all_failed_batch_reports_failure_and_releases_model(app):
    c,p,s,b,n,r=app
    @contextmanager
    def broken(state,engine,stop):
        n.loads+=1
        try:
            def analyze(label,images):raise RuntimeError('Synthetic inference failure')
            yield analyze
        finally:n.releases+=1
    n.session=broken
    job=stage(app).json()['id'];result=run(app,job)
    assert result['state']=='failed' and 'All character analyses failed' in result['message']
    assert len(result['results'])==2 and all(x['state']=='failed' for x in result['results'])
    assert b.summary()['review']==0 and n.loads==n.releases==1


def test_partial_failure_preserves_successful_draft(app):
    c,p,s,b,n,r=app;original=n.session
    @contextmanager
    def partial(state,engine,stop):
        with original(state,engine,stop) as analyze:
            def wrapped(label,images):
                if 'Alien 1' in label:raise RuntimeError('Synthetic inference failure')
                return analyze(label,images)
            yield wrapped
    n.session=partial
    job=stage(app).json()['id'];result=run(app,job)
    assert result['state']=='completed' and '1 character analysis failed' in result['message']
    assert [x['state'] for x in result['results']]==['failed','review']
    assert approve(app,job,1).status_code==200 and n.loads==n.releases==1


def test_reference_removed_between_listing_and_read(app,monkeypatch):
    c,p,s,b,n,r=app;original=s.appearance_photo_rows;calls=0
    path=s.REFERENCE_DIR/f'{1:024x}.jpg'
    def removed(role):
        nonlocal calls
        rows=original(role);calls+=1
        if calls==2:path.unlink()
        return rows
    monkeypatch.setattr(s,'appearance_photo_rows',removed)
    response=stage(app,[r[0]])
    assert response.status_code==409 and 'no longer readable' in response.json()['detail']
    assert n.loads==0 and b.job is None

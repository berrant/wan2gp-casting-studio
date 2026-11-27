from test_native_plugin import installation
from test_rc2_jackhammer import API,server


def test_idle_status_includes_saved_research_history(installation):
    client,*_=installation;s=server()
    with s.connect() as db:
        db.executemany('INSERT INTO credit_refresh(name_key,checked,count,status) VALUES(?,?,?,?)', [('fixtureone',100,8,'ok'),('fixturetwo',101,0,'ok'),('fixturethree',102,0,'error')])
        db.executemany('INSERT INTO public_profiles(name_key,status) VALUES(?,?)',[('fixtureone','matched'),('fixturetwo','ambiguous'),('fixturethree','unmatched')])
    credits=client.get(API+'/credits/status').json()
    assert not credits['running'] and credits['done']==0
    assert credits['last_refresh']==102
    assert credits['history']=={'ok':{'performers':2,'credits':8},'error':{'performers':1,'credits':0}}
    enrichment=client.get(API+'/enrichment/status').json()
    assert not enrichment['running'] and enrichment['done']==0
    assert enrichment['history']=={'matched':1,'ambiguous':1,'unmatched':1}

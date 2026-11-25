"""Application upgrades must not reuse the old embedded HTML URL or cache."""
from test_native_plugin import installation
from html import unescape
import re
from urllib.parse import parse_qs, urlsplit


def test_versioned_iframe_url_and_uncached_shell(installation):
    c,p,*_=installation
    ui=p.create_ui()
    iframe=next(str(x['props'].get('value','')) for x in ui.config['components'] if '<iframe title=' in str(x['props'].get('value','')))
    src=unescape(re.search(r'<iframe[^>]*src="([^"]+)"',iframe).group(1))
    assert parse_qs(urlsplit(src).query)=={'embedded':['1'],'version':[p.version]}
    r=c.get('/casting-studio/?embedded=1&version='+p.version)
    assert r.status_code==200 and 'no-store' in r.headers['cache-control']
    assert 'v'+p.version in r.text
    old=c.get('/casting-studio/?embedded=1&version=1.0.0-rc.1',headers={'If-None-Match':'"old-release"'})
    assert old.status_code==200 and 'no-store' in old.headers['cache-control'] and 'v'+p.version in old.text
    status=c.get('/casting-studio/api/integration/status')
    assert status.headers['cache-control']=='no-store' and status.json()['casting_studio']==p.version
    assert c.get('/casting-studio/api/changelog').headers['cache-control']=='no-store'
    assert c.get('/casting-studio/api/ui/icons/casting-logo').headers['cache-control']=='public, max-age=604800'

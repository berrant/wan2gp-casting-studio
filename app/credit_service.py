"""Verified public performer role refresh; preserves manually curated casting data.

Public sources only, no identity inference, and no private-profile lookups. All
network activity is optional and failure does not remove existing roles.
"""
from __future__ import annotations
import re
import time
from urllib.parse import quote
import httpx
try:
    from .credit_sync import clean, key, parse_tvmaze_castcredits, parse_wikipedia_filmography
except ImportError:  # standalone Docker module path
    from credit_sync import clean, key, parse_tvmaze_castcredits, parse_wikipedia_filmography

AGENT = 'CastingStudio/1.0.1 (+https://github.com/berrant/wan2gp-casting-studio)'

def fetch_credits(name, timeout=14):
    name=clean(name)
    if not 2<=len(name)<=160:
        raise ValueError('Invalid public performer name')
    result={};warnings=[]
    # Search for a person, not a production. Never arbitrarily take the first
    # similar-name match; homonymous entries remain pending review.
    with httpx.Client(timeout=timeout, headers={'User-Agent':AGENT}, follow_redirects=False, trust_env=False) as client:
        try:
            response=client.get('https://api.tvmaze.com/search/people', params={'q':name});response.raise_for_status()
            matches=[x['person'] for x in response.json() if key(x.get('person',{}).get('name'))==key(name)]
            if len(matches)==1:
                pid=int(matches[0]['id'])
                credits=client.get(f'https://api.tvmaze.com/people/{pid}/castcredits',
                                   params=[('embed[]','show'),('embed[]','character')]);credits.raise_for_status()
                for r in parse_tvmaze_castcredits(credits.json(), name):
                    result[(key(r['production']),key(r['character']))]=r
            elif len(matches)>1:
                warnings.append('TVMaze: name is ambiguous, skipped')
        except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
            warnings.append(f'TVMaze: {type(exc).__name__}')
        try:
            parsed=client.get('https://en.wikipedia.org/w/api.php',params={
                'action':'parse','page':name,'prop':'text','format':'json','formatversion':'2',
                'redirects':'1'});parsed.raise_for_status()
            item=parsed.json().get('parse') or {}
            title=re.sub(r'\s*\([^)]*\)$','',str(item.get('title','')))
            if key(title)==key(name):
                for r in parse_wikipedia_filmography(item.get('text') or '',name):
                    r['source_url']='https://en.wikipedia.org/wiki/'+quote(str(item.get('title') or name).replace(' ','_'),safe='')
                    result.setdefault((key(r['production']),key(r['character'])),r)
            else:
                warnings.append('Wikipedia: no exact article match')
        except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
            warnings.append(f'Wikipedia: {type(exc).__name__}')
    if not result and len(warnings)==2:
        raise RuntimeError('; '.join(warnings))
    return list(result.values()),warnings

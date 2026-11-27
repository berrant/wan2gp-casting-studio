"""Conservative, dated public scene evidence. No generation-time networking.

Only extract attributed wardrobe and explicit story-world location descriptions;
never confuse filming locations with fictional locations or invent visual details.
"""
import re
from urllib.parse import quote

WARDROBE = re.compile(r'\b(?:wears?|wearing|dressed in|clad in|costume consists of|outfit consists of)\s+([^.;!?]{8,300})', re.I)
GARMENT = re.compile(r'\b(?:uniform|jacket|shirt|trousers|pants|robe|dress|coat|armor|armour|boots|tunic|cloak|suit|vest|skirt|helmet|gloves|overalls|coveralls)\b', re.I)
LOCATION = re.compile(r'\b(?:set (?:primarily |mainly |largely |mostly )?(?:in|on|aboard|at)|takes place (?:primarily |mainly )?(?:in|on|aboard|at)|(?:lives|works|is stationed|is based) (?:in|on|aboard|at))\s+([^.;!?]{5,340})', re.I)
EXCLUDE = re.compile(r'\b(?:filming|filmed|shooting|shot on location|production design|premiere|released|actor|actress|portrayed|behind the scenes|cosplay|merchandise|advertisement|promotional|sequel|remake|adaptation)\b', re.I)
VISUAL = re.compile(r'\b(?:city|town|village|planet|ship|starship|station|base|castle|palace|forest|desert|mountain|island|house|home|school|hospital|laboratory|office|room|corridor|spaceship|landscape|world|kingdom|colony|apartment|building|street|facility|outpost|camp|bunker|bridge|cockpit|library|farm|hotel|restaurant|bar|cave|temple|headquarters|prison|university|academy|wilderness|suburb|district)\b', re.I)

def normalized(value):
    return re.sub(r'[^\w]+','',str(value).casefold())

def extract_scene(text, character, production):
    """Return brief attributable clauses, not free-form model speculation."""
    name=re.compile(r'(?<!\w)'+r'\s+'.join(re.escape(x) for x in character.split())+r'(?!\w)',re.I)
    wardrobe=[]; settings=[]; role_settings=[]
    for sentence in re.split(r'(?<=[.!?])\s+|\n+',re.sub(r'\[\d+\]','',text[:48000])):
        sentence=sentence.strip()
        if not 12<=len(sentence)<=650 or EXCLUDE.search(sentence):continue
        # Require the character as the grammatical subject immediately before wardrobe/location.
        for match in WARDROBE.finditer(sentence):
            if not name.search(sentence[:match.start()]) or not re.search(name.pattern+r'\s*$',sentence[:match.start()],re.I):continue
            desc=match.group(1).strip(' ,')
            if GARMENT.search(desc) and desc not in wardrobe:wardrobe.append(desc)
        for match in LOCATION.finditer(sentence):
            prefix=sentence[:match.start()]
            role=bool(re.search(name.pattern+r'\s*$',prefix,re.I))
            general=bool(re.fullmatch(r'\s*(?:the\s+(?:film|series|show|story|action|narrative|game|plot)\s+(?:is\s+)?|'+re.escape(production)+r'\s+(?:is\s+)?)',prefix,re.I))
            if not (role or general):continue
            desc=match.group(1).strip(' ,')
            if not VISUAL.search(desc):continue
            target=role_settings if role else settings
            # Preserve the spatial preposition instead of guessing indoor/outdoor.
            prep=re.search(r'\b(in|on|aboard|at)\s*$',sentence[match.start():match.start(1)],re.I)
            value=(prep.group(1).capitalize()+' ' if prep else '')+desc
            if value not in target:target.append(value)
    # Do not blend alternative costumes or incompatible locations.
    return {'wardrobe': (wardrobe[0][0].upper()+wardrobe[0][1:]+'.' if wardrobe else ''),
            'setting': ((role_settings or settings)[0]+'.' if role_settings or settings else '')}

def research_scene(client, wiki_api, character, production, year):
    if '|' in production or not 1<=len(production)<=180:return {'wardrobe':'','setting':'','source':''}
    titles=[f'{production} ({year} film)',f'{production} ({year} TV series)',f'{production} (TV series)',f'{production} (film)',production]
    data=wiki_api(client,{'action':'query','titles':'|'.join(dict.fromkeys(titles)),'redirects':1,'prop':'extracts|pageprops','explaintext':1})
    if 'error' in data:raise ValueError('Public source lookup failed')
    matches=[]
    for page in data.get('query',{}).get('pages',[]):
        if page.get('missing') or page.get('invalid') or 'disambiguation' in page.get('pageprops',{}):continue
        title=page.get('title',''); raw=page.get('extract') or ''
        base=re.sub(r'\s*\((?:(?:\d{4} )?(?:film|TV series)|\d{4})\)\s*$','',title,flags=re.I)
        if normalized(base)!=normalized(production):continue
        # Verify exact release year in title or the production's opening description.
        lead=raw.split('\n',1)[0][:1000]
        explicit=re.search(r'\((\d{4})(?: film| TV series)?\)$',title,re.I)
        if explicit and int(explicit.group(1))!=year:continue
        if not explicit and not re.search(r'\b'+str(year)+r'\b[^.!?]{0,90}\b(?:film|television series|TV series|video game)\b|\b(?:premiered|released|debuted)\b[^.!?]{0,60}\b'+str(year)+r'\b',lead,re.I):continue
        if not re.search(r'\b(?:film|television series|TV series|video game)\b',lead,re.I):continue
        # An exact character mention is required even for production-wide settings.
        if not re.search(r'(?<!\w)'+r'\s+'.join(re.escape(x) for x in character.split())+r'(?!\w)',raw,re.I):continue
        matches.append((title,raw))
    if len(matches)!=1:return {'wardrobe':'','setting':'','source':''}
    title,raw=matches[0]
    result=extract_scene(raw,character,production)
    result['source']='https://en.wikipedia.org/wiki/'+quote(title.replace(' ','_'),safe='') if any(result.values()) else ''
    return result

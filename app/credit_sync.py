"""Conservative public performer credit discovery (no keys, no private identities).

Only import credits with a named character/role from a positively identified person.
Never invent missing characters from production titles. Network providers may fail; the
existing local catalog remains authoritative and usable offline.
"""
import re
from bs4 import BeautifulSoup


def key(value):
    return re.sub(r'[^a-z0-9]', '', str(value or '').casefold())


def clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip(' \t\n\r†‡*')


def year_of(value):
    match=re.search(r'\b(18\d{2}|19\d{2}|20\d{2}|2100)\b', str(value or ''))
    return int(match.group(1)) if match else None


def table_rows(table):
    """Expand row/colspan so Wikipedia filmography's carried-forward years align."""
    carried={}
    for tr in table.find_all('tr'):
        raw=tr.find_all(['th','td'],recursive=False)
        if not raw:
            continue
        values=[];index=0
        for cell in raw:
            while index in carried:
                left,value=carried.pop(index)
                values.append(value)
                if left>1:carried[index]=(left-1,value)
                index+=1
            for tag in cell.select('sup.reference,.reference,.mw-editsection,.sortkey,.mw-empty-elt'):
                tag.decompose()
            value=clean(cell.get_text(' ',strip=True))
            try:rowspan=min(int(cell.get('rowspan',1)),500)
            except (TypeError,ValueError):rowspan=1
            try:colspan=min(int(cell.get('colspan',1)),12)
            except (TypeError,ValueError):colspan=1
            for _ in range(colspan):
                values.append(value)
                if rowspan>1:carried[index]=(rowspan-1,value)
                index+=1
        if carried:
            end=max(carried)
            while index<=end:
                if index in carried:
                    left,value=carried.pop(index)
                    values.append(value)
                    if left>1:carried[index]=(left-1,value)
                else:values.append('')
                index+=1
        yield values


def parse_wikipedia_filmography(html, person_name):
    """Only accept Film/TV filmography tables with explicit Year, Title, Role columns.

    Parsing actor-specific tables (not arbitrary prose) prevents mapping an unrelated
    character to the installed performer. Result order is newest year first.
    """
    soup=BeautifulSoup(html,'html.parser')
    results={}
    for table in soup.select('table.wikitable'):
        rows=list(table_rows(table))
        if len(rows)<2:continue
        # Some tables have a visually merged superheading; locate a header row.
        headers=[];header_idx=-1
        for i,row in enumerate(rows[:4]):
            norm=[clean(c).casefold() for c in row]
            def match_header(names):
                return next((j for j,h in enumerate(norm) if h in names),None)
            title_idx=match_header({'title','film','film title','production','series','show','television'})
            role_idx=match_header({'role','character','role / character','character / role'})
            year_idx=match_header({'year','release year','date'})
            if title_idx is not None and role_idx is not None and year_idx is not None:
                headers=[title_idx,role_idx,year_idx];header_idx=i;break
        if not headers:continue
        title_col,role_col,year_col=headers
        heading=table.find_previous(['h2','h3','h4'])
        context=clean(heading.get_text(' ',strip=True)).casefold() if heading else ''
        if any(x in context for x in ('theatre','theater','stage','videogame','video game','music video','award','nomination')):
            continue
        kind='series' if any(x in context for x in ('television','tv series','web series')) else 'film'
        for row in rows[header_idx+1:]:
            if max(headers)>=len(row):continue
            prod=clean(row[title_col]);role=clean(row[role_col]);year=year_of(row[year_col])
            prod=re.sub(r'\s*\((?:19|20)\d{2}\)$','',prod).strip()
            if not (2<=len(prod)<=180 and 2<=len(role)<=150):continue
            if key(prod) in ('title','film','television','role','notes') or role.casefold() in (
                'self','herself','himself','themselves','tba','unknown','n/a','—','–','none','uncredited'):
                continue
            if role.casefold().startswith(('see ', 'various roles', 'multiple roles')):continue
            # Data is from the named performer's filmography, not a cast of another production.
            record={'actress':person_name,'character':role,'production':prod,'year':year,
                    'kind':kind,'source':'Wikipedia filmography'}
            results[(key(prod),key(role))]=record
    return sorted(results.values(),key=lambda x:(-(x['year'] or 0),x['production'].casefold(),x['character'].casefold()))


def parse_tvmaze_castcredits(credits, person_name):
    """Parse show + character embeds; skip incomplete references and unnamed roles."""
    result={}
    for item in credits:
        embedded=item.get('_embedded') or {}
        show=embedded.get('show') or {}
        role=embedded.get('character') or {}
        prod=clean(show.get('name'));character=clean(role.get('name'))
        if not (2<=len(prod)<=180 and 2<=len(character)<=150):continue
        photo=(role.get('image') or {}).get('medium') or ''
        if not isinstance(photo,str) or not photo.startswith('https://'):photo=''
        year=year_of(show.get('premiered'))
        r={'actress':person_name,'character':character,'production':prod,'year':year,
           'kind':'series','image':photo,'source':'TVMaze'}
        result[(key(prod),key(character))]=r
    return list(result.values())

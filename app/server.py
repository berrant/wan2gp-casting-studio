import json, os, re, sqlite3, threading, time, random, hashlib, socket, ipaddress, io, shutil, zipfile, uuid, subprocess
from pathlib import Path
from urllib.parse import quote, urlencode
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
import httpx
from PIL import Image, ImageOps, UnidentifiedImageError
from bs4 import BeautifulSoup
try:
    from .credit_sync import parse_wikipedia_filmography, parse_tvmaze_castcredits
    from .credit_service import fetch_credits
except ImportError:  # top-level test imports
    from credit_sync import parse_wikipedia_filmography, parse_tvmaze_castcredits
    from credit_service import fetch_credits

ROOT=Path(__file__).resolve().parent
WANGP_ROOT=ROOT.parents[2]
DEFAULT_REFMOD_ROOT=Path(os.environ.get('CASTING_STUDIO_REFMOD_ROOT') or (WANGP_ROOT/'loras'/'refmods_plugin')).expanduser().absolute()
REFS=Path(os.environ.get('CASTING_STUDIO_H3_DIR') or os.environ.get('REFMOD_DIR',str(DEFAULT_REFMOD_ROOT/'minimax_h3'/'celebs')))
FLUX_REFS=Path(os.environ.get('CASTING_STUDIO_FLUX_DIR') or os.environ.get('REFMOD_FLUX_DIR',str(DEFAULT_REFMOD_ROOT/'flux2')))
# Runtime state must never resolve into the distributed plugin, including via symlinks.
def external_data_path(path):
    resolved=Path(path).expanduser().resolve()
    if resolved.is_relative_to(ROOT.parent.resolve()):
        raise RuntimeError('Casting Studio runtime storage must be outside the plugin directory')
    return resolved

DATA=external_data_path(os.environ.get('CASTING_STUDIO_DATA_DIR') or WANGP_ROOT/'data'/'casting-studio')
DATA.mkdir(parents=True,exist_ok=True)
PHOTO_DIR=external_data_path(DATA/'photos')
PHOTO_DIR.mkdir(parents=True,exist_ok=True)
PERSONAL_PORTRAITS=external_data_path(DATA/'personal_portraits')
PERSONAL_PORTRAITS.mkdir(parents=True,exist_ok=True)
PERSONAL_H3=Path(os.environ.get('CASTING_STUDIO_PERSONAL_H3_DIR') or os.environ.get('PERSONAL_H3_DIR',str(DEFAULT_REFMOD_ROOT/'minimax_h3'/'personal')))
PERSONAL_FLUX=Path(os.environ.get('CASTING_STUDIO_PERSONAL_FLUX_DIR') or os.environ.get('PERSONAL_FLUX_DIR',str(DEFAULT_REFMOD_ROOT/'flux2'/'personal')))
PERSONAL_STUDIO='A plain, seamless neutral gray photography studio backdrop with soft, even professional studio lighting, gentle floor shadows and a stationary camera. A clean, uncluttered studio portrait setting.'
PERSONAL_ORIGINAL_WARDROBE='Simple everyday studio attire appropriate to the same person, with the subject’s recognizable physical features and natural proportions preserved.'
PERSONAL_TRANSFORMED_WARDROBE='Elegant formal studio attire. The same person retains their recognizable facial identity, distinctive physical features, hairstyle and proportions throughout.'
DB={'meta':{'mapped_roles_count':0,'production_count':0,'inventory_notice':'Local discovery only'},'people':[],'roles':[],'productions':[],'creditSuggestions':[]}
NAME_REGISTRY={}
app=FastAPI(title='Casting Studio for WanGP')

@app.exception_handler(RequestValidationError)
async def request_validation_error(request:Request, exc:RequestValidationError):
    # Pydantic's raw input can contain non-finite floats or private text. Never
    # echo it into JSON: Infinity/NaN otherwise cause a second, unhandled error.
    details=[{'type':str(e.get('type','validation_error')),
              'loc':[str(v) if not isinstance(v,int) else v for v in e.get('loc',())],
              'msg':str(e.get('msg','Invalid request'))} for e in exc.errors()]
    return JSONResponse(status_code=422,content={'detail':details})

lock=threading.Lock()
schema_lock=threading.RLock()
prefetch_lock=threading.Lock()
prefetch_state={'running':False,'paused':False,'total':0,'done':0,'found':0,'failed':0,'last':'','started':None}
prefetch_stop=threading.Event()
prefetch_thread=None
catalog_cache={'until':0,'models':[],'revision':0}

# Read the driver's existing sensor, without initializing CUDA or touching GPU jobs.
GPU_TEMPERATURE_TTL=5.0
_gpu_temp_lock=threading.Lock()
_gpu_temp_cache={'until':0.0,'result':{'gpus':[],'available':False}}


def gpu_temperature_band(celsius):
    # Conservative display bands, not device-specific thermal limits.
    return 'normal' if celsius<75 else 'warm' if celsius<85 else 'hot'


def read_gpu_temperatures():
    executable=shutil.which('nvidia-smi')
    if not executable and os.name=='nt':
        candidate=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'NVIDIA Corporation'/'NVSMI'/'nvidia-smi.exe'
        if candidate.is_file():executable=str(candidate)
    if not executable:return {'gpus':[],'available':False}
    try:
        result=subprocess.run([executable,'--query-gpu=index,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,check=True)
    except (OSError,subprocess.SubprocessError,UnicodeError):
        return {'gpus':[],'available':False}
    readings={}
    for line in result.stdout.splitlines()[:128]:
        parts=line.split(',')
        if len(parts)!=2:continue
        try:index,temp=map(int,parts)
        except ValueError:continue
        if 0<=index<128 and 0<temp<=150:
            readings[index]={'index':index,'celsius':temp,'band':gpu_temperature_band(temp)}
    return {'gpus':list(readings.values()),'available':bool(readings)}


@app.get('/api/telemetry/gpu-temperature')
def gpu_temperature():
    now=time.monotonic()
    if now<_gpu_temp_cache['until']:return _gpu_temp_cache['result']
    # Never launch overlapping driver queries when multiple tabs are polling.
    if not _gpu_temp_lock.acquire(blocking=False):return _gpu_temp_cache['result']
    try:
        if time.monotonic()>=_gpu_temp_cache['until']:
            result=read_gpu_temperatures()
            _gpu_temp_cache.update(result=result,until=time.monotonic()+GPU_TEMPERATURE_TTL)
        return _gpu_temp_cache['result']
    finally:_gpu_temp_lock.release()


def token(s):
    text=str(s).casefold()
    return re.sub(r'[^a-z0-9]','',text) or ''.join(c for c in text if c.isalnum())
PUBLIC_CATALOG_NAMES={token(p['name']):p['name'] for p in DB['people']}
# No shipped identity, role or credit records. User changes live in SQLite.
KNOWN_IDENTITIES={}
CURATED_ROLE_DATA={}
CURATED_CATEGORIES={}
CURATED_CREDITS={}
CURATED_IMDB={}
# Occupations are public professional activities, not identity attributes.
# Wikidata P106 IDs: occupation categories are conservative and multi-label.
OCCUPATIONS={
 'Q33999':'Actor', 'Q10800557':'Actor','Q2405480':'Actor',
 'Q2252262':'Actor','Q3282637':'Actor','Q10798782':'Actor',
 'Q488111':'Model','Q4610556':'Model','Q16618675':'Model',
 'Q49757':'Musician','Q177220':'Musician','Q639669':'Musician',
 'Q36834':'Musician','Q753110':'Musician','Q486748':'Musician',
 'Q245068':'Comedian','Q4009406':'Comedian',
 'Q13590141':'Presenter','Q947873':'Presenter',
 'Q14089670':'TV personality','Q2526255':'TV personality',
 'Q17125263':'Influencer','Q123297072':'Influencer',
 'Q1404067':'Influencer','Q4977025':'Influencer',
}
ENRICH_LOCK=threading.Lock()
ENRICH_STOP=threading.Event()
ENRICH_STATE={'running':False,'total':0,'done':0,'matched':0,'classified':0,'failed':0,'last':'','last_error':''}
identity_overrides={}
def refresh_identities():
    global identity_overrides
    with connect() as conn:
        identity_overrides={key: name for key,name in conn.execute('SELECT key, display_name FROM identity_names')}
def canonical_name(s):
    raw=(s or '').strip()
    t=token(raw)
    return identity_overrides.get(t) or KNOWN_IDENTITIES.get(t) or raw
def canonical_production(s):
    # Remove only a trailing four-digit date, preserving non-year numbers in film titles.
    return re.sub(r'\s*\(?\b(?:19|20)\d{2}\)?\s*$', '', (s or '').strip()).strip()
def canonical_role_key(name, character, production):
    return '|'.join(map(token,(canonical_name(name),character,canonical_production(production))))
def canonical_photo_key(key):
    parts=key.split('|')
    if len(parts)==2 and parts[0]=='actress':
        return 'actress|'+token(canonical_name(parts[1]))
    if len(parts)==2 and parts[0]=='production':
        return 'production|'+token(canonical_production(parts[1]))
    if len(parts)==4 and parts[0]=='role':
        # Legacy image keys were tokenized before a production year was removed.
        production=re.sub(r'(?<=[a-z])(?:19|20)\d{2}$','',parts[3])
        return 'role|'+canonical_role_key(parts[1],parts[2],production)
    return key

def categories_from_legacy(description):
    text=(description or '').casefold()
    if any(x in text for x in ('unverified identity','planned refmod','unclassified')):return []
    labels=[]
    for category, terms in {
        'Video game character':('video game character','videogame character','game character'),
        'Actor':('actor','actress','voice actor'),
        'Model':('model',), 'Musician':('singer','musician','songwriter','rapper','vocalist'),
        'Influencer':('influencer','streamer','content creator','internet personality'),
        'Comedian':('comedian',), 'Presenter':('presenter','host'),
        'TV personality':('tv personality','television personality','reality tv','news anchor','news reporter','broadcast journalist','television journalist','weather presenter','meteorologist'),
    }.items():
        if any(term in text for term in terms): labels.append(category)
    return labels

def decoded_categories(raw):
    try:
        value=json.loads(raw)
        if isinstance(value,list) and all(isinstance(x,str) for x in value):return value
    except (ValueError,TypeError,RecursionError):pass
    return None


def decoded_cast(raw):
    try:
        value=json.loads(raw)
        if not isinstance(value,dict):return None
        if any(not isinstance(value.get(k),str) for k in ('actress','character','production')):return None
        if not value['actress'].strip() or not value['production'].strip():return None
        year=value.get('year')
        if year is not None and (type(year) is not int or not 1880<=year<=2100):return None
        return value
    except (ValueError,TypeError,RecursionError):return None


def saved_cast_rows(db):
    # Quarantine malformed rows in place; never rewrite or delete user data on read.
    return [role for (raw,) in db.execute('SELECT payload FROM production_cast')
            if (role:=decoded_cast(raw)) is not None]


def fictional_game_name_keys(include_damaged=False):
    """User-marked fictional identities, excluded from human performer research.

    An entry is only treated as fictional after explicit classification or
    source metadata; never infer fictional identity from name or appearance.
    """
    with connect() as db:
        rows=db.execute('SELECT name,categories FROM profile_categories').fetchall()
    result=set()
    for name,payload in rows:
        cats=decoded_categories(payload)
        # Unknown classification must not trigger human research.
        if (cats is None and include_damaged) or (cats is not None and 'Video game character' in cats):result.add(token(canonical_name(name)))
    return result


def is_video_game_character(name):
    return token(canonical_name(name)) in fictional_game_name_keys()


def normalized_catalog(models=None, discovery=False):
    private_names=personal_name_keys()
    models=[m for m in (models if models is not None else scan()) if token(m['name']) not in private_names]
    installed={token(m['name']):m['name'] for m in models}
    legacy={}
    for person in DB['people']:
        k=token(canonical_name(person['name']))
        prev=legacy.get(k)
        # Prefer useful known biographies over empty unverified records.
        if prev is None or (not prev.get('credits') and person.get('credits')):
            legacy[k]=person
    with connect() as db:
        public={k:{'categories':decoded_categories(cats) or [],'imdb':imdb,'status':status} for k,cats,imdb,status in db.execute('SELECT name_key,categories,imdb_id,status FROM public_profiles')}
        edits={token(canonical_name(k)):cats for k,v in db.execute('SELECT name,categories FROM profile_categories') if (cats:=decoded_categories(v)) is not None}
    role_performers={token(canonical_name(role['actress'])) for role in DB['roles']}
    if discovery:
        for person in DB['people']:
            name=canonical_name(person['name']); k=token(name)
            if k not in private_names:installed.setdefault(k,name)
        with connect() as conn:
            for name, in conn.execute('SELECT name FROM profile_categories'):
                k=token(canonical_name(name))
                if k and k not in private_names:installed.setdefault(k,canonical_name(name))
            extra=saved_cast_rows(conn)
        for role in [*DB['roles'],*extra]:
            name=canonical_name(role['actress']); k=token(name)
            if k not in private_names:installed.setdefault(k,name)

    people=[]
    for k,name in sorted(installed.items(),key=lambda z:z[1].casefold()):
        p=legacy.get(k,{})
        existing=categories_from_legacy(p.get('type',''))
        remote=public.get(k,{})
        cats=edits.get(k) or CURATED_CATEGORIES.get(k) or existing or remote.get('categories',[]) or (['Actor'] if k in role_performers else [])
        cats=[c for c in cats if c and c!='Unclassified']
        people.append({**p,'name':name,'type':' / '.join(cats) if cats else 'Unclassified',
                       'categories':cats,'credits':p.get('credits') or CURATED_CREDITS.get(k,[]),
                       'enrichment_status':remote.get('status','pending')})
    roles_by_key={}
    for role in DB['roles']:
        k=token(canonical_name(role['actress']))
        if k not in installed: continue
        r=dict(role)
        r['actress']=installed[k]
        year_match=re.search(r'\b((?:19|20)\d{2})\)?\s*$',r['production'])
        if year_match and not r.get('year'):r['year']=int(year_match.group(1))
        r['production']=canonical_production(r['production'])
        rk=canonical_role_key(r['actress'],r['character'],r['production'])
        if rk not in roles_by_key:roles_by_key[rk]=r
    with connect() as conn:
        customroles=saved_cast_rows(conn)
    for r in customroles:
        k=token(canonical_name(r['actress']))
        if k in installed:
            rr={**r,'actress':installed[k]}
            roles_by_key.setdefault(canonical_role_key(rr['actress'],rr['character'],rr['production']),rr)
    for k, rolelist in CURATED_ROLE_DATA.items():
        if k not in installed:continue
        for role in rolelist:
            r={'actress':installed[k], 'character':role['character'],'production':role['production'],'year':role.get('year')}
            rk=canonical_role_key(r['actress'],r['character'],r['production'])
            roles_by_key.setdefault(rk,r)
    # Some legacy/third-party cast imports numbered the exact same role as
    # "Amanda Lucas", "Amanda Lucas 2", "Amanda Lucas 3". Suppress only
    # suffixed variants when the base role exists for the SAME performer/show.
    # Do not erase SQLite entries or combine distinct genuine character names.
    for rk, role in list(roles_by_key.items()):
        role_name=role.get('character') or ''
        m=re.fullmatch(r'(.+?)\s+([2-9]|[1-9][0-9])', role_name.strip())
        if not m:continue
        base_key=canonical_role_key(role['actress'],m.group(1),role['production'])
        if base_key in roles_by_key and base_key!=rk:
            roles_by_key.pop(rk,None)
    return people,list(roles_by_key.values())


# Normalize legacy stored keys on startup; keep a backup of the original database.
def migrate_legacy():
    path=external_data_path(DATA/'casting.sqlite3')
    if path.exists() and not external_data_path(DATA/'casting.pre-v2.sqlite3').exists():
        # sqlite backup handles WAL safely and avoids altering the original file.
        src=sqlite3.connect(path);dst=sqlite3.connect(external_data_path(DATA/'casting.pre-v2.sqlite3'))
        try:src.backup(dst)
        finally:dst.close();src.close()
    with lock,connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS auto_images (key TEXT PRIMARY KEY, url TEXT NOT NULL, checked INTEGER NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS system_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS photo_files (url TEXT PRIMARY KEY, filename TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS prompt_settings (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS prompt_overrides (key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        if db.execute("SELECT value FROM system_meta WHERE key='migration_v2'").fetchone():return
        oldchoices=list(db.execute('SELECT key,payload FROM choices'))
        for oldkey,payload in oldchoices:
            try:
                entry=json.loads(payload)
                entry['person']=canonical_name(entry['person'])
                entry['production']=canonical_production(entry['production'])
                entry['key']=canonical_role_key(entry['person'],entry['character'],entry['production'])
                db.execute('INSERT OR IGNORE INTO choices(key,payload) VALUES (?,?)',(entry['key'],json.dumps(entry)))
            except (ValueError,KeyError,TypeError):continue
        for oldkey,_ in oldchoices:
            try:
                entry=json.loads(dict(oldchoices)[oldkey])
                if canonical_role_key(entry['person'],entry['character'],entry['production'])!=oldkey:
                    db.execute('DELETE FROM choices WHERE key=?',(oldkey,))
            except (ValueError,KeyError,TypeError):pass
        for oldkey,url in list(db.execute('SELECT key,url FROM images')):
            newkey=canonical_photo_key(oldkey)
            if newkey!=oldkey:
                db.execute('INSERT OR IGNORE INTO images(key,url) VALUES (?,?)',(newkey,url))
        db.execute("INSERT INTO system_meta VALUES('migration_v2','done')")

@app.on_event('startup')
def startup():
    refresh_identities()
    migrate_legacy()
    # No network research or scheduled maintenance on startup. The previous
    # 30-second automatic public-credit sync could contend with generation.
    # All bulk enrichment/role/photo jobs require explicit POST requests.



def connect():
    conn=sqlite3.connect(external_data_path(DATA/'casting.sqlite3'),timeout=20)
    with schema_lock:
        conn.execute('CREATE TABLE IF NOT EXISTS identity_names (key TEXT PRIMARY KEY, display_name TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS choices (key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS production_selection_sets (production TEXT NOT NULL, family TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(production,family))')
        conn.execute('CREATE TABLE IF NOT EXISTS casting_gallery (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS casting_job_history (id TEXT PRIMARY KEY, updated INTEGER NOT NULL, payload TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS images (key TEXT PRIMARY KEY, url TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS photo_files (url TEXT PRIMARY KEY, filename TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS profile_categories (name TEXT PRIMARY KEY, categories TEXT NOT NULL)')
        conn.execute("CREATE TABLE IF NOT EXISTS public_profiles (name_key TEXT PRIMARY KEY, matched_name TEXT NOT NULL DEFAULT '', qid TEXT NOT NULL DEFAULT '', imdb_id TEXT NOT NULL DEFAULT '', categories TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'pending', checked INTEGER NOT NULL DEFAULT 0)")
        # Record errors to diagnose throttling or network interruptions on later research runs.
        conn.execute('''CREATE TABLE IF NOT EXISTS enrichment_failures (
            name_key TEXT PRIMARY KEY, name TEXT NOT NULL, error_type TEXT NOT NULL,
            http_status INTEGER, error_detail TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 1,
            last_checked INTEGER NOT NULL)''')
        conn.execute("CREATE TABLE IF NOT EXISTS credit_refresh (name_key TEXT PRIMARY KEY, checked INTEGER NOT NULL DEFAULT 0, count INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending', detail TEXT NOT NULL DEFAULT '')")
        conn.execute('CREATE TABLE IF NOT EXISTS profile_markers (name TEXT PRIMARY KEY, adult INTEGER NOT NULL DEFAULT 0)')
        conn.execute("CREATE TABLE IF NOT EXISTS profile_links (name TEXT PRIMARY KEY, imdb_url TEXT NOT NULL DEFAULT '', checked INTEGER NOT NULL)")
        conn.execute('CREATE TABLE IF NOT EXISTS productions (key TEXT PRIMARY KEY, name TEXT NOT NULL, year INTEGER, kind TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS production_cast (key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS reference_images (id TEXT PRIMARY KEY, person TEXT NOT NULL, production TEXT NOT NULL, character TEXT NOT NULL, source_url TEXT NOT NULL, page_url TEXT NOT NULL, filename TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL)')
        # Additive columns; older collected images remain present for an explicit audit.
        fields={row[1] for row in conn.execute('PRAGMA table_info(reference_images)')}
        for field,definition in {'quality_status':"TEXT NOT NULL DEFAULT 'pending'",'quality_notes':"TEXT NOT NULL DEFAULT ''",'perceptual_hash':"TEXT NOT NULL DEFAULT ''",'sharpness':'REAL NOT NULL DEFAULT 0','face_count':'INTEGER NOT NULL DEFAULT -1'}.items():
            if field not in fields:conn.execute(f'ALTER TABLE reference_images ADD COLUMN {field} {definition}')
        conn.execute('CREATE TABLE IF NOT EXISTS prompt_settings (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS profile_gender (name_key TEXT PRIMARY KEY, symbol TEXT NOT NULL)')
        conn.execute('''CREATE TABLE IF NOT EXISTS personal_profiles (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE,
            relationship TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
            consent INTEGER NOT NULL DEFAULT 0, portrait TEXT NOT NULL DEFAULT '',
            h3_refmod TEXT NOT NULL DEFAULT '', flux_refmod TEXT NOT NULL DEFAULT '',
            updated_at INTEGER NOT NULL DEFAULT 0)''')
        conn.execute('CREATE TABLE IF NOT EXISTS production_artwork (name_key TEXT PRIMARY KEY, url TEXT NOT NULL, checked INTEGER NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS prompt_overrides (key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        conn.execute("CREATE TABLE IF NOT EXISTS final_prompt_edits (key TEXT PRIMARY KEY, choice_key TEXT NOT NULL, personal_id TEXT NOT NULL DEFAULT '', prompt TEXT NOT NULL)")
        conn.execute('CREATE TABLE IF NOT EXISTS character_identity (key TEXT PRIMARY KEY, traits TEXT NOT NULL, updated_at INTEGER NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS appearance_analysis (key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS character_identity_suggestions (key TEXT PRIMARY KEY, traits TEXT NOT NULL, source TEXT NOT NULL, checked INTEGER NOT NULL)')
        conn.commit()
    return conn

def model_name(p):
    base=p.stem
    if '__role__' in base:base=base.split('__role__',1)[0]
    base=re.sub(r'^minimaxh3[_-]?','',base,flags=re.I)
    base=re.sub(r'(?i)(?:_v\d+)?_refmod(?:h3)?$','',base)
    base=re.sub(r'(?i)_H3(?:_v\d+)?$','',base)
    base=re.sub(r'(?i)(?:_flux(?:2|3)?|_klein(?:4b|9b)?)$','',base)
    return NAME_REGISTRY.get(p.name.casefold(),{}).get('name') or PUBLIC_CATALOG_NAMES.get(token(base)) or base.replace('_',' ').strip()

def personal_name_keys():
    """Private identity names; never submit these to public metadata or photo providers."""
    with connect() as db:
        keys={name_key for (name_key,) in db.execute('SELECT name_key FROM personal_profiles')}
    # Treat both ends of a locally registered alias as private when either
    # identifies a Personal profile, including chains of aliases.
    edges=[(key,token(name)) for key,name in identity_overrides.items()]
    changed=True
    while changed:
        before=len(keys)
        for a,b in edges:
            if a in keys or b in keys:keys.update((a,b))
        changed=len(keys)!=before
    return keys

def assert_public_name(name):
    keys=personal_name_keys()
    if token(name) in keys or token(canonical_name(name)) in keys:
        raise HTTPException(403,'Personal profiles are excluded from public research and photo lookup')

# Local paths are intentionally confined to the known mounted model roots.
# Arbitrary filesystem paths would expose unrelated private files through a
# network-accessible application, and Refmod-Fork cannot load arbitrary folders.
LOCAL_PATH_KEYS={
    'public_h3':REFS, 'public_flux':FLUX_REFS,
    'personal_h3':PERSONAL_H3, 'personal_flux':PERSONAL_FLUX,
}
PATHS_FILE=external_data_path(DATA/'local_paths.json')

def root_paths(root):
    root=Path(root)
    return {'public_h3':root/'minimax_h3'/'celebs', 'public_flux':root/'flux2',
            'personal_h3':root/'minimax_h3'/'personal', 'personal_flux':root/'flux2'/'personal'}


def approved_refmod_root(value):
    """A root is a location of the native library, not a second model mount."""
    if not isinstance(value,str) or not value.strip():
        raise ValueError('Enter the RefMod root folder')
    try:
        candidate=Path(value).expanduser()
        if not candidate.is_absolute() or not candidate.is_dir():
            raise ValueError('Choose an existing absolute RefMod root folder')
        paths=root_paths(candidate)
        if (any(paths[k].resolve()!=base.resolve() for k,base in LOCAL_PATH_KEYS.items())
            or (candidate/'flux2'/'celebs').resolve()!=(FLUX_REFS/'celebs').resolve()):
            raise ValueError('Root must match the library mounted by Refmod-Fork. Configure its model mount first, then use the detected root.')
        return candidate
    except (OSError,RuntimeError) as exc:
        raise ValueError('Invalid or inaccessible RefMod root folder') from exc


def stored_refmod_root():
    try: stored=json.loads(PATHS_FILE.read_text(encoding='utf-8'))
    except (OSError,ValueError):stored={}
    if isinstance(stored,dict) and 'refmod_root' in stored:
        try:return approved_refmod_root(stored['refmod_root'])
        except (ValueError,TypeError):pass
    # Former per-folder filters are deliberately not applied to the unified root.
    return DEFAULT_REFMOD_ROOT


def effective_local_paths():
    # Native mounts are authoritative even if a previously saved alias disappears.
    return {key:base.resolve() for key,base in LOCAL_PATH_KEYS.items()}


class LocalPathsRequest(BaseModel):
    refmod_root:str=Field(min_length=1,max_length=4096)
    model_config={'extra':'forbid'}


@app.get('/api/settings/paths')
def get_local_paths():
    active=effective_local_paths()
    root=stored_refmod_root()
    return {'refmod_root':str(root),'default_root':str(DEFAULT_REFMOD_ROOT),
            'paths':{k:str(v) for k,v in active.items()},
            'workshop_output':str(REFS.resolve()),
            'photo_library':str(REFERENCE_DIR.resolve()) if 'REFERENCE_DIR' in globals() else str((DATA/'reference_images').resolve()),
            'note':'Public FLUX includes celebs/ and legacy files directly in flux2/; personal/ is excluded. Missing folders are skipped. The native Refmod-Fork mount controls model loading and output.'}


def atomic_state_write(path,text):
    # Exclusive creation avoids following stale temporary symlinks or clobbering
    # another writer. Same-directory rename preserves the last committed state.
    temp=path.with_name(path.stem+'.'+uuid.uuid4().hex+'.tmp')
    created=False
    try:
        with temp.open('x',encoding='utf-8') as stream:
            created=True
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        if created:temp.unlink(missing_ok=True)


@app.put('/api/settings/paths')
def put_local_paths(settings:LocalPathsRequest):
    try:candidate=approved_refmod_root(settings.refmod_root)
    except (ValueError,TypeError) as exc:raise HTTPException(422,str(exc)) from exc
    # Only persist the root selection; never create, move or modify model files.
    try:
        with lock:atomic_state_write(PATHS_FILE,json.dumps({'refmod_root':str(candidate)},indent=2)+'\n')
    except OSError as exc:raise HTTPException(503,'Could not save library settings. Previous settings retained.') from exc
    invalidate_catalog_cache()
    if 'WORKSHOP_MOD_CACHE' in globals():WORKSHOP_MOD_CACHE['created']=0
    return get_local_paths()

CATALOG_SCAN_STATE={'running':False,'last_scanned':None,'checked':0,'total':0,'count':0,'phase':'Waiting'}
CATALOG_SCAN_LOCK=threading.RLock()
CATALOG_SCAN_WORKER=threading.Lock()

def invalidate_catalog_cache():
    # A scan already underway must not erase a later invalidation.
    with CATALOG_SCAN_LOCK:
        catalog_cache['until']=0
        catalog_cache['revision']+=1

CATALOG_SCAN_INFO=external_data_path(DATA/'catalog_last_scan.json')
try:
    stored=json.loads(CATALOG_SCAN_INFO.read_text(encoding='utf-8'))
    if isinstance(stored,dict):
        for key in ('last_scanned','checked','total','count'):
            if key in stored:CATALOG_SCAN_STATE[key]=stored[key]
except (OSError,ValueError):pass

@app.get('/api/catalog/scan-status')
def catalog_scan_status():
    with CATALOG_SCAN_LOCK:
        return dict(CATALOG_SCAN_STATE)

def picture_conversion_source(path):
    try:
        try:from ..conversion_bridge import safetensors_metadata,is_h3_picture_refmod
        except ImportError:from conversion_bridge import safetensors_metadata,is_h3_picture_refmod
        return is_h3_picture_refmod(safetensors_metadata(path,'refmod_meta'))
    except (ImportError,OSError,ValueError,TypeError,AttributeError):return False

def cached_public_inventory():
    with CATALOG_SCAN_LOCK:
        if time.monotonic()>=catalog_cache['until']:return None
        models=catalog_cache['models']
    private_names=personal_name_keys()
    return [m for m in models if token(m['name']) not in private_names]


def scan(force=False):
    # Cached readers stay responsive while an explicit refresh is running.
    # Cold readers recheck the cache after waiting for the single scan owner.
    if not force and (cached:=cached_public_inventory()) is not None:return cached
    with CATALOG_SCAN_WORKER:
        if not force and (cached:=cached_public_inventory()) is not None:return cached
        return scan_uncached()


def scan_uncached():
    with CATALOG_SCAN_LOCK:revision=catalog_cache['revision']
    private_names=personal_name_keys()
    active=effective_local_paths()
    roots=[(active['public_h3'],'minimax_h3'),(active['public_flux'],'flux2')]
    # pathlib does not descend into symlinked children during rglob. The
    # installed FLUX celebs directory is an explicit allowed public root.
    flux_public=(FLUX_REFS/'celebs').resolve()
    if active['public_flux']==FLUX_REFS.resolve() and (FLUX_REFS/'celebs').is_symlink():
        roots.append((flux_public,'flux2'))
    with CATALOG_SCAN_LOCK:
        CATALOG_SCAN_STATE.update(running=True,checked=0,total=0,phase='Enumerating .safetensors')
    try:
        candidates=[]
        for root,family in roots:
            if root.is_dir():
                for f in root.rglob('*.safetensors'):
                    if f.is_file():candidates.append((root,family,f))
        with CATALOG_SCAN_LOCK:
            CATALOG_SCAN_STATE.update(total=len(candidates),phase='Checking public model names')
        items=[];seen_paths=set()
        for i,(root,family,f) in enumerate(candidates,1):
            with CATALOG_SCAN_LOCK:CATALOG_SCAN_STATE['checked']=i
            if f.name.startswith('._') or f.is_symlink():continue
            if f.relative_to(root).parts[0].casefold()=='personal':continue
            if token(canonical_name(model_name(f))) in private_names:continue
            base=(REFS if family=='minimax_h3' else FLUX_REFS).resolve()
            physical=f.resolve()
            if any(physical.is_relative_to(p.resolve()) for p in (PERSONAL_H3,PERSONAL_FLUX)):continue
            if family=='flux2' and physical.is_relative_to(flux_public):
                relative='celebs/'+physical.relative_to(flux_public).as_posix()
            elif physical.is_relative_to(base):relative=physical.relative_to(base).as_posix()
            else:continue
            path=relative if family=='minimax_h3' else 'flux2/'+relative
            if (family,path) in seen_paths:continue
            seen_paths.add((family,path))
            convertible=picture_conversion_source(f) if family=='minimax_h3' else False
            items.append({'filename':f.name,'path':path,'name':canonical_name(model_name(f)),'family':family,'convertible_to_flux':convertible, 'role_specific':'__role__' in f.stem})
        items.sort(key=lambda x:(x['name'].casefold(),x['family'],x['path']))
        # A Personal profile may have been registered during enumeration.
        # Recheck before publishing, and leave the cache invalidated if any
        # concurrent identity/path mutation occurred while the scan was active.
        private_names=personal_name_keys()
        items=[m for m in items if token(m['name']) not in private_names]
        stamp=int(time.time())
        with CATALOG_SCAN_LOCK:
            catalog_cache.update(models=items,until=float('inf') if revision==catalog_cache['revision'] else 0)
            CATALOG_SCAN_STATE.update(last_scanned=stamp,count=len(items),phase='Complete')
            snapshot={k:CATALOG_SCAN_STATE[k] for k in ('last_scanned','checked','total','count')}
        try:
            atomic_state_write(CATALOG_SCAN_INFO,json.dumps(snapshot))
        except OSError:pass
        return items
    finally:
        with CATALOG_SCAN_LOCK:CATALOG_SCAN_STATE['running']=False

def personal_refmod_inventory():
    """Only dedicated, read-only /personal model files are eligible for Personal profiles.

    Public /celebs files are never offered as personal identity sources.
    """
    options={}
    for folder,family in ((effective_local_paths()['personal_h3'],'minimax_h3'),(effective_local_paths()['personal_flux'],'flux2')):
        if not folder.is_dir():continue
        for f in folder.rglob('*.safetensors'):
            if not f.is_file() or f.name.startswith('._') or f.is_symlink():continue
            base=(PERSONAL_H3 if family=='minimax_h3' else PERSONAL_FLUX).resolve()
            if not f.resolve().is_relative_to(base):continue
            relative=f.resolve().relative_to(base).as_posix()
            path=('personal/'+relative if family=='minimax_h3' else 'flux2/personal/'+relative)
            options[path]={'path':path,'filename':f.name,'family':family,'name':model_name(f),'source':'personal folder','convertible_to_flux':family=='minimax_h3' and picture_conversion_source(f)}
    return sorted(options.values(),key=lambda m:(m['family'],m['name'].casefold(),m['path']))

MODEL_OPTIONS=[
 {'id':'h3_video','label':'MiniMax H3 Ref2VA · video','kind':'video','family':'minimax_h3'},
 {'id':'h3_image','label':'MiniMax H3-Image 33B · 5 stills','kind':'image','family':'minimax_h3'},
 {'id':'h3_image_pruned','label':'MiniMax H3-Image Pruned 20B · 5 stills','kind':'image','family':'minimax_h3'},
 {'id':'p_h3_image','label':'Pruna P-H3-Image 20B · 5 stills','kind':'image','family':'minimax_h3'},
 {'id':'flux2_dev','label':'FLUX.2 Dev · 5 stills','kind':'image','family':'flux2'},
 {'id':'flux2_klein4','label':'FLUX.2 Klein 4B · 5 stills','kind':'image','family':'flux2'},
 {'id':'flux2_klein9','label':'FLUX.2 Klein 9B · 5 stills','kind':'image','family':'flux2'},
 {'id':'pi_flux2','label':'pi-FLUX.2 · 5 stills','kind':'image','family':'flux2'},
 {'id':'flux3_klein','label':'FLUX.3 Klein · 5 stills','kind':'image','family':'flux2'},
]
MODEL_BY_ID={m['id']:m for m in MODEL_OPTIONS}

@app.get('/api/models/options')
def available_models():return MODEL_OPTIONS

def selected_model(model):
    if model not in MODEL_BY_ID:raise HTTPException(400,'Unsupported image/video model')
    return MODEL_BY_ID[model]

@app.get('/api/profiles/gender')
def profile_gender_list():
    with connect() as db:return {token(canonical_name(k)):v for k,v in db.execute('SELECT name_key,symbol FROM profile_gender')}

class GenderEdit(BaseModel):
    name:str=Field(min_length=1,max_length=180)
    symbol:str=Field(default='',max_length=4)

@app.put('/api/profiles/gender')
def update_profile_gender(item:GenderEdit):
    if item.symbol not in ('','♀','♂','⚧'):
        raise HTTPException(400,'Choose an available symbol or clear the symbol')
    with lock,connect() as db:
        assert_public_name(item.name)
        name_key=token(canonical_name(item.name))
        for (old,) in db.execute('SELECT name_key FROM profile_gender').fetchall():
            if token(canonical_name(old))==name_key:
                db.execute('DELETE FROM profile_gender WHERE name_key=?',(old,))
        if item.symbol:db.execute('INSERT INTO profile_gender VALUES (?,?)',(name_key,item.symbol))
    return {'saved':True,'name':item.name,'symbol':item.symbol}

@app.get("/api/ui/icons/{name}")
def ui_icon(name: str):
    if name not in {"personal", "performers", "productions", "models", "adult", "workshop", "casting-logo", "television"}:
        raise HTTPException(404, "Unknown icon")
    return FileResponse(ROOT / "icons" / (name + ".png"), media_type="image/png",
                        headers={"Cache-Control": "public, max-age=604800"})

@app.get('/api/changelog')
def changelog():
    path=ROOT.parent/'CHANGELOG.md'
    if not path.is_file():raise HTTPException(404,'Changelog not found')
    return FileResponse(path,media_type='text/markdown',headers={'Cache-Control':'no-store'})

@app.get('/api/legal/{document}')
def legal_document(document: str):
    filename = {'license': 'LICENSE', 'notice': 'NOTICE.md'}.get(document)
    if filename is None:
        raise HTTPException(404, 'Unknown legal document')
    path = ROOT.parent / filename
    if not path.is_file() or path.is_symlink():
        raise HTTPException(404, 'Legal document not found')
    return FileResponse(path, media_type='text/plain', headers={
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

@app.get('/')
def home():
    # The inline HTML/JS is the application itself, not a cacheable static asset.
    return FileResponse(ROOT/'index.html',headers={'Cache-Control':'no-store, no-cache, must-revalidate','Pragma':'no-cache','Expires':'0'})

@app.get('/api/catalog')
def catalog(response:Response=None):
    models=scan()
    people,roles=normalized_catalog(models)
    with connect() as db:
        damaged=sum(decoded_cast(raw) is None for (raw,) in db.execute('SELECT payload FROM production_cast'))
        for table in ('profile_categories','public_profiles'):
            damaged+=sum(decoded_categories(raw) is None for (raw,) in db.execute('SELECT categories FROM '+table))
    if response is not None and damaged:response.headers['X-Casting-Catalog-Warning']='Damaged catalog records skipped; original data retained.'
    return {'models':models,'people':people,'roles':roles,'meta':{**DB['meta'],'mapped_roles_count':len(roles),'damaged_records':damaged}}

@app.post('/api/catalog/rescan')
def catalog_rescan():
    models=scan(force=True)
    WORKSHOP_MOD_CACHE['created']=0
    return {'ok': True, 'count': len(models)}

@app.get('/api/profiles/categories')
def get_profile_categories():
    with connect() as db:
        return {canonical_name(name):cats for name,categories in db.execute('SELECT name,categories FROM profile_categories') if (cats:=decoded_categories(categories)) is not None}

class ProfileCategories(BaseModel):
    name:str=Field(min_length=1,max_length=150)
    categories:list[str]=Field(default_factory=list,max_length=8)

@app.put('/api/profiles/categories')
def put_profile_categories(item:ProfileCategories):
    allowed={'Actor','Model','Influencer','Musician','TV personality','Comedian','Presenter','Other performer','Video game character','Unclassified'}
    if any(x not in allowed for x in item.categories):raise HTTPException(400,'Unknown performer category')
    with lock,connect() as db:
        assert_public_name(item.name)
        name=canonical_name(item.name)
        for (old,) in db.execute('SELECT name FROM profile_categories').fetchall():
            if token(canonical_name(old))==token(name) and old!=name:
                db.execute('DELETE FROM profile_categories WHERE name=?',(old,))
        db.execute('INSERT OR REPLACE INTO profile_categories(name,categories) VALUES (?,?)',(name,json.dumps(item.categories)))
    return {'saved':True}


# Labels are explicitly recorded by the local user; no identity markers are shipped.
ADULT_SEED=set()

@app.get('/api/profiles/markers')
def get_profile_markers():
    with connect() as db:
        overrides={token(canonical_name(name)):bool(flag) for name,flag in db.execute('SELECT name,adult FROM profile_markers')}
    names={p['name'] for p in normalized_catalog(discovery=True)[0]}
    return {name:overrides.get(token(name), token(name) in ADULT_SEED) for name in names if overrides.get(token(name),token(name) in ADULT_SEED)}

class ProfileMarker(BaseModel):
    name:str=Field(min_length=1,max_length=180)
    adult:bool

@app.put('/api/profiles/markers')
def put_profile_marker(item:ProfileMarker):
    with lock:
        assert_public_name(item.name)
        name_key=token(canonical_name(item.name))
        if name_key not in {token(p['name']) for p in normalized_catalog(discovery=True)[0]}:
            raise HTTPException(404,'Known public profile not found')
        with connect() as db:
            # Collapse older aliases for this marker so clearing is authoritative.
            for (old,) in db.execute('SELECT name FROM profile_markers').fetchall():
                if token(canonical_name(old))==name_key:
                    db.execute('DELETE FROM profile_markers WHERE name=?',(old,))
            db.execute('INSERT OR REPLACE INTO profile_markers(name,adult) VALUES (?,?)',(name_key,int(item.adult)))
    return {'name':item.name,'adult':item.adult}

@app.get('/api/profiles/link')
def get_profile_link(name:str=Query(min_length=1,max_length=180)):
    assert_public_name(name)
    if token(canonical_name(name)) in fictional_game_name_keys(include_damaged=True):
        raise HTTPException(400,'Video-game characters cannot be researched as human performers')
    # Wikidata's IMDb identifier is P345. Only link an exact public human identity;
    # otherwise use DuckDuckGo. Never present generic IMDb search as a verified profile.
    if token(name) not in {token(m['name']) for m in scan()}:
        raise HTTPException(404,'Installed RefMod profile not found')
    curated=CURATED_IMDB.get(token(name))
    if curated:return {'provider':'imdb','url':'https://www.imdb.com/name/'+curated+'/','verified':True}
    with connect() as db:
        public=db.execute('SELECT imdb_id FROM public_profiles WHERE name_key=?',(token(name),)).fetchone()
    if public and re.fullmatch(r'nm\d{7,10}',public[0] or ''):
        return {'provider':'imdb','url':'https://www.imdb.com/name/'+public[0]+'/','verified':True}
    default={'provider':'duckduckgo','url':'https://duckduckgo.com/?'+urlencode({'q':'"'+name+'" performer'}),'verified':False}
    now=int(time.time())
    with connect() as db:
        row=db.execute('SELECT imdb_url,checked FROM profile_links WHERE name=?',(token(name),)).fetchone()
    if row and now-row[1]<30*86400:
        return {'provider':'imdb','url':row[0],'verified':True} if row[0] else default
    imdb=''
    try:
        with httpx.Client(timeout=5,headers={'User-Agent':'CastingStudio/1.0.0-rc.12.20 (personal catalog)'}) as client:
            resp=client.get('https://www.wikidata.org/w/api.php',params={'action':'wbsearchentities','search':name,'language':'en','format':'json','limit':6,'type':'item'})
            resp.raise_for_status()
            candidates=[v for v in resp.json().get('search',[]) if token(v.get('label'))==token(name)]
            if candidates:
                ids='|'.join(x['id'] for x in candidates[:6])
                entity=client.get('https://www.wikidata.org/w/api.php',params={'action':'wbgetentities','ids':ids,'props':'claims','format':'json'})
                entity.raise_for_status()
                found=set()
                for candidate in candidates:
                    claims=entity.json().get('entities',{}).get(candidate['id'],{}).get('claims',{})
                    human=any(str(c.get('mainsnak',{}).get('datavalue',{}).get('value',{}).get('id',''))=='Q5' for c in claims.get('P31',[]))
                    if human:
                        for c in claims.get('P345',[]):
                            val=c.get('mainsnak',{}).get('datavalue',{}).get('value','')
                            if isinstance(val,str) and re.fullmatch(r'nm\d{7,10}',val):found.add(val)
                if len(found)==1:imdb='https://www.imdb.com/name/'+next(iter(found))+'/'
    except Exception:
        # Transient network issues should not be cached as a permanent negative.
        return default
    with lock,connect() as db:
        db.execute('INSERT OR REPLACE INTO profile_links(name,imdb_url,checked) VALUES (?,?,?)',(token(name),imdb,now))
    return {'provider':'imdb','url':imdb,'verified':True} if imdb else default

class IdentityEdit(BaseModel):
    original_name:str=Field(min_length=1,max_length=180)
    display_name:str=Field(min_length=2,max_length=180)

@app.get('/api/identities')
def list_identities():
    return {'known':KNOWN_IDENTITIES, 'overrides':identity_overrides}

@app.put('/api/identities')
def put_identity(item:IdentityEdit):
    original_key=token(item.original_name)
    display_name=' '.join(item.display_name.split())
    if not original_key or not token(display_name) or not re.fullmatch(r"[\w .,'’()\-]+",display_name,re.UNICODE):
        raise HTTPException(400,'Invalid identity')
    # Existing models and saved public identities share the local alias registry.
    with lock:
        assert_public_name(item.original_name);assert_public_name(display_name)
        current_key=token(canonical_name(item.original_name))
        known={token(p['name']) for p in normalized_catalog(discovery=True)[0]}
        if current_key not in known and original_key not in {token(model_name(Path(m['path']))) for m in scan()}:
            raise HTTPException(400,'Original identity not found in the catalog')
        target_key=token(display_name)
        if target_key!=current_key and (target_key in known or (target_key in identity_overrides and token(canonical_name(display_name))!=current_key)):
            raise HTTPException(409,'That display name belongs to another public identity')
        # Flatten aliases already pointing to the same identity, including repeated corrections.
        keys={original_key,current_key}|{k for k,v in identity_overrides.items() if token(v)==current_key}
        with connect() as db:
            for k in keys:
                db.execute('INSERT OR REPLACE INTO identity_names(key,display_name) VALUES(?,?)',(k,display_name))
        refresh_identities()
    scan(force=True)
    return {'saved':True,'original_key':original_key,'display_name':display_name}

@app.get('/api/identities/review.csv')
def identity_review():
    import csv
    sio=io.StringIO()
    writer=csv.writer(sio)
    writer.writerow(['current_path','current_name','suggested_display_name','status'])
    for m in scan():
        raw=model_name(Path(m['path']))
        tag=token(raw)
        chosen=canonical_name(raw)
        status='user-corrected' if tag in identity_overrides else 'verified-correction' if tag in KNOWN_IDENTITIES else 'needs-review' if chosen==raw and '_' not in Path(m['path']).stem else 'mapped'
        writer.writerow([m['path'],raw,chosen,status])
    return Response(sio.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="refmod_identity_review.csv"'})


# Public Wikidata search: professional-category metadata only. Never infer personal
# demographic attributes from a photo, name, or unverified search result.
class ResearchCancelled(Exception):
    pass

WIKIDATA_TEMPORARY={429,500,502,503,504}

def wikidata_get(client,params):
    # Retry transient response/transport failures. Stop button cancels backoff.
    last_error=None
    for attempt in range(5):
        if ENRICH_STOP.is_set():raise ResearchCancelled()
        try:
            response=client.get('https://www.wikidata.org/w/api.php',params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            last_error=exc
            if exc.response.status_code not in WIKIDATA_TEMPORARY or attempt==4:raise
            retry_header=exc.response.headers.get('Retry-After','').strip()
            try: delay=max(1,min(90,float(retry_header)))
            except ValueError:delay=min(80,5*(2**attempt))
        except (httpx.TimeoutException,httpx.TransportError) as exc:
            last_error=exc
            if attempt==4:raise
            delay=min(80,5*(2**attempt))
        if ENRICH_STOP.wait(delay):raise ResearchCancelled()
    raise last_error

def wikidata_profile(name):
    with httpx.Client(timeout=20, headers={'User-Agent':'CastingStudio/1.0.0-rc.12.20 (public performer metadata; respectful research)'}) as client:
        search=wikidata_get(client,{
            'action':'wbsearchentities','search':name,'language':'en','format':'json','type':'item','limit':8})
        candidates=[c for c in search.get('search',[]) if token(c.get('label',''))==token(name) or
                    any(token(a)==token(name) for a in c.get('aliases',[]))]
        if not candidates:return {'status':'unmatched','categories':[],'imdb_id':'','qid':'','label':''}
        # Pace a second call to avoid a burst of Wikidata requests.
        if ENRICH_STOP.wait(0.75):raise ResearchCancelled()
        ids='|'.join(c['id'] for c in candidates[:8])
        entities=wikidata_get(client,{
            'action':'wbgetentities','ids':ids,'props':'claims|labels','languages':'en','format':'json'}).get('entities',{})
        matches=[]
        def entity_values(claims,prop):
            return [v.get('mainsnak',{}).get('datavalue',{}).get('value') for v in claims.get(prop,[])]
        for candidate in candidates:
            data=entities.get(candidate['id'],{})
            claims=data.get('claims',{})
            if not any(isinstance(q,dict) and q.get('id')=='Q5' for q in entity_values(claims,'P31')):
                continue
            occ=set()
            for q in entity_values(claims,'P106'):
                if isinstance(q,dict) and q.get('id') in OCCUPATIONS:occ.add(OCCUPATIONS[q['id']])
            imdbids=[v for v in entity_values(claims,'P345') if isinstance(v,str) and re.fullmatch(r'nm\d{7,10}',v)]
            matches.append({'status':'matched','categories':sorted(occ),'imdb_id':imdbids[0] if imdbids else '',
                            'qid':candidate['id'],'label':candidate.get('label','')})
        if len(matches)!=1:return {'status':'ambiguous' if matches else 'unmatched','categories':[],'imdb_id':'','qid':'','label':''}
        return matches[0]

def research_error_record(name,exc):
    http_status=exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None
    detail=str(exc).strip()[:600] or repr(exc)
    typ=type(exc).__name__
    with lock,connect() as db:
        db.execute('''INSERT INTO enrichment_failures
            (name_key,name,error_type,http_status,error_detail,attempts,last_checked)
            VALUES (?,?,?,?,?,1,?) ON CONFLICT(name_key) DO UPDATE SET
            name=excluded.name,error_type=excluded.error_type,http_status=excluded.http_status,
            error_detail=excluded.error_detail,attempts=attempts+1,last_checked=excluded.last_checked''',
            (token(name),name,typ,http_status,detail,int(time.time())))
    return (f'HTTP {http_status} ' if http_status else '')+typ+': '+detail

def enrichment_job(mode='all'):
    try:
        people,_=normalized_catalog()
        fictional=fictional_game_name_keys(include_damaged=True)
        allowed={token(p['name']):p['name'] for p in people if token(p['name']) not in fictional}
        with connect() as db:
            existing={key:(status,checked) for key,status,checked in db.execute('SELECT name_key,status,checked FROM public_profiles')}
            failures={k for (k,) in db.execute('SELECT name_key FROM enrichment_failures')}
        now=int(time.time())
        if mode=='errors':
            todo=[name for key,name in allowed.items() if key in failures]
        else:
            todo=[name for key,name in allowed.items() if key not in existing or now-existing[key][1] > 30*86400 or key in failures]
        with ENRICH_LOCK:
            ENRICH_STATE.update(total=len(todo),done=0,matched=0,classified=0,failed=0,last='',last_error='')
        for name in todo:
            if ENRICH_STOP.is_set():break
            # Re-evaluate privacy at execution time: users may add a Personal profile while running.
            if token(name) in personal_name_keys() or token(name) in fictional_game_name_keys(include_damaged=True):
                with ENRICH_LOCK:ENRICH_STATE['done']+=1
                continue
            try:
                result=wikidata_profile(name)
                with lock,connect() as db:
                    db.execute('INSERT OR REPLACE INTO public_profiles(name_key,matched_name,qid,imdb_id,categories,status,checked) VALUES(?,?,?,?,?,?,?)',
                               (token(name),result['label'],result['qid'],result['imdb_id'],json.dumps(result['categories']),result['status'],int(time.time())))
                    db.execute('DELETE FROM enrichment_failures WHERE name_key=?',(token(name),))
                with ENRICH_LOCK:
                    ENRICH_STATE['matched']+=int(result['status']=='matched')
                    ENRICH_STATE['classified']+=int(bool(result['categories']))
                    ENRICH_STATE['last']=name+' — '+result['status']
            except ResearchCancelled:
                break
            except Exception as exc:
                try:reason=research_error_record(name,exc)
                except Exception as log_exc:reason=f'{type(exc).__name__}: {str(exc)[:200]} (error-log failure: {type(log_exc).__name__})'
                with ENRICH_LOCK:
                    ENRICH_STATE['failed']+=1
                    ENRICH_STATE['last']=name+' — '+type(exc).__name__
                    ENRICH_STATE['last_error']=name+' — '+reason
                print('Research failure:',name,reason,flush=True)
            finally:
                with ENRICH_LOCK:ENRICH_STATE['done']+=1
            if ENRICH_STOP.wait(2.5):break
    except Exception as exc:
        # A setup failure previously left the UI looking like a completed research job.
        with ENRICH_LOCK:
            ENRICH_STATE['last_error']='Research job failed to start: '+type(exc).__name__+': '+str(exc)[:400]
        print(ENRICH_STATE['last_error'],flush=True)
    finally:
        with ENRICH_LOCK:ENRICH_STATE['running']=False

# Filmography discovery. Only verified person-level credits with named roles.
CREDIT_LOCK=threading.Lock()
CREDIT_STOP=threading.Event()
CREDIT_STATE={'running':False,'total':0,'done':0,'added':0,'failed':0,'last':'','error':''}
CREDIT_THREAD=None
CREDIT_PENDING=[]
CREDIT_ACTIVE=''
AUTO_CREDIT_STOP=threading.Event()


def sync_one_public_person(name):
    assert_public_name(name)
    person_key=token(canonical_name(name))
    if person_key in personal_name_keys():raise ValueError('Personal profiles cannot be researched')
    if person_key in fictional_game_name_keys(include_damaged=True):raise ValueError('Video-game characters cannot be researched as human performers')
    people,_=normalized_catalog(discovery=True)
    if person_key not in {token(x['name']) for x in people}:
        raise ValueError('Only known public performers can be researched')
    records, warnings=fetch_credits(name)
    inserted=0
    with lock,connect() as db:
        for r in records:
            production=canonical_production(r['production'])
            role=r['character'].strip()
            if not role or not production:continue
            # Skip numbered copies when the unnumbered role is already known.
            numbered=re.fullmatch(r'(.+?)\s+([2-9]|[1-9][0-9])',role)
            if numbered:
                baseline=canonical_role_key(name,numbered.group(1),production)
                if db.execute('SELECT 1 FROM production_cast WHERE key=?',(baseline,)).fetchone():
                    continue
            record={'actress':canonical_name(name),'character':role,'production':production,
                    'year':r.get('year'),'image':r.get('image',''),'source':r.get('source','')}
            existing=db.execute('INSERT OR IGNORE INTO production_cast (key,payload) VALUES (?,?)',
                    (canonical_role_key(name,role,production),json.dumps(record,ensure_ascii=False)))
            inserted+=existing.rowcount
            db.execute('INSERT OR IGNORE INTO productions(key,name,year,kind) VALUES (?,?,?,?)',
                       (token(production),production,r.get('year'),r.get('kind','other')))
        db.execute('INSERT OR REPLACE INTO credit_refresh(name_key,checked,count,status,detail) VALUES (?,?,?,?,?)',
                   (person_key,int(time.time()),len(records),'ok','; '.join(warnings)[:400]))
    return {'person':name,'discovered':len(records),'added':inserted,'warnings':warnings}


def credit_sync_worker():
    global CREDIT_ACTIVE
    try:
        while not CREDIT_STOP.is_set():
            with CREDIT_LOCK:
                if not CREDIT_PENDING:break
                name=CREDIT_PENDING.pop(0)
                CREDIT_ACTIVE=name
            if token(name) in personal_name_keys() or token(name) in fictional_game_name_keys(include_damaged=True):
                with CREDIT_LOCK:CREDIT_STATE['done']+=1
                continue
            try:
                result=sync_one_public_person(name)
                with CREDIT_LOCK:
                    CREDIT_STATE['added']+=result['added'];CREDIT_STATE['last']=name
            except Exception as e:
                # Failed imports must not remove known/manual roles. Retry later.
                with lock,connect() as db:
                    db.execute('INSERT OR REPLACE INTO credit_refresh(name_key,checked,count,status,detail) VALUES (?,?,?,?,?)',
                               (token(name),int(time.time()),0,'error',f'{type(e).__name__}: {e}'[:400]))
                with CREDIT_LOCK:
                    CREDIT_STATE['failed']+=1;CREDIT_STATE['last']=name
                    CREDIT_STATE['error']=f'{name}: {str(e)[:160]}'
            finally:
                with CREDIT_LOCK:CREDIT_STATE['done']+=1
            if CREDIT_STOP.wait(8):break  # polite pacing for public services
    finally:
        with CREDIT_LOCK:
            CREDIT_ACTIVE=''
            CREDIT_PENDING.clear()
            CREDIT_STATE['running']=False


def launch_credit_sync(names):
    global CREDIT_THREAD
    names=list(dict.fromkeys(names))
    if not names:return False
    with CREDIT_LOCK:
        if CREDIT_STATE['running']:return False
        CREDIT_PENDING[:]=names
        CREDIT_STATE.update(running=True,total=len(names),done=0,added=0,failed=0,last='',error='')
        CREDIT_STOP.clear()
    try:
        CREDIT_THREAD=threading.Thread(target=credit_sync_worker,daemon=True,name='casting-credit-sync')
        CREDIT_THREAD.start()
    except Exception as exc:
        with CREDIT_LOCK:
            CREDIT_THREAD=None;CREDIT_PENDING.clear();CREDIT_STATE.update(running=False,error='Could not start credit worker')
        raise HTTPException(503,'Could not start credit worker; retry.') from exc
    return True


def prioritize_credit_refresh(name):
    """Move one public performer to the front of an active bulk sync."""
    with CREDIT_LOCK:
        if not CREDIT_STATE['running']:
            return False
        if name in CREDIT_PENDING:
            CREDIT_PENDING.remove(name)
            CREDIT_PENDING.insert(0,name)
        elif name != CREDIT_ACTIVE:
            CREDIT_PENDING.insert(0,name)
            CREDIT_STATE['total']+=1
        return True

@app.get('/api/credits/status')
def credit_sync_status():
    with CREDIT_LOCK: result=dict(CREDIT_STATE)
    with connect() as db:
        result['last_refresh']=db.execute('SELECT MAX(checked) FROM credit_refresh').fetchone()[0]
    return result

class CreditRefreshRequest(BaseModel):
    person:str=''  # empty = refresh installed public performers due for update
    force:bool=False

@app.post('/api/credits/refresh')
def credit_refresh(item:CreditRefreshRequest):
    people,_=normalized_catalog()
    fictional=fictional_game_name_keys(include_damaged=True)
    public={token(p['name']):p['name'] for p in people if token(p['name']) not in personal_name_keys() and token(p['name']) not in fictional}
    if item.person:
        name=public.get(token(item.person))
        if not name:raise HTTPException(404,'Installed public performer not found')
        if prioritize_credit_refresh(name):
            return {'started':True,'prioritized':True,'pending':1,'reason':'This performer will be refreshed next'}
        names=[name]
    else:
        with connect() as db:
            checked={k:(v,status) for k,v,status in db.execute('SELECT name_key,checked,status FROM credit_refresh')}
        now=int(time.time())
        names=[name for k,name in public.items() if (item.force or k not in checked or
                now-checked[k][0] > (7*86400 if checked[k][1]=='ok' else 12*3600))]
        # Bring newer/no-roles performers forward, but do not flood the providers.
        names.sort(key=lambda n:(checked.get(token(n),(0,''))[0],n.casefold()))
    started=launch_credit_sync(names)
    return {'started':started,'pending':len(names),'reason':'' if started else 'Credit refresh already running or nothing is due'}

@app.post('/api/credits/stop')
def credit_stop():
    CREDIT_STOP.set();return {'stopping':True}

@app.get('/api/maintenance/activity')
def maintenance_activity():
    """Read-only, cheap status of jobs a user intentionally started.

    The endpoint never launches research, rescans, image prefetch, or downloads.
    It also reports any pre-upgrade worker that remains active until restart.
    """
    jobs=[]
    with CREDIT_LOCK:
        c=dict(CREDIT_STATE)
    if c.get('running'):
        jobs.append({'id':'credits','label':'Screen-role synchronization',
                     'done':c.get('done',0),'total':c.get('total',0),
                     'detail':c.get('last','')})
    with ENRICH_LOCK:
        e=dict(ENRICH_STATE)
    if e.get('running'):
        jobs.append({'id':'enrichment','label':'Performer classification',
                     'done':e.get('done',0),'total':e.get('total',0),
                     'detail':e.get('last','')})
    with prefetch_lock:
        p=dict(prefetch_state)
    if p.get('running'):
        jobs.append({'id':'prefetch','label':'Photo prefetch',
                     'done':p.get('done',0),'total':p.get('total',0),
                     'detail':p.get('last','')})
    if archive_thread and archive_thread.is_alive():
        jobs.append({'id':'archive','label':'Archiving photographs',
                     'done':None,'total':None,'detail':''})
    with CATALOG_SCAN_LOCK:
        c=dict(CATALOG_SCAN_STATE)
    if c.get('running'):
        jobs.append({'id':'catalog','label':'RefMod inventory scan',
                     'done':c.get('checked',0),'total':c.get('total',0),
                     'detail':c.get('phase','')})
    with WORKSHOP_SCAN_LOCK:
        w=dict(WORKSHOP_SCAN_STATE)
    if w.get('running'):
        jobs.append({'id':'workshop','label':'Workshop RefMod validation',
                     'done':w.get('checked',0),'total':w.get('total',0),
                     'detail':w.get('phase','')})
    bridge=getattr(app.state,'casting_vision_bridge',None)
    result={'running':bool(jobs),'count':len(jobs),'jobs':jobs}
    if bridge and (appearance:=bridge.summary()):result['appearance']=appearance
    return result

@app.get('/api/enrichment/status')
def enrichment_status():
    with ENRICH_LOCK:state=dict(ENRICH_STATE)
    with connect() as db:
        state['recorded_errors']=db.execute('SELECT COUNT(*) FROM enrichment_failures').fetchone()[0]
    return state

@app.post('/api/enrichment/start')
def enrichment_start():
    with ENRICH_LOCK:
        if ENRICH_STATE['running']:return {'started':False,'reason':'already running'}
        ENRICH_STATE['running']=True;ENRICH_STOP.clear()
    try:threading.Thread(target=enrichment_job,kwargs={'mode':'all'},daemon=True).start()
    except Exception as exc:
        with ENRICH_LOCK:ENRICH_STATE.update(running=False,last_error='Could not start research worker')
        raise HTTPException(503,'Could not start research worker; retry.') from exc
    return {'started':True}

@app.post('/api/enrichment/retry-errors')
def enrichment_retry_errors():
    with ENRICH_LOCK:
        if ENRICH_STATE['running']:return {'started':False,'reason':'already running'}
        ENRICH_STATE['running']=True;ENRICH_STOP.clear()
    try:threading.Thread(target=enrichment_job,kwargs={'mode':'errors'},daemon=True).start()
    except Exception as exc:
        with ENRICH_LOCK:ENRICH_STATE.update(running=False,last_error='Could not start research worker')
        raise HTTPException(503,'Could not start research worker; retry.') from exc
    return {'started':True}

@app.post('/api/enrichment/stop')
def enrichment_stop():
    ENRICH_STOP.set();return {'stopping':True}

@app.get('/api/enrichment/errors.csv')
def enrichment_errors_csv():
    import csv
    private=personal_name_keys()
    buf=io.StringIO();writer=csv.writer(buf)
    writer.writerow(['name','error_type','http_status','detail','attempts','last_checked_unix'])
    with connect() as db:
        rows=db.execute('SELECT name_key,name,error_type,http_status,error_detail,attempts,last_checked FROM enrichment_failures ORDER BY last_checked DESC').fetchall()
    for key,name,err_type,http_status,detail,attempts,checked in rows:
        if key not in private:writer.writerow([name,err_type,http_status or '',detail,attempts,checked])
    return Response(buf.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="refmod_research_errors.csv"'})

@app.get('/api/enrichment/review.csv')
def enrichment_review():
    import csv
    out=io.StringIO();w=csv.writer(out)
    w.writerow(['name','classification','status','wikidata_id','imdb_id','source'])
    people,_=normalized_catalog()
    with connect() as db:
        public={k:(qid,imdb,status) for k,qid,imdb,status in db.execute('SELECT name_key,qid,imdb_id,status FROM public_profiles')}
    for p in people:
        qid,imdb,status=public.get(token(p['name']),('','','not checked'))
        w.writerow([p['name'],p['type'],status,qid,imdb,'https://www.wikidata.org/wiki/'+qid if qid else ''])
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="refmod_classification_review.csv"'})

# v6.8 — Personal profiles: locally stored metadata and portraits, no public enrichment.
def get_personal_rows():
    with connect() as db:
        rows=db.execute("""SELECT id,name,name_key,relationship,notes,consent,portrait,h3_refmod,flux_refmod
                             FROM personal_profiles ORDER BY name COLLATE NOCASE""").fetchall()
    keys=('id','name','name_key','relationship','notes','consent','portrait','h3_refmod','flux_refmod')
    return [dict(zip(keys,row)) for row in rows]

def personal_row_by_id(personal_id):
    with connect() as db:
        row=db.execute('SELECT id,name,name_key,relationship,notes,consent,portrait,h3_refmod,flux_refmod FROM personal_profiles WHERE id=?',(personal_id,)).fetchone()
    return dict(zip(('id','name','name_key','relationship','notes','consent','portrait','h3_refmod','flux_refmod'),row)) if row else None

class PersonalPayload(BaseModel):
    name:str=Field(min_length=1,max_length=160)
    relationship:str=Field(default='',max_length=240)
    notes:str=Field(default='',max_length=4000)
    consent:bool=False
    h3_refmod:str=Field(default='',max_length=500)
    flux_refmod:str=Field(default='',max_length=500)

def validate_personal_links(item,previous=None):
    known={m['path']:m for m in personal_refmod_inventory()}
    for field,family in (('h3_refmod','minimax_h3'),('flux_refmod','flux2')):
        value=getattr(item,field)
        if value and (value not in known or known[value]['family']!=family):
            if previous and previous[field]==value:continue  # Preserve legacy value only for editing/revoking consent; not exportable.
            raise HTTPException(400,'RefMod must be chosen from available '+family+' files')

@app.get('/api/personal/refmods')
def personal_refmods():
    return personal_refmod_inventory()

@app.get('/api/personal')
def personal_list():
    found={m['path'] for m in personal_refmod_inventory()}
    out=[]
    for row in get_personal_rows():
        out.append({'id':row['id'],'name':row['name'],'relationship':row['relationship'],
            'notes':row['notes'],'consent':bool(row['consent']),
            'portrait_url':'api/personal/portraits/'+row['portrait'] if row['portrait'] else '',
            'h3_refmod':row['h3_refmod'],'flux_refmod':row['flux_refmod'],
            'h3_installed':bool(row['h3_refmod'] and row['h3_refmod'] in found),
            'flux_installed':bool(row['flux_refmod'] and row['flux_refmod'] in found),
            'needs_private_relink':bool((row['h3_refmod'] and row['h3_refmod'] not in found) or
                                        (row['flux_refmod'] and row['flux_refmod'] not in found))})
    return out

@app.post('/api/personal')
def personal_add(item:PersonalPayload):
    name=item.name.strip()
    if not token(name):raise HTTPException(400,'Enter a name containing a letter or number')
    validate_personal_links(item)
    uid=uuid.uuid4().hex
    with lock,connect() as db:
        try:
            db.execute('INSERT INTO personal_profiles(id,name,name_key,relationship,notes,consent,h3_refmod,flux_refmod,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                (uid,name,token(name),item.relationship.strip(),item.notes,int(item.consent),item.h3_refmod,item.flux_refmod,int(time.time())))
        except sqlite3.IntegrityError:raise HTTPException(409,'A Personal entry with that name already exists')
    invalidate_catalog_cache()
    return {'id':uid,'saved':True}

@app.put('/api/personal/{personal_id}')
def personal_update(personal_id:str,item:PersonalPayload):
    before=personal_row_by_id(personal_id)
    if not before:raise HTTPException(404,'Personal entry not found')
    name=item.name.strip()
    if not token(name):raise HTTPException(400,'Enter a name containing a letter or number')
    # Selection uses the original name as its key. Prevent renaming after selection
    # unless all associated choices have been removed.
    if token(name)!=before['name_key']:
        with connect() as db:
            selected=[]
            for (raw,) in db.execute('SELECT payload FROM choices'):
                try:saved=json.loads(raw)
                except (ValueError,TypeError):continue
                if isinstance(saved,dict):selected.append(saved)
        if any(c.get('personal_id')==personal_id for c in selected):
            raise HTTPException(409,'Remove this person from My Selections before changing their name')
    validate_personal_links(item,before)
    with lock,connect() as db:
        try:
            db.execute('UPDATE personal_profiles SET name=?,name_key=?,relationship=?,notes=?,consent=?,h3_refmod=?,flux_refmod=?,updated_at=? WHERE id=?',
                       (name,token(name),item.relationship.strip(),item.notes,int(item.consent),item.h3_refmod,item.flux_refmod,int(time.time()),personal_id))
        except sqlite3.IntegrityError:raise HTTPException(409,'A Personal entry with that name already exists')
    invalidate_catalog_cache()
    return {'saved':True}

@app.delete('/api/personal/{personal_id}')
def personal_remove(personal_id:str):
    before=personal_row_by_id(personal_id)
    if not before:raise HTTPException(404,'Personal entry not found')
    with lock,connect() as db:
        db.execute('DELETE FROM personal_profiles WHERE id=?',(personal_id,))
        db.execute('DELETE FROM final_prompt_edits WHERE personal_id=?',(personal_id,))
        for key,payload in db.execute('SELECT key,payload FROM choices').fetchall():
            try:
                data=json.loads(payload)
                if not isinstance(data,dict):continue
                if (data.get('personal_id')==personal_id or
                    (token(data.get('person',''))==before['name_key'] and
                     not data.get('character') and not data.get('production'))):
                    db.execute('DELETE FROM choices WHERE key=?',(key,))
            except (ValueError,TypeError):pass
    remove_owned_portrait(before['portrait'],personal_id)
    invalidate_catalog_cache()
    return {'removed':True}

@app.post('/api/personal/{personal_id}/portrait')
async def personal_portrait_upload(personal_id:str,request:Request):
    before=personal_row_by_id(personal_id)
    if not before:raise HTTPException(404,'Personal entry not found')
    if request.headers.get('content-type','').split(';')[0].strip().lower() not in ('image/png','image/jpeg','image/webp'):
        raise HTTPException(415,'Upload a JPEG, PNG or WebP portrait')
    # Stream and cap bytes before buffering the image (8 MiB maximum).
    parts=[];size=0
    async for chunk in request.stream():
        size+=len(chunk)
        if size>8*1024*1024:raise HTTPException(413,'Maximum portrait size is 8 MB')
        parts.append(chunk)
    body=b''.join(parts)
    if not body:raise HTTPException(400,'Choose a portrait file')
    try:
        with Image.open(io.BytesIO(body)) as picture:
            if picture.format not in ('JPEG','PNG','WEBP'):raise ValueError('Unsupported format')
            if picture.width*picture.height>40_000_000:raise ValueError('Portrait exceeds 40 megapixels')
            if picture.width<100 or picture.height<100:raise ValueError('Portrait is too small')
            picture.load()
            rgb=ImageOps.exif_transpose(picture).convert('RGB')
            rgb.thumbnail((1400,1400),Image.Resampling.LANCZOS)
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as e:
        raise HTTPException(400,'Invalid portrait image: '+str(e)[:120])
    filename=personal_id+'-'+uuid.uuid4().hex[:10]+'.webp'
    dest=PERSONAL_PORTRAITS/filename
    with lock:
        current=personal_row_by_id(personal_id)
        if not current:raise HTTPException(404,'Personal profile was removed during upload')
        if current['portrait']!=before['portrait']:raise HTTPException(409,'Portrait changed during upload; retry if you want to replace it')
        try:
            rgb.save(dest,format='WEBP',quality=90)
            with connect() as db:
                db.execute('UPDATE personal_profiles SET portrait=?,updated_at=? WHERE id=?',(filename,int(time.time()),personal_id))
        except Exception as exc:
            try:dest.unlink(missing_ok=True)
            except OSError:pass
            raise HTTPException(503,'Could not save portrait; previous portrait retained.') from exc
        remove_owned_portrait(current['portrait'],current['id'])
    return {'saved':True,'portrait_url':'api/personal/portraits/'+filename}

def remove_owned_portrait(filename,personal_id):
    if not isinstance(filename,str) or not filename.startswith(personal_id+'-'):return
    path=safe_media_file(PERSONAL_PORTRAITS,filename,r'[0-9a-f]{32}-[0-9a-f]{10}\.webp')
    if path:path.unlink(missing_ok=True)

@app.get('/api/personal/portraits/{filename}')
def personal_portrait_file(filename:str):
    if not re.fullmatch(r'[0-9a-f]{32}-[0-9a-f]{10}\.webp',filename):raise HTTPException(404,'Portrait not found')
    with connect() as db:
        active=db.execute('SELECT 1 FROM personal_profiles WHERE portrait=?',(filename,)).fetchone()
    p=safe_media_file(PERSONAL_PORTRAITS,filename)
    if not active or not p:raise HTTPException(404,'Portrait not found')
    return FileResponse(p,media_type='image/webp',headers={'Cache-Control':'private, no-store'})

def decoded_choice(key,raw):
    try:
        item=json.loads(raw)
        if not isinstance(item,dict):return None
        if any(not isinstance(item.get(field),str) for field in ('key','person','character','production','refmod')):return None
        if item['key']!=key or not item['person'].strip() or not item['refmod'].strip():return None
        if not isinstance(item.get('personal_id',''),str):return None
        if item.get('year') is not None and (type(item['year']) is not int or not 1880<=item['year']<=2100):return None
        return item
    except (ValueError,TypeError):return None


def require_choice(key,raw):
    item=decoded_choice(key,raw)
    if item is None:raise HTTPException(409,'A saved casting selection is damaged. Re-select the role or explicitly remove all selections to repair it.')
    return item


def read_choices(db):
    good=[];damaged=[]
    for key,raw in db.execute('SELECT key,payload FROM choices ORDER BY key'):
        item=decoded_choice(key,raw)
        if item is None:damaged.append(key)
        else:good.append(item)
    return good,damaged


@app.get('/api/choices')
def get_choices(response:Response=None):
    with connect() as db:items,damaged=read_choices(db)
    if response is not None and damaged:response.headers['X-Casting-Choice-Warning']=str(len(damaged))
    return items

class Choice(BaseModel):
    key:str; person:str; character:str; production:str; refmod:str; personal_id:str=''; year:int|None=Field(default=None,ge=1880,le=2100)

@app.put('/api/choices')
def put_choice(item:Choice):
    # Never accept selections without a real installed RefMod.
    public_matches={m['path']:m for m in scan()}
    private_matches={m['path']:m for m in personal_refmod_inventory()}
    person_by_name={r['name_key']:r for r in get_personal_rows()}
    personal=personal_row_by_id(item.personal_id) if item.personal_id else person_by_name.get(token(canonical_name(item.person)))
    if item.personal_id and not personal:raise HTTPException(404,'Personal profile not found')
    if not item.personal_id:assert_public_name(item.person)
    if personal:
        if not item.personal_id:raise HTTPException(403,'Use the Personal tab for this profile')
        if not personal['consent']:raise HTTPException(403,'Consent must be recorded before selecting this Personal profile')
        if token(item.person)!=personal['name_key']:raise HTTPException(400,'Personal selection name does not match profile')
        if item.character or item.production:raise HTTPException(400,'Personal prompts use the person as themselves in a studio')
        if item.refmod not in (personal['h3_refmod'],personal['flux_refmod']):
            raise HTTPException(400,'Personal profile is not linked to the selected RefMod')
    matches=private_matches if personal else public_matches
    if item.refmod not in matches:
        raise HTTPException(400,'Selection requires an installed RefMod in the correct public/private directory')
    if not personal and token(canonical_name(item.person)) != token(matches[item.refmod]['name']):
        raise HTTPException(400,'RefMod does not match the selected performer')
    with lock,connect() as db:
        if not personal:assert_public_name(item.person)
        else:
            current=personal_row_by_id(personal['id'])
            if not current or not current['consent'] or current['name_key']!=personal['name_key'] or item.refmod not in (current['h3_refmod'],current['flux_refmod']):
                raise HTTPException(409,'Personal profile changed during selection; refresh and try again')
        payload=item.model_dump(exclude_none=True)
        payload['person']=personal['name'] if personal else canonical_name(payload['person'])
        payload['personal_id']=personal['id'] if personal else ''
        explicit_year=re.search(r'\b((?:18|19|20)\d{2})\)?\s*$',payload['production'])
        if explicit_year and 1880<=int(explicit_year.group(1))<=2100:payload['year']=int(explicit_year.group(1))
        payload['production']=canonical_production(payload['production'])
        payload['key']=canonical_role_key(payload['person'],payload['character'],payload['production'])
        db.execute('INSERT OR REPLACE INTO choices VALUES (?,?)',(payload['key'],json.dumps(payload)))
    return {'saved':True}

class ProductionSelectionSet(BaseModel):
    production:str=Field(min_length=1,max_length=180)
    family:str

@app.get('/api/production-selection-set')
def get_production_selection_set(production:str=Query(min_length=1,max_length=180),family:str='minimax_h3'):
    if family not in ('minimax_h3','flux2'):raise HTTPException(400,'Unknown RefMod family')
    assert_public_name(production)
    with connect() as db:row=db.execute('SELECT payload FROM production_selection_sets WHERE production=? AND family=?',(token(canonical_production(production)),family)).fetchone()
    if not row:return {'choices':[]}
    try:
        data=json.loads(row[0])
        if not isinstance(data,list) or any(not isinstance(x,dict) or not decoded_choice(x.get('key'),json.dumps(x)) or x.get('personal_id') or x['key']!=canonical_role_key(x['person'],x['character'],x['production']) for x in data):raise ValueError('Invalid set')
    except (TypeError,ValueError):raise HTTPException(409,'Saved production selections are damaged')
    return {'choices':data}

@app.put('/api/production-selection-set')
def save_production_selection_set(req:ProductionSelectionSet):
    if req.family not in ('minimax_h3','flux2'):raise HTTPException(400,'Unknown RefMod family')
    assert_public_name(req.production)
    production=token(canonical_production(req.production));private=personal_name_keys()
    paths={m['path']:m for m in scan(force=True) if m['family']==req.family}
    with lock,connect() as db:
        items,damaged=read_choices(db)
        if damaged:raise HTTPException(409,'Repair damaged selections before saving a set')
        chosen=[c for c in items if not c.get('personal_id') and token(canonical_production(c['production']))==production and token(canonical_name(c['person'])) not in private]
        if not chosen:raise HTTPException(400,'Select at least one public role in this production')
        if any(c['refmod'] not in paths or token(canonical_name(c['person']))!=token(canonical_name(paths[c['refmod']]['name'])) for c in chosen):raise HTTPException(409,'Resolve missing or incompatible RefMods before saving the set')
        db.execute('INSERT OR REPLACE INTO production_selection_sets VALUES (?,?,?)',(production,req.family,json.dumps(chosen)))
    return {'saved':len(chosen)}

@app.post('/api/production-selection-set/restore')
def restore_production_selection_set(req:ProductionSelectionSet):
    data=get_production_selection_set(req.production,req.family)['choices']
    paths={m['path']:m for m in scan(force=True) if m['family']==req.family}
    private=personal_name_keys();errors=[];added=0;skipped=0
    # Merge only absent public selections, with one transaction and no silent replacements.
    with lock,connect() as db:
        for c in data:
            if c.get('personal_id') or token(canonical_name(c['person'])) in private or token(canonical_production(c['production']))!=token(canonical_production(req.production)) or c['refmod'] not in paths or token(canonical_name(paths[c['refmod']]['name']))!=token(canonical_name(c['person'])):
                errors.append(c['person']+' · missing or incompatible RefMod');continue
            cur=db.execute('INSERT OR IGNORE INTO choices VALUES (?,?)',(canonical_role_key(c['person'],c['character'],canonical_production(c['production'])),json.dumps(c)))
            if cur.rowcount:added+=1
            else:skipped+=1
    return {'added':added,'skipped':skipped,'errors':errors}

class ModelFamilySwitch(BaseModel):
    family:str
    keep_convertible:bool=False

@app.post('/api/choices/reconcile')
def reconcile_choices_for_model(req:ModelFamilySwitch):
    """Atomically ensure every selected role has its explicitly chosen model-family RefMod.

    Missing or ambiguous cross-family counterparts are deselected. The selected
    RefMod is never replaced after a same-family file disappears. Public and
    Personal inventories are separate, and consent is checked again.
    """
    if req.family not in ('minimax_h3','flux2'):
        raise HTTPException(400,'Unknown RefMod model family')
    public=scan()
    paths={m['path']:m for m in public}
    by_person={}
    for model in public:
        by_person.setdefault(token(canonical_name(model['name'])),{}).setdefault(model['family'],[]).append(model)
    private={m['path']:m for m in personal_refmod_inventory()}
    people={r['id']:r for r in get_personal_rows()}
    removed=[];switched=[];keep=[];pending=[];damaged_count=0
    with lock,connect() as db:
        rows=list(db.execute('SELECT key,payload FROM choices ORDER BY key'))
        for key_string,raw in rows:
            item=decoded_choice(key_string,raw)
            if item is None:
                damaged_count+=1;continue
            personal_id=item.get('personal_id') or ''
            chosen=item.get('refmod') or ''
            if personal_id:
                person=people.get(personal_id)
                desired=(person.get('h3_refmod') if req.family=='minimax_h3' else person.get('flux_refmod')) if person else None
                if not person or not person.get('consent') or not desired or desired not in private:
                    if req.keep_convertible and req.family=='flux2' and person and person.get('consent') and chosen==person.get('h3_refmod') and private.get(chosen,{}).get('convertible_to_flux'):
                        pending.append(key_string);keep.append(item);continue
                    removed.append({'key':key_string,'person':item.get('person'),'reason':'No consent or compatible Personal RefMod'})
                    db.execute('DELETE FROM choices WHERE key=?',(key_string,))
                    continue
                resolved=desired
            else:
                current=paths.get(chosen)
                family_mods=by_person.get(token(canonical_name(item.get('person',''))),{}).get(req.family,[])
                if current and current['family']==req.family:
                    resolved=chosen
                elif current and current['family']!=req.family and len(family_mods)==1 and not current.get('role_specific') and not family_mods[0].get('role_specific'):
                    resolved=family_mods[0]['path']
                elif req.keep_convertible and req.family=='flux2' and not family_mods and current and current.get('convertible_to_flux'):
                    pending.append(key_string);keep.append(item);continue
                else:
                    reason=('More than one '+req.family+' RefMod; select the correct file first'
                            if len(family_mods)>1 and current else 'No compatible, verified '+req.family+' RefMod')
                    removed.append({'key':key_string,'person':item.get('person'),'reason':reason})
                    db.execute('DELETE FROM choices WHERE key=?',(key_string,))
                    continue
            if resolved!=chosen:
                item['refmod']=resolved
                db.execute('UPDATE choices SET payload=? WHERE key=?',(json.dumps(item),key_string))
                switched.append({'key':key_string,'person':item['person'],'refmod':resolved})
            keep.append(item)
    return {'family':req.family,'choices':keep,'removed':removed,'switched':switched,
            'remaining':len(keep),'conversion_required':pending,'damaged_count':damaged_count}


# H3 picture -> FLUX conversion is done only through WanGP's native Gradio
# queue relay. The HTTP endpoint stages and validates; it never runs a VAE.
class AutoConversionRequest(BaseModel):
    target_model: str
    choice_keys: list[str] | None = None

class AutoConversionApply(BaseModel):
    job_id: str
    preserve_choices: bool = False


def validate_auto_conversion(entry):
    """Recheck identity, chosen file and Personal consent before EACH VAE step."""
    from ..conversion_bridge import safetensors_metadata, is_h3_picture_refmod
    bridge=_casting_bridge()
    with connect() as db:
        row=db.execute('SELECT payload FROM choices WHERE key=?',(entry.key,)).fetchone()
    if not row:raise ValueError('Casting selection was removed during conversion')
    selected=require_choice(entry.key,row[0])
    if selected.get('refmod')!=entry.source or (selected.get('personal_id') or '')!=entry.personal_id:
        raise ValueError('Casting selection changed during conversion')
    if token(selected.get('person',''))!=token(entry.person):
        raise ValueError('Casting performer changed during conversion')
    personal=bool(entry.personal_id)
    if personal:
        profile=personal_row_by_id(entry.personal_id)
        if not profile or not profile['consent'] or profile['h3_refmod']!=entry.source:
            raise PermissionError('Personal consent or private H3 link is missing')
    else:
        if token(entry.person) in personal_name_keys() or token(canonical_name(entry.person)) in personal_name_keys():
            raise PermissionError('Use the Personal tab for this profile')
        model=next((m for m in scan() if m['path']==entry.source and
                    token(canonical_name(m['name']))==token(canonical_name(entry.person))
                    and m['family']=='minimax_h3'),None)
        if not model:raise ValueError('Public H3 file no longer matches the performer')
    path=bridge.adapter.validate_refmod(relative_path=entry.source,
                 family='minimax_h3',personal=personal)
    from ..queue_bridge import refmod_identifier
    source_name=refmod_identifier(path,bridge.adapter.refmod_root,'minimax_h3')
    destination=(bridge.adapter.refmod_root/'flux2'/source_name).resolve()
    destination_root=effective_local_paths()['personal_flux' if personal else 'public_flux'].resolve()
    if not destination.is_relative_to(destination_root):
        raise ValueError('Converted FLUX file would be outside the configured scan folder')
    metadata=safetensors_metadata(path,'refmod_meta')
    if not is_h3_picture_refmod(metadata):
        raise ValueError('Only still-image H3 RefMods, including picture stacks, can be converted to FLUX')
    return path

@app.post('/api/choices/conversion/prepare',include_in_schema=False)
def prepare_auto_conversion(req:AutoConversionRequest):
    """Prepare conversion for selected roles lacking the requested FLUX format.

    No selected role is removed until the conversion finishes and its actual
    output has been verified. Unconvertible choices reconcile normally after.
    """
    bridge=_casting_bridge()  # missing native bridge must fail cleanly with HTTP 503
    from ..conversion_bridge import ConversionItem, ConversionTask
    if not (req.target_model.startswith('flux') or req.target_model=='pi_flux2'):
        return {'id':None,'count':0,'reason':'No conversion required for H3 models'}
    public=scan()
    existing={}
    for m in public:
        existing.setdefault(token(canonical_name(m['name'])),{}).setdefault(m['family'],[]).append(m)
    people={p['id']:p for p in get_personal_rows()}
    with connect() as db:
        choices_to_convert,damaged=read_choices(db)
    if damaged and (req.choice_keys is None or any(k in req.choice_keys for k in damaged)):
        raise HTTPException(409,'Saved casting selections are damaged; repair or remove them before converting.')
    items=[];not_convertible=[]
    for entry in choices_to_convert:
        if req.choice_keys is not None and entry['key'] not in req.choice_keys:continue
        saved=entry.get('refmod','');pid=entry.get('personal_id','')
        if pid:
            person=people.get(pid)
            if not person or not person['consent']:
                not_convertible.append({'person':entry.get('person'),'reason':'No Personal consent'});continue
            if person['flux_refmod'] and any(p['path']==person['flux_refmod'] for p in personal_refmod_inventory()):continue
            if saved != person['h3_refmod'] or not saved.startswith('personal/'):
                continue
        else:
            mods=existing.get(token(canonical_name(entry.get('person',''))),{})
            if mods.get('flux2'):continue
            if not any(m['path']==saved for m in mods.get('minimax_h3',[])):continue
        item=ConversionItem(key=entry['key'],source=saved,
                  person=entry.get('person',''),personal_id=pid)
        try:
            validate_auto_conversion(item)
            items.append(item)
        except (ValueError,PermissionError,OSError) as exc:
            not_convertible.append({'person':entry.get('person'),'reason':str(exc)[:160]})
    if not items:
        return {'id':None,'count':0,'not_convertible':not_convertible,
                'reason':'No convertible H3 picture RefMods found; original casting selections preserved'}
    target=[x for x in bridge.models(req.target_model) if x['ready']]
    source=[x for x in bridge.models('h3_video') if x['ready']]
    if not target or not source:
        # No usable VAE pair; the browser can still perform its normal model
        # compatibility reconciliation (removing incompatible active choices).
        return {'id':None,'count':0,'not_convertible':not_convertible +
                [{'person':'Conversion','reason':'Compatible H3/FLUX encoders are not installed'}]}
    task=ConversionTask(target_model=req.target_model,
             h3_model_type=source[0]['model_type'],flux_model_type=target[0]['model_type'],items=tuple(items))
    try:
        job_id=bridge.enqueue_conversion(task,validate_auto_conversion)
    except (ValueError,RuntimeError) as exc:raise HTTPException(400,str(exc))
    return {'id':job_id,'count':len(items),'not_convertible':not_convertible}

# Explicit library-wide conversion: no temporary casting choices, no automatic
# profile linking, no downloads requested by this planner, no background startup.
class LibraryConversionRequest(BaseModel):
    include_personal:bool=False
    plan_token:str=Field(default='',max_length=64)
    model_config={'extra':'forbid'}


def library_conversion_key(path):
    # Preserve role-specific suffixes; normalize only the format suffix.
    stem=Path(path).stem.casefold()
    return re.sub(r'(?:_h3(?:_v\d+)?|_flux(?:2|3)?|_klein(?:4b|9b)?)$', '', stem)


def library_source_check(entry, bridge):
    from ..conversion_bridge import safetensors_metadata,is_h3_picture_refmod
    from ..queue_bridge import refmod_identifier
    private=bool(entry.personal_id)
    if private:
        profile=personal_row_by_id(entry.personal_id)
        if not profile or not profile['consent'] or profile['h3_refmod']!=entry.source:
            raise PermissionError('Personal consent or linked source changed')
        if profile['flux_refmod']:
            try:bridge.adapter.validate_refmod(relative_path=profile['flux_refmod'],family='flux2',personal=True)
            except ValueError:pass
            else:raise ValueError('Personal FLUX link already exists')
    elif token(entry.person) in personal_name_keys() or token(canonical_name(entry.person)) in personal_name_keys():
        raise PermissionError('Private identity excluded from public conversion')
    path=bridge.adapter.validate_refmod(relative_path=entry.source,family='minimax_h3',personal=private)
    name=refmod_identifier(path,bridge.adapter.refmod_root,'minimax_h3')
    root=bridge.adapter.refmod_root/'flux2'
    dest=root/(name+'.safetensors')
    approved=effective_local_paths()['personal_flux' if private else 'public_flux'].resolve()
    if not dest.resolve().is_relative_to(approved):raise ValueError('Destination is outside the approved library')
    if dest.exists() or dest.is_symlink():raise ValueError('Destination already exists')
    for folder in {dest.parent, root} if not private else {dest.parent}:
        if folder.is_dir() and any(p.is_file() and library_conversion_key(p.name)==library_conversion_key(entry.source) for p in folder.glob('*.safetensors')):
            raise ValueError('Existing FLUX counterpart')
    if not is_h3_picture_refmod(safetensors_metadata(path,'refmod_meta')):
        raise ValueError('Not a convertible H3 still-picture RefMod')
    return path


def library_conversion_plan(include_personal):
    from ..conversion_bridge import ConversionItem,ConversionTask
    bridge=_casting_bridge()
    public=scan(force=True)
    private=personal_refmod_inventory() if include_personal else []
    existing={library_conversion_key(m['path']) for m in public if m['family']=='flux2'}
    private_existing={library_conversion_key(m['path']) for m in private if m['family']=='flux2'}
    profiles={p['h3_refmod']:p for p in get_personal_rows() if p['consent'] and p['h3_refmod']} if include_personal else {}
    items=[];skipped=[];fingerprints={}
    for m in public+private:
        if m['family']!='minimax_h3':continue
        path=m['path'];personal=path.startswith('personal/');profile=profiles.get(path) if personal else None
        if personal and not profile:
            skipped.append({'source':path,'reason':'No linked Personal profile with consent'});continue
        if library_conversion_key(path) in (private_existing if personal else existing):
            skipped.append({'source':path,'reason':'Existing FLUX counterpart'});continue
        item=ConversionItem('library:'+path,path,profile['name'] if profile else m['name'],profile['id'] if profile else '')
        try:
            f=library_source_check(item,bridge);st=f.stat()
            fingerprints[path]=(st.st_size,st.st_mtime_ns,st.st_ino)
            items.append(item)
        except (OSError,ValueError,PermissionError,TypeError,AttributeError) as exc:
            skipped.append({'source':path,'reason':str(exc)[:200]})
    def ready_models(board):
        try:return [m for m in bridge.models(board) if m.get('ready')]
        except (RuntimeError,ValueError,AttributeError):return []
    h3=next(iter(ready_models('h3_video')),None)
    # Prefer smaller compatible FLUX model definitions to avoid unnecessary
    # full Dev model loading. Native readiness does not prove weights cached.
    target=next(((board,m) for board in ('flux2_klein4','flux2_klein9','flux3_klein','pi_flux2','flux2_dev') for m in ready_models(board)),None)
    reason=''
    if not bridge.live_session_ready or bridge.dispatch_mode!='gradio':reason='Native WanGP queue relay unavailable'
    elif (bridge.adapter.discover().get('fork_revision') or 0)<58:reason='Refmod-Fork fork.58 or newer required'
    elif not h3 or not target:reason='Compatible H3 and FLUX model definitions required'
    task=ConversionTask(target[0],h3['model_type'],target[1]['model_type'],tuple(items),library=True) if h3 and target else None
    # Existing native relay limits a single job to 500. Subsequent scans pick up
    # the remainder; never silently run an unreviewed extra batch.
    preview={'count':len(items),'batch_count':min(500,len(items)),'skipped':skipped,'items':[{'source':i.source,'person':i.person} for i in items],
             'ready':not reason,'reason':reason,'h3_model':h3['model_type'] if h3 else None,'flux_model':target[1]['model_type'] if target else None}
    signature=hashlib.sha256(json.dumps([include_personal,preview,fingerprints],sort_keys=True).encode()).hexdigest()
    preview['plan_token']=signature
    return preview,task,fingerprints


@app.get('/api/settings/conversion/plan',include_in_schema=False)
def preview_library_conversion(include_personal:bool=False):
    return library_conversion_plan(include_personal)[0]


@app.get('/api/settings/conversion/status',include_in_schema=False)
def library_conversion_status():
    return {'job':_casting_bridge().library_conversion_status()}


@app.post('/api/settings/conversion/start',include_in_schema=False)
def start_library_conversion(req:LibraryConversionRequest):
    bridge=_casting_bridge()
    preview,task,fingerprints=library_conversion_plan(req.include_personal)
    if not req.plan_token or req.plan_token!=preview['plan_token']:
        raise HTTPException(409,'Library or encoder availability changed; preview again.')
    if not preview['ready'] or not task or not task.items:
        raise HTTPException(409,preview['reason'] or 'No missing supported formats')
    from dataclasses import replace
    task=replace(task,items=task.items[:500])
    def validate(item):
        path=library_source_check(item,bridge);st=path.stat()
        if fingerprints.get(item.source)!=(st.st_size,st.st_mtime_ns,st.st_ino):raise ValueError('Source changed since preview')
        return path
    try:job_id=bridge.enqueue_conversion(task,validate)
    except (OSError,ValueError,RuntimeError) as exc:raise HTTPException(409,str(exc))
    return {'id':job_id,'count':len(task.items)}


@app.post('/api/choices/conversion/apply',include_in_schema=False)
def apply_auto_conversion(req:AutoConversionApply):
    """Attach only verified native conversion outputs to their original roles."""
    bridge=_casting_bridge()
    from ..conversion_bridge import safetensors_metadata, is_h3_picture_refmod
    from ..queue_bridge import refmod_identifier
    job=bridge.status(req.job_id)
    if not job or job.get('operation')!='auto_convert':raise HTTPException(404,'Conversion job not found')
    if job.get('state') not in ('completed','partial','failed'):
        raise HTTPException(409,'Conversion is still running')
    if job.get('applied'):raise HTTPException(409,'Conversion results were already applied')
    # A partially successful conversion must not delete unrelated casting choices.
    # Converted files stay safely on disk and can be reused in a later attempt.
    if job.get('failures') or len(job.get('converted',[])) != job.get('total_tasks', len(job.get('converted',[]))):
        raise HTTPException(409,'Some RefMods failed conversion; no casting selections have been changed. Review the conversion job status.')
    assigned=[];skipped=[]
    with lock:
        if (bridge.status(req.job_id) or {}).get('applied'):
            raise HTTPException(409,'Conversion results were already applied')
        with connect() as db:
            for result in job.get('converted',[]):
                row=db.execute('SELECT payload FROM choices WHERE key=?',(result['key'],)).fetchone()
                if not row:continue
                original=decoded_choice(result['key'],row[0])
                if original is None:
                    skipped.append({'person':result['person'],'reason':'Casting entry is damaged'});continue
                if original.get('refmod')!=result['source'] or (original.get('personal_id') or '')!=result['personal_id']:
                    skipped.append({'person':result['person'],'reason':'Casting entry changed during conversion'});continue
                personal=bool(result['personal_id'])
                if not personal and (token(original['person']) in personal_name_keys() or token(canonical_name(original['person'])) in personal_name_keys()):
                    skipped.append({'person':result['person'],'reason':'Use the Personal tab for this profile'});continue
                if personal:
                    person=personal_row_by_id(result['personal_id'])
                    if not person or not person['consent']:
                        skipped.append({'person':result['person'],'reason':'Consent revoked'});continue
                try:
                    dest=bridge.adapter.validate_refmod(relative_path=result['refmod'],family='flux2',personal=personal)
                    source=bridge.adapter.validate_refmod(relative_path=result['source'],family='minimax_h3',personal=personal)
                    expected=refmod_identifier(source,bridge.adapter.refmod_root,'minimax_h3')
                    meta=safetensors_metadata(dest,'klein9_refmod_meta')
                    if meta.get('converted_from')!=expected:
                        raise ValueError('Converted output does not match the selected H3 source')
                except (OSError,ValueError) as exc:
                    skipped.append({'person':result['person'],'reason':str(exc)[:160]});continue
                original['refmod']=result['refmod']
                db.execute('UPDATE choices SET payload=? WHERE key=?',(json.dumps(original),result['key']))
                if personal:
                    db.execute('UPDATE personal_profiles SET flux_refmod=?,updated_at=? WHERE id=?',
                              (result['refmod'],int(time.time()),result['personal_id']))
                assigned.append(result)
        bridge._change(req.job_id,applied=True)
    # Scan the newly generated model files before any compatibility pruning.
    scan(force=True)
    reconciled={'choices':get_choices(),'removed':[],'switched':[]} if req.preserve_choices else reconcile_choices_for_model(ModelFamilySwitch(family='flux2'))
    return {**reconciled,'converted':assigned,'skipped_converted':skipped,'conversion_failures':job.get('failures',[])}

@app.delete('/api/choices/{key}')
def delete_choice(key:str):
    with lock,connect() as db: db.execute('DELETE FROM choices WHERE key=?',(key,))
    return {'deleted':True}

@app.delete('/api/choices')
def delete_all_choices():
    with lock, connect() as db:
        count=db.execute('SELECT COUNT(*) FROM choices').fetchone()[0]
        db.execute('DELETE FROM choices')
        db.execute('DELETE FROM prompt_overrides')
    return {'removed':count}

def photo_mapping(db,table):
    # Preserve old keys and expose their current canonical equivalents. Exact
    # canonical entries win over older aliases; no migration deletes user data.
    rows=list(db.execute('SELECT key,url FROM '+table))
    result={k:local_photo_url(u,db) for k,u in rows if u}
    for k,u in rows:
        if u:result.setdefault(canonical_photo_key(k),local_photo_url(u,db))
    return result

@app.get('/api/images/saved')
def saved_images():
    with connect() as db:return photo_mapping(db,'images')

class Photo(BaseModel):
    key:str=Field(min_length=4,max_length=500)
    url:str=Field(min_length=1,max_length=8192)

@app.put('/api/images/saved')
def save_image(item:Photo):
    if not item.url.startswith('https://'):raise HTTPException(400,'Image must be an HTTPS URL')
    key=canonical_photo_key(item.key)
    # A successful manual save means readable bytes exist locally. Never replace
    # a previous selection with an unverified hotlink or a failed download.
    try:local=download_image(item.url)
    except Exception:local=''
    if not local or not re.fullmatch(r'api/photos/[0-9a-f]{64}\.jpg',local) or not safe_media_file(PHOTO_DIR,Path(local).name):
        raise HTTPException(422,'Could not archive the image locally. The host may block downloads; upload a local copy instead.')
    with lock,connect() as db:
        db.execute('INSERT OR REPLACE INTO images(key,url) VALUES (?,?)',(key,local))
    return {'saved':True,'key':key,'url':local}

@app.get('/api/images/search')
def image_search(actress:str=Query('',max_length=120),character:str=Query('',max_length=120),production:str=Query('',max_length=140),kind:str='role',page:int=Query(1,ge=1,le=15),refmod_only:bool=False):
    if actress:assert_public_name(actress)
    # Real provider pagination. Each scroll requests a new page rather than revealing an already-limited result list.
    parts=[actress,character,production] if kind=='role' else ([actress] if kind=='actress' else [production])
    query=' '.join(part for part in parts if part).strip()
    if not query:return {'query':'','images':[],'warning':'Missing search terms','has_more':False,'page':page}
    images=[];warning=None
    try:
        from ddgs import DDGS
        params={'max_results':24,'page':page}
        if refmod_only:params.update(size='Medium',type_image='photo')
        with DDGS(timeout=18) as ddg:
            for item in ddg.images(query,**params):
                url=item.get('image') or item.get('thumbnail')
                if not url or not url.startswith('https://'):continue
                try:
                    width=int(item.get('width') or 0);height=int(item.get('height') or 0)
                except (TypeError,ValueError):width=height=0
                title=item.get('title','') or ''
                # Only use metadata as an early search filter. Actual downloaded pixels get a stricter check on collection.
                bad_meta=width>0 and height>0 and (min(width,height)<600 or max(width,height)/max(1,min(width,height))>2.5)
                bad_title=any(x in title.casefold() for x in ('collage','fan art','fanart','wallpaper','meme ','meme:','before and after','cartoon','illustration','ai generated','ai-generated','watermarked'))
                images.append({'url':url,'thumbnail':item.get('thumbnail') or url,'title':title,'source':item.get('url',''),
                               'width':width,'height':height,'quality_hint':'low' if (bad_meta or bad_title) else ('unknown' if not width or not height else 'candidate')})
    except Exception as exc:
        warning=f'Image search provider unavailable: {type(exc).__name__}. You can still open external image results or paste an HTTPS image URL.'
    return {'query':query,'images':images,'warning':warning,'page':page,'has_more':len(images)>=20 and page<15,
            'web_search':'https://www.google.com/search?tbm=isch&q='+quote(query)}


def search_candidates(actress, character='', production='', kind='role', max_results=10):
    if actress:assert_public_name(actress)
    from ddgs import DDGS
    parts=[actress,character,production] if kind=='role' else [actress]
    query=' '.join(x for x in parts if x).strip()
    if not query:return []
    results=[]
    with DDGS(timeout=12) as ddg:
        for item in ddg.images(query,max_results=max_results):
            url=item.get('image') or item.get('thumbnail')
            if url and url.startswith('https://'):
                results.append({'url':url,'thumbnail':item.get('thumbnail') or url,
                    'title':item.get('title',''),'source':item.get('url','')})
    return results

def auto_select(results, actress, character, production, kind):
    # Ranking is deliberately conservative; a result must mention the identity
    # and, for role images, ideally the production or character.
    wanted=token(actress)
    words=[w for w in re.split(r'\W+',actress.casefold()) if len(w)>2]
    character_words=[w for w in re.split(r'\W+',character.casefold()) if len(w)>2]
    prod_words=[w for w in re.split(r'\W+',production.casefold()) if len(w)>2]
    ranked=[]
    for idx,r in enumerate(results):
        text=(r.get('title','')+' '+r.get('source','')).casefold()
        score=3*sum(w in text for w in words)+2*sum(w in text for w in character_words)+2*sum(w in text for w in prod_words)
        if kind=='role' and not any(w in text for w in character_words+prod_words):continue
        if not any(w in text for w in words):continue
        if any(x in text for x in ('collage','before and after','then and now','wedding','duchess of')):score-=4
        ranked.append((score,-idx,r))
    if not ranked:return ''
    score,_,result=max(ranked,key=lambda z:(z[0],z[1]))
    return result['url'] if score>= (5 if kind=='actress' else 7) else ''

@app.get('/api/images/auto')
def auto_image(key:str=Query(...,max_length=500),actress:str=Query(...,max_length=120),
               character:str=Query('',max_length=120),production:str=Query('',max_length=140),kind:str='role'):
    assert_public_name(actress)
    if kind not in ('role','actress'):raise HTTPException(400,'Unsupported image type')
    key=canonical_photo_key(key)
    with connect() as db:
        manual=db.execute('SELECT url FROM images WHERE key=?',(key,)).fetchone()
        if manual:return {'url':local_photo_url(manual[0],db),'source':'manual'}
        cached=db.execute('SELECT url,checked FROM auto_images WHERE key=?',(key,)).fetchone()
        if cached and time.time()-cached[1]<7*86400:
            return {'url':local_photo_url(cached[0],db),'source':'automatic-cache'}
    url=''
    try:
        results=search_candidates(actress,character,production,kind)
        url=auto_select(results,actress,character,production,kind)
    except Exception:
        # A transient provider failure should be retried; do not cache failure.
        return {'url':'','source':'search-unavailable'}
    with lock,connect() as db:
        db.execute('INSERT OR REPLACE INTO auto_images(key,url,checked) VALUES(?,?,?)',(key,url,int(time.time())))
        manual=db.execute('SELECT url FROM images WHERE key=?',(key,)).fetchone()
    if url: threading.Thread(target=download_image,args=(url,),daemon=True).start()
    return {'url':local_photo_url(manual[0] if manual else url),'source':'manual' if manual else 'automatic'}


# Prefetch uses the same cautious automatic selector as browsing. It stores only
# suggestions, never changes the user's manually chosen images or casting picks.
# The queue prioritizes locally installed cast and their roles, then optional
# historical catalog entries. The user can stop/resume between requests.
def prefetch_items(scope='installed'):
    installed={token(canonical_name(m['name'])) for m in scan()}
    norm_people,norm_roles=normalized_catalog()
    people={token(canonical_name(p['name'])):canonical_name(p['name']) for p in norm_people}
    for m in scan(): people.setdefault(token(m['name']),m['name'])
    jobs=[]; seen=set()
    for name in people.values():
        if scope=='installed' and token(name) not in installed: continue
        key='actress|'+token(name)
        if key not in seen:
            jobs.append({'key':key,'actress':name,'character':'','production':'','kind':'actress'})
            seen.add(key)
    for r in norm_roles:
        name=r['actress']
        if scope=='installed' and token(name) not in installed: continue
        key='role|'+canonical_role_key(name,r['character'],r['production'])
        if key not in seen:
            jobs.append({'key':key,'actress':name,'character':r['character'],
                         'production':r['production'],'kind':'role'})
            seen.add(key)
    return jobs

def prefetch_run(scope):
    global prefetch_thread
    try:
        jobs=prefetch_items(scope)
        # Reuse valid cached entries and skip any manually selected images.
        with connect() as db:
            now=int(time.time())
            known=set(row[0] for row in db.execute('SELECT key FROM images'))
            known.update(row[0] for row in db.execute('SELECT key FROM auto_images WHERE checked>?',(now-7*86400,)))
        todo=[j for j in jobs if j['key'] not in known]
        with prefetch_lock:
            prefetch_state.update(total=len(todo),done=0,found=0,failed=0,last='',started=int(time.time()),running=True,paused=False)
        for j in todo:
            if prefetch_stop.is_set(): break
            if token(j['actress']) in personal_name_keys():
                with prefetch_lock:prefetch_state['done']+=1
                continue
            # Intentionally paced requests to reduce image-provider throttling.
            try:
                results=search_candidates(j['actress'],j['character'],j['production'],j['kind'],max_results=10)
                url=auto_select(results,j['actress'],j['character'],j['production'],j['kind'])
                if url: download_image(url)
                with lock,connect() as db:
                    db.execute('INSERT OR REPLACE INTO auto_images(key,url,checked) VALUES(?,?,?)',
                               (j['key'],url,int(time.time())))
                with prefetch_lock:
                    prefetch_state['found']+=int(bool(url))
                    prefetch_state['last']=j['actress']+(' — '+j['character'] if j['character'] else '')
            except Exception as exc:
                with prefetch_lock:
                    prefetch_state['failed']+=1
                    prefetch_state['last']='Provider error: '+type(exc).__name__
            finally:
                with prefetch_lock:prefetch_state['done']+=1
            # No sleeping under a global lock; stop remains responsive.
            if prefetch_stop.wait(3):break
    finally:
        with prefetch_lock:prefetch_state.update(running=False,paused=False)

@app.get('/api/prefetch/status')
def prefetch_status():
    with prefetch_lock: return dict(prefetch_state)

class PrefetchRequest(BaseModel):
    scope:str='installed'

@app.post('/api/prefetch/start')
def prefetch_start(config:PrefetchRequest):
    global prefetch_thread
    if config.scope not in ('installed','all'):raise HTTPException(400,'Scope must be installed or all')
    with prefetch_lock:
        if prefetch_state['running']:return {'started':False,'reason':'already running'}
        prefetch_state['running']=True
        prefetch_state['last']='Preparing queue...'
        prefetch_stop.clear()
        try:
            prefetch_thread=threading.Thread(target=prefetch_run,args=(config.scope,),daemon=True)
            prefetch_thread.start()
        except Exception as exc:
            prefetch_thread=None;prefetch_state.update(running=False,paused=False,last='Could not start worker')
            raise HTTPException(503,'Could not start prefetch worker; retry.') from exc
    return {'started':True}

@app.post('/api/prefetch/stop')
def prefetch_cancel():
    prefetch_stop.set()
    return {'stopping':True}

@app.get('/api/images/cached')
def cached_images():
    # One request retrieves the entire local cache, avoiding per-card API waits.
    with connect() as db:
        suggestions=photo_mapping(db,'auto_images')
        suggestions.update(photo_mapping(db,'images'))
    return suggestions

# v4 local image archive: downloaded once, then served through our own URL.
# Only public HTTPS destinations are allowed to prevent access to internal services.
def validate_public_url(url):
    from urllib.parse import urlsplit
    u=urlsplit(url)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.port not in (None,443):
        raise ValueError('A public HTTPS image URL is required')
    if u.hostname.lower() in ('localhost','localhost.localdomain') or u.hostname.lower().endswith(('.local','.internal','.localhost')):
        raise ValueError('Private hosts are not permitted')
    results=socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM)
    if not results or any(not ipaddress.ip_address(r[4][0]).is_global for r in results):
        raise ValueError('Private IP addresses are not permitted')
    return u

def local_photo_url(url, db=None):
    if not url:return ''
    if url.startswith(('api/photos/','/api/photos/')):return url.lstrip('/')
    if db is None:
        with connect() as conn:
            row=conn.execute('SELECT filename FROM photo_files WHERE url=?',(url,)).fetchone()
    else:
        row=db.execute('SELECT filename FROM photo_files WHERE url=?',(url,)).fetchone()
    if row and safe_media_file(PHOTO_DIR,row[0],r'[0-9a-f]{64}\.jpg'):return 'api/photos/'+row[0]
    return url

def download_image(url):
    if not url or url.startswith(('api/photos/','/api/photos/')):return ''
    try:
        with connect() as db:
            cached=db.execute('SELECT filename FROM photo_files WHERE url=?',(url,)).fetchone()
        if cached and safe_media_file(PHOTO_DIR,cached[0],r'[0-9a-f]{64}\.jpg'):return 'api/photos/'+cached[0]
        validate_public_url(url)
        # Disable proxies and redirects; redirects must not reach private network addresses.
        with httpx.Client(timeout=12,follow_redirects=False,trust_env=False,headers={'User-Agent':'Mozilla/5.0 (compatible; CastingStudio/1.0.0-rc.12.20)'}) as client:
            with client.stream('GET',url) as res:
                if res.status_code!=200 or not res.headers.get('content-type','').lower().startswith('image/'):
                    return ''
                if int(res.headers.get('content-length') or 0)>8*1024*1024:return ''
                buf=io.BytesIO()
                for chunk in res.iter_bytes():
                    if buf.tell()+len(chunk)>8*1024*1024:return ''
                    buf.write(chunk)
        buf.seek(0)
        with Image.open(buf) as img:
            img.verify()
        buf.seek(0)
        with Image.open(buf) as img:
            if img.width<80 or img.height<80 or img.width*img.height>35_000_000:return ''
            img=ImageOps.exif_transpose(img).convert('RGB')
            img.thumbnail((1400,1400))
        with lock:
            # Another download may have finished while the network was in flight.
            with connect() as db:
                cached=db.execute('SELECT filename FROM photo_files WHERE url=?',(url,)).fetchone()
            if cached and safe_media_file(PHOTO_DIR,cached[0],r'[0-9a-f]{64}\.jpg'):return 'api/photos/'+cached[0]
            filename=hashlib.sha256(url.encode()).hexdigest()+'.jpg'
            # Never overwrite an unrelated/uncommitted file with the same name.
            while (PHOTO_DIR/filename).exists() or (PHOTO_DIR/filename).is_symlink():
                filename=hashlib.sha256(uuid.uuid4().bytes).hexdigest()+'.jpg'
            tmp=PHOTO_DIR/(filename+'.'+uuid.uuid4().hex+'.tmp')
            created=False;published=False
            try:
                with tmp.open('xb') as stream:
                    created=True
                    img.save(stream,format='JPEG',quality=88,optimize=True)
                tmp.replace(PHOTO_DIR/filename);published=True
                with connect() as db:
                    db.execute('INSERT OR REPLACE INTO photo_files(url,filename) VALUES(?,?)',(url,filename))
            except (OSError,sqlite3.Error):
                if published:
                    try:(PHOTO_DIR/filename).unlink(missing_ok=True)
                    except OSError:pass
                return ''
            finally:
                if created:
                    try:tmp.unlink(missing_ok=True)
                    except OSError:pass
        return 'api/photos/'+filename
    except (ValueError, OSError, httpx.HTTPError, UnidentifiedImageError, socket.gaierror, Image.DecompressionBombError, sqlite3.Error):
        return ''

@app.get('/api/photos/status')
def photo_status():
    with connect() as db:
        files=db.execute('SELECT COUNT(*) FROM photo_files').fetchone()[0]
        available=db.execute('SELECT COUNT(*) FROM auto_images WHERE url!=""').fetchone()[0]
    return {'local_files':files,'automatic_suggestions':available}

@app.get('/api/photos/{filename}')
def serve_photo(filename:str):
    if not re.fullmatch(r'[0-9a-f]{64}\.jpg',filename):raise HTTPException(404,'Not found')
    path=safe_media_file(PHOTO_DIR,filename)
    if not path:raise HTTPException(404,'Not found')
    return FileResponse(path,media_type='image/jpeg',headers={'Cache-Control':'public, max-age=31536000, immutable'})

@app.post('/api/photos/archive-existing')
def archive_existing():
    # one-at-a-time background worker archives already selected and prefetched URLs.
    global archive_thread
    if archive_thread and archive_thread.is_alive():return {'started':False,'reason':'already running'}
    try:
        archive_thread=threading.Thread(target=archive_existing_worker,daemon=True)
        archive_thread.start()
    except Exception as exc:
        archive_thread=None
        raise HTTPException(503,'Could not start archive worker; retry.') from exc
    return {'started':True}

archive_thread=None

def archive_existing_worker():
    with connect() as db:
        urls={r[0] for r in db.execute('SELECT url FROM images')}
        urls.update(r[0] for r in db.execute('SELECT url FROM auto_images WHERE url!=""'))
    for url in urls:
        download_image(url)
        if prefetch_stop.is_set():break

# Editable template is separate from casting metadata and from per-selection overrides.
SAMPLE_TEMPLATE={
 'name':'Cinematic character showcase',
 'wardrobe':'Clothing faithful to the selected subject’s established visual appearance and appropriate to the scene. For a named production, match its wardrobe design and period. Maintain consistent clothing throughout this presentation.',
 'setting':'A cinematic setting appropriate to the selected production and year, with authentic environmental design, natural lighting and subtle background ambience. For a subject appearing as themselves, use a tasteful, neutral portrait environment.',
 'video1_action':'0–5s: <Subject 1> faces the camera in a medium shot with relaxed confidence. 5–10s: The subject slowly turns to show a three-quarter profile while the camera gently arcs. 10–15s: The subject returns their gaze to the camera and settles into a natural pose.',
 'video2_action':'0–5s: <Subject 1> begins walking at a comfortable pace through the location. 5–10s: The camera tracks alongside the subject, revealing the surroundings in a medium-wide composition. 10–15s: The subject pauses naturally and looks toward a point of interest.',
 'video3_action':'0–5s: <Subject 1> settles into a medium close-up. 5–10s: The subject performs a small, natural expressive gesture appropriate to the scene. 10–15s: Their expression develops into a calm, confident look as the camera holds steady.',
 'video4_action':'0–5s: <Subject 1> stands in a balanced composition. 5–10s: The camera moves gently closer as the subject looks toward the viewer. 10–15s: Hold a composed closing portrait with a natural expression and steady eye contact.',
 'video1_sound':'Subtle location ambience, natural breathing and gentle movement.',
 'video2_sound':'Continuous location ambience and natural footsteps synchronized with the movement.',
 'video3_sound':'Quiet location ambience, natural breathing and subtle movement.',
 'video4_sound':'Soft location ambience and a natural settling of movement.',
 'include_non_diegetic_music':False,
 'include_caption':False,
 'music_description':'The theme music of {production} plays at low volume underneath the scene audio; environmental sounds, footsteps, reactions, and effects stay clearly audible.',
 'video_count':2,
}
PERSONAL_VIDEO_ACTIONS={
    1:'0–5s: <Subject 1> faces the camera in a relaxed pose. 5–10s: The subject slowly turns to a three-quarter profile. 10–15s: Return to face the camera with a natural expression.',
    2:'0–5s: <Subject 1> stands comfortably in the studio. 5–10s: Shift weight and take a small natural step within the frame. 10–15s: Settle into a relaxed pose.',
    3:'0–5s: <Subject 1> looks toward the camera. 5–10s: Make a small, natural expressive gesture. 10–15s: Settle into a friendly expression.',
    4:'0–5s: <Subject 1> faces the camera. 5–10s: Relax the shoulders and smile gently. 10–15s: Hold the composed studio pose.',
}
TEMPLATE_FIELDS=('name','wardrobe','setting','video_count','include_non_diegetic_music','include_caption','music_description',*(f'video{v}_{field}' for v in range(1,5) for field in ('action','sound')))

class TemplatePayload(BaseModel):
    name:str=Field(default='Custom template',max_length=140)
    wardrobe:str=Field(default='',max_length=8000)
    setting:str=Field(default='',max_length=4000)
    video_count:int=Field(default=2,ge=1,le=4)
    include_non_diegetic_music:bool=False
    include_caption:bool=False
    music_description:str=Field(default=SAMPLE_TEMPLATE['music_description'],max_length=3000)
    video1_action:str=Field(default='',max_length=10000)
    video2_action:str=Field(default='',max_length=10000)
    video3_action:str=Field(default='',max_length=10000)
    video4_action:str=Field(default='',max_length=10000)
    video1_sound:str=Field(default='',max_length=4000)
    video2_sound:str=Field(default='',max_length=4000)
    video3_sound:str=Field(default='',max_length=4000)
    video4_sound:str=Field(default='',max_length=4000)

def stored_video_template(row, *, override=False):
    if not row:return {} if override else dict(SAMPLE_TEMPLATE)
    try:
        raw=json.loads(row[0])
        if not isinstance(raw,dict):raise ValueError('Expected a template object')
        # Old partial settings inherit factory values, while explicit empty fields remain empty.
        if override:return TemplatePayload.model_validate(raw).model_dump(exclude_unset=True)
        return TemplatePayload.model_validate({**SAMPLE_TEMPLATE,**raw}).model_dump()
    except (ValueError,TypeError):
        kind='per-selection override' if override else 'video template'
        raise HTTPException(409,f'Saved {kind} is damaged. Open the prompt editor and reset or save a corrected template before generating.')

@app.get('/api/prompts/template')
def prompt_template(response:Response):
    with connect() as db:
        row=db.execute("SELECT payload FROM prompt_settings WHERE id='default'").fetchone()
    try:return stored_video_template(row)
    except HTTPException:
        response.headers['X-Casting-Template-Warning']='Saved video template is damaged. Reset or save a corrected template before generating.'
        return dict(SAMPLE_TEMPLATE)

@app.put('/api/prompts/template')
def save_prompt_template(t:TemplatePayload):
    with lock,connect() as db:
        db.execute("INSERT OR REPLACE INTO prompt_settings(id,payload) VALUES('default',?)",(t.model_dump_json(),))
    return {'saved':True}

@app.post('/api/prompts/template/reset')
def reset_prompt_template():
    with lock,connect() as db:db.execute("DELETE FROM prompt_settings WHERE id='default'")
    return SAMPLE_TEMPLATE

class OverridePayload(TemplatePayload):
    key:str=Field(max_length=500)

@app.get('/api/prompts/overrides')
def prompt_overrides(response:Response):
    result={};damaged=False
    with connect() as db:
        for k,v in db.execute('SELECT key,payload FROM prompt_overrides'):
            try:result[k]=stored_video_template((v,),override=True)
            except HTTPException:damaged=True
    if damaged:response.headers['X-Casting-Template-Warning']='One or more saved overrides are damaged. Reset or save the affected override before generating.'
    return result

@app.put('/api/prompts/overrides')
def update_override(item:OverridePayload):
    with lock,connect() as db:db.execute('INSERT OR REPLACE INTO prompt_overrides(key,payload) VALUES (?,?)',(item.key,item.model_dump_json()))
    return {'saved':True}

@app.delete('/api/prompts/overrides/{key}')
def delete_override(key:str):
    with lock,connect() as db:db.execute('DELETE FROM prompt_overrides WHERE key=?',(key,))
    return {'deleted':True}

def clean_line(s):return str(s or '').replace('\r','').strip()
def flatten(s):return '\n'.join(x.strip() for x in str(s).splitlines() if x.strip())
def portrayal_production_label(item):
    """Attach a recorded production year when available, never guess one.

    Saved casting choices predating this change do not have a year field;
    the production catalog already stores its year independently.
    """
    production=clean_line(item.get('production',''))
    if not production:return ''
    if re.search(r'\((?:19|20)\d{2}\)\s*$',production):return production
    explicit=re.search(r'\b((?:19|20)\d{2})\s*$',production)
    if explicit:return production[:explicit.start()].rstrip(' ,(-')+f' ({explicit.group(1)})'
    year=item.get('year')
    if not year:
        with connect() as db:
            row=db.execute('SELECT year FROM productions WHERE key=?',
                           (token(canonical_production(production)),)).fetchone()
        year=row[0] if row else None
        if not year:
            years={str(p.get('year')) for p in DB.get('productions',[]) if token(canonical_production(p.get('title') or p.get('id') or ''))==token(production) and str(p.get('year')).isdigit()}
            if len(years)==1:year=years.pop()
        if not year:
            # Older saved roles may have a year even if their parent production
            # was never manually added to the production table.
            with connect() as db:
                local_roles=saved_cast_rows(db)
            same=[role for role in local_roles if token(canonical_production(role.get('production','')))==token(production) and role.get('year')]
            exact=[role for role in same if token(canonical_name(role.get('actress','')))==token(canonical_name(item.get('person',''))) and token(role.get('character',''))==token(item.get('character',''))]
            years={str(role['year']) for role in (exact or same)}
            if len(years)==1:year=years.pop()
    if year and str(year).isdigit() and 1880<=int(year)<=2100:
        return f'{production} ({int(year)})'
    return production

# Production-scoped character identity: unlike actor RefMod appearance,
# anatomy/markings/skin cannot be changed by a wardrobe transition.
# Only high-confidence built-ins are supplied; do not invent other roles' traits.
CURATED_CHARACTER_TRAITS = {}

# Public-character descriptions are extracted cautiously from the same exact
# character's article. These cannot replace a human appearance review; credits,
# clothing, actions, and speculative physical descriptions are never included.
_CHAR_VISUAL = re.compile(r"\b(?:skin|skinned|complexion|eyes?|eyed|hair|haired|facial markings?|facial features?|scars?|tattoos?|freckles?|antennae|horns?|tentacles?|lekku|montrals?|species|alien|non.human|cybernetic|prosthetic|robotic|android|droid|ears?|fur|feathers|scales|tails?|wings?|beak|snout|muzzle|fangs?|claws?|exoskeleton|chitin|limbs?|hooves|body markings?|pigmentation)\b",re.I)
_CHAR_EXCLUDE = re.compile(r'\b(?:wears?|wearing|dressed|clothes|clothing|costume|robe|uniform|outfit|armor|armour|jacket|shirt|dress|played|portrayed|voiced|actor|actress|filmography|episode|release|introduced|debut|created|developed|written|producer|role of|video game)\b',re.I)
_CHAR_CACHE_VERSION = 'character-v2:'

def _character_mentions(text,name):
    return bool(re.search(r'(?<!\w)'+r'\s+'.join(re.escape(x) for x in name.split())+r'(?!\w)',text,re.I))

def _character_traits_from_text(raw,character):
    """Keep only attributed visual clauses; never use arbitrary pronouns."""
    raw=re.sub(r'\[\d+\]','',str(raw or ''))[:24000]
    traits=[]
    for sentence in re.split(r'(?<=[.!?])\s+|\n+',raw):
        if not _character_mentions(sentence,character):continue
        # Casting and costume clauses sometimes follow a valid anatomy clause.
        for clause in re.split(r';|[—–]|,\s*(?=(?:and\s+)?(?:portrayed|played|voiced|wears|wearing|dressed)\b)',sentence,flags=re.I):
            clause=clause.strip(' ,;')
            if not _character_mentions(clause,character) or not _CHAR_VISUAL.search(clause) or _CHAR_EXCLUDE.search(clause):continue
            if not 12<=len(clause)<=400:continue
            if clause not in traits:traits.append(clause)
    return traits[:4]

def _fandom_character_traits(client,url,character,production):
    """Read an exact public character page's structured appearance fields only."""
    from urllib.parse import urlsplit,unquote
    u=urlsplit(url); host=u.hostname or ''
    if u.scheme!='https' or not re.fullmatch(r'[a-z0-9-]+\.fandom\.com',host) or u.port or u.username or u.password or not u.path.startswith('/wiki/') or u.query or u.fragment:return []
    if token(unquote(u.path.rsplit('/',1)[-1]))!=token(character):return []
    with client.stream('GET',url,follow_redirects=False,headers={'User-Agent':WIKI_AGENT}) as response:
        if response.status_code!=200:return []
        data=bytearray()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data)>2_000_000:return []
    soup=BeautifulSoup(bytes(data),'html.parser')
    heading=soup.select_one('h1.page-header__title, h1#firstHeading, h1')
    if not heading or token(heading.get_text(' ',strip=True))!=token(character):return []
    # The same name can occur in unrelated franchises. Require the production
    # to be mentioned in the article, not navigation or search query text.
    article=soup.select_one('.mw-parser-output')
    if not article or not _character_mentions(article.get_text(' ',strip=True),production):return []
    fields={'species':'Species','skin':'Skin','skin color':'Skin color','skin colour':'Skin color','eyes':'Eyes','eye color':'Eye color','eye colour':'Eye color','hair':'Hair','hair color':'Hair color','hair colour':'Hair color','fur':'Fur','fur color':'Fur color','scales':'Scales','markings':'Markings','facial markings':'Facial markings','distinguishing features':'Distinguishing features','physical features':'Physical features'}
    result=[]
    for item in soup.select('aside.portable-infobox .pi-item.pi-data'):
        label=item.select_one('.pi-data-label');value=item.select_one('.pi-data-value')
        if not label or not value:continue
        name=fields.get(label.get_text(' ',strip=True).casefold());text=re.sub(r'\[\d+\]','',value.get_text(' ',strip=True)).strip()
        if name and 0<len(text)<=180 and not _CHAR_EXCLUDE.search(text):result.append(name+': '+text)
    return result[:8]

def research_character_traits(character,production):
    """Bounded, on-demand lookup. No bundled character or franchise profiles."""
    character=character.strip(); production=canonical_production(production).strip()
    if not (2<=len(character)<=120 and 2<=len(production)<=150):return '', ''
    assert_public_name(character);assert_public_name(production)
    traits=[];sources=[]
    def add(items,source):
        if items:
            for text in items:
                if text not in traits:traits.append(text)
            if source not in sources:sources.append(source)
    try:
        with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as client:
            try:
                data=wiki_api(client,{'action':'query','titles':'|'.join((character,character+' (character)',production)),'redirects':1,'prop':'extracts','explaintext':1,'exintro':0})
                for page in data.get('query',{}).get('pages',[]):
                    title=page.get('title','');base=re.sub(r'\s*\([^)]*\)\s*$','',title)
                    raw=page.get('extract','') or ''
                    if page.get('missing'):continue
                    exact=token(base)==token(character) and _character_mentions(raw,production)
                    production_page=token(base)==token(production)
                    if exact or production_page:add(_character_traits_from_text(raw,character),'Wikipedia: '+title)
            except (httpx.HTTPError,ValueError,TypeError,KeyError):pass
            # Character encyclopedias often hold explicit skin/eye/species data
            # absent from general encyclopedias. Search only public role names;
            # never send reference images, performer files or private notes.
            try:
                from ddgs import DDGS
                query=f'"{character}" "{production}" character physical appearance species skin eyes'
                with DDGS(timeout=7) as ddg:results=list(ddg.text(query,max_results=6))
                fandom_checked=0
                for result in results[:6]:
                    title=str(result.get('title') or '');body=str(result.get('body') or '');url=str(result.get('href') or '')
                    if not _character_mentions(title,character):continue
                    if _character_mentions(title+' '+body,production):
                        add(_character_traits_from_text(body,character),'Public search excerpt: '+title[:160])
                    if fandom_checked<2 and '.fandom.com/wiki/' in url:
                        fandom_checked+=1
                        try:add(_fandom_character_traits(client,url,character,production),'Character encyclopedia: '+url[:240])
                        except (httpx.HTTPError,ValueError,TypeError):pass
            except Exception:pass
    except (httpx.HTTPError,ValueError,TypeError,KeyError):pass
    return ' '.join(traits)[:1800], ' · '.join(sources)[:900]

def cached_character_suggestion(character,production,auto=False,refresh=False):
    key=character_identity_key(character,production)
    with connect() as db:
        row=db.execute('SELECT traits,source,checked FROM character_identity_suggestions WHERE key=?',(key,)).fetchone()
    now=int(time.time())
    # Retry older positive and negative results once after upgrading the lookup algorithm.
    if row and not refresh and (not auto or (now-row[2] < (30*86400 if row[0] else 7*86400) and row[1].startswith(_CHAR_CACHE_VERSION))):
        return row[0],row[1].removeprefix(_CHAR_CACHE_VERSION)
    if not auto:return ('','') if row is None else (row[0],row[1].removeprefix(_CHAR_CACHE_VERSION))
    traits,source=research_character_traits(character,production)
    # Do not discard a previously useful result on a temporary lookup failure.
    if not traits and row and row[0]:traits,source=row[0],row[1].removeprefix(_CHAR_CACHE_VERSION)
    with lock,connect() as db:
        db.execute('INSERT OR REPLACE INTO character_identity_suggestions VALUES (?,?,?,?)',(key,traits,_CHAR_CACHE_VERSION+source,now))
    return traits,source

def character_identity_key(character,production):
    return token(character)+'|'+token(canonical_production(production))

def portrayal_identity_key(character,production,person='',year=None):
    if not person:return character_identity_key(character,production)
    label=portrayal_production_label({'person':person,'character':character,'production':production,'year':year})
    match=re.search(r'\((\d{4})\)$',label)
    parts=[token(canonical_name(person)),token(character),token(canonical_production(production)),match.group(1) if match else 'undated']
    return 'portrayal|'+hashlib.sha256(json.dumps(parts,separators=(',',':')).encode()).hexdigest()

def identity_row(character,production,person='',year=None):
    exact=portrayal_identity_key(character,production,person,year)
    with connect() as db:
        row=db.execute('SELECT traits FROM character_identity WHERE key=?',(exact,)).fetchone()
        if row:return row
        # Legacy custom descriptions remain a fallback, not a migration into all portrayals.
        if person:return db.execute('SELECT traits FROM character_identity WHERE key=?',(character_identity_key(character,production),)).fetchone()
    return None

def character_identity_traits(character,production,person='',year=None):
    if not character or not production:return ''
    row=identity_row(character,production,person,year)
    if row:return row[0]
    curated=CURATED_CHARACTER_TRAITS.get(token(character),'')
    return curated or cached_character_suggestion(character,production)[0]

class CharacterIdentityPayload(BaseModel):
    character:str=Field(min_length=1,max_length=180)
    production:str=Field(min_length=1,max_length=180)
    person:str=Field(default='',max_length=180)
    year:int|None=Field(default=None,ge=1880,le=2100)
    traits:str=Field(default='',max_length=2200)

@app.get('/api/characters/identity')
def get_character_identity(character:str,production:str,auto:bool=False,refresh:bool=False,person:str='',year:int|None=None):
    if not character or not production:raise HTTPException(400,'Choose a public character and production')
    assert_public_name(character);assert_public_name(production)
    if person:assert_public_name(person)
    row=identity_row(character,production,person,year)
    curated=CURATED_CHARACTER_TRAITS.get(token(character),'')
    suggested,source=('', '') if row or curated else cached_character_suggestion(character,production,auto=auto,refresh=refresh)
    default=curated or suggested
    return {'traits':row[0] if row else default,'source':'custom' if row else ('curated' if curated else ('researched' if suggested else 'none')),
            'has_override':bool(row),'default':default,'reference':source}

def validate_appearance_traits(traits):
    if any(c in traits for c in ('<Subject 2>','wardrobe_description:','detailed_description:')):
        raise HTTPException(400,'Character identity describes visual traits only; keep wardrobe and actions in their own template fields')

def exact_identity_snapshot(key):
    with connect() as db:
        row=db.execute('SELECT traits,updated_at FROM character_identity WHERE key=?',(key,)).fetchone()
    return list(row) if row else None

@app.put('/api/characters/identity')
def set_character_identity(payload:CharacterIdentityPayload):
    assert_public_name(payload.character);assert_public_name(payload.production)
    if payload.person:assert_public_name(payload.person)
    validate_appearance_traits(payload.traits)
    key=portrayal_identity_key(payload.character,payload.production,payload.person,payload.year)
    with lock,connect() as db:
        if payload.traits.strip():
            db.execute('INSERT OR REPLACE INTO character_identity VALUES (?,?,?)',(key,payload.traits.strip(),int(time.time())))
        else:
            db.execute('DELETE FROM character_identity WHERE key=?',(key,))
        db.execute('DELETE FROM appearance_analysis WHERE key=?',(key,))
    return {'saved':True,'traits':character_identity_traits(payload.character,payload.production,payload.person,payload.year)}

# Local, explicit game-world anchors; no network lookup during generation.
GAME_WORLD_DEFAULTS = {}

def game_world_context(item):
    name=clean_line(item.get('character') or item.get('person'))
    production=clean_line(item.get('production'))
    known=GAME_WORLD_DEFAULTS.get(token(name))
    if known and (not production or 'thelastofus' in token(production)):
        return known
    if production:
        return portrayal_production_label(item), ''
    titles=[]
    key=token(canonical_name(item.get('person','')))
    with connect() as db:
        rows=saved_cast_rows(db)
    for role in [*DB.get('roles',[]), *rows, *CURATED_ROLE_DATA.get(key,[])]:
        if role.get('actress') and token(canonical_name(role['actress']))!=key:continue
        title=clean_line(role.get('production'))
        if title and title not in titles:titles.append(title)
    return ' and '.join(titles), ''

def game_world_setting(item, setting):
    if setting and flatten(setting)!=flatten(SAMPLE_TEMPLATE['setting']):return flatten(setting)
    title, detail=game_world_context(item)
    universe=title or 'the fictional game universe depicted in all images provided'
    return f'A cinematic scene set within {universe}, with production-authentic architecture, terrain, atmosphere and environmental design. '+(detail or 'Use the game’s established visual world and natural environmental lighting.')

def game_subject(item):
    name=clean_line(item.get('character') or item.get('person'))
    title,_=game_world_context(item)
    return f'{name}, a fictional video-game character'+(f' as seen in {title}' if title else '')+', as depicted in all images provided.'

def is_broadcast_credit(item):
    name=item.get('person','');role=item.get('character','');production=item.get('production','')
    if not name or not role or not production:return False
    with connect() as db:
        row=db.execute('SELECT payload FROM production_cast WHERE key=?',(canonical_role_key(name,role,production),)).fetchone()
    return bool(row and (decoded_cast(row[0]) or {}).get('source')=='user-confirmed broadcast credit')

def portrayal_reference_authority(traits):
    """RefMods can encode several pictures and may be appended after native refs.
    The plugin does not expose the actual runtime reference map at preview time.
    Scope the aggregate reference instead of inventing picture numbers or roles.
    """
    text=("Use all images provided for the performer’s recognizable facial geometry, proportions and apparent age. "
          "Everyday performer photos supply facial identity only; any in-character references reinforce the specified portrayal. "
          "The character’s phenotype and anatomy take precedence over the performer’s everyday appearance, defining skin, irises, scalp or biological head structures and permanent markings.")
    if traits:
        text+=' Fixed character appearance: '+flatten(traits)
    return text


# Identity captions belong to the template toggle, not to editable scene fields.
# Recognize the two formats emitted by Casting Studio (including old pasted
# template placeholders). Leave other scene text, signage and final edits alone.
_IDENTITY_CAPTION = re.compile(
    r'(?:^[ \t]*|(?<=[.!?:])[ \t]+)'
    r'(?:A crisp, fixed bottom caption reads|Bottom caption)[ \t]*:[ \t]*'
    r'(?:"[^"\r\n]*"|“[^”\r\n]*”|["“]?\[Performer Name\][ \t]*-[ \t]*\[Character Name\][ \t]*-[ \t]*\[Production Title\](?:[ \t]*\[Year\])?[ \t]*$)'
    r'(?:[ \t]*\.)?', re.I | re.M)


def generated_caption_parts(parts, enabled, caption, *, video=False):
    """Normalize generated scenes only; never rewrite stored template fields."""
    cleaned=[]
    for part in parts:
        text=_IDENTITY_CAPTION.sub('',part)
        if text!=part:
            text=flatten(text)
            if not text:continue
        cleaned.append(text)
    if enabled and caption:
        line=(f'A crisp, fixed bottom caption reads: "{caption}".' if video
              else f'Bottom caption: "{caption}".')
        if video:
            cleaned.insert(cleaned.index('overall_soundscape:'),line)
        else:
            cleaned.append(line)
    return cleaned


def prompt_for_selection(item,t,personal=False):
    actress=clean_line(item.get('person',''))
    character=clean_line(item.get('character',''))
    production=clean_line(item.get('production',''))
    refmod=Path(str(item.get('refmod',''))).name
    if not refmod.lower().endswith('.safetensors'):refmod='NO_INSTALLED_REFMOD_SELECTED.safetensors'
    portrayal=portrayal_production_label(item) if character and production and not personal else ''
    caption=' - '.join(x for x in ((actress,clean_line(item.get('relationship',''))) if personal else (actress,character,portrayal or production)) if x)
    broadcast=not personal and is_broadcast_credit(item)
    traits=character_identity_traits(character,production,item.get('person',''),item.get('year')) if character and production and not personal and not broadcast else ''
    game_character=not personal and is_video_game_character(actress)
    if personal:
        # Private profiles remain a single real person in a neutral studio.
        identity=(f'<Subject 1> is {actress}, appearing as themselves in a professional photography studio. '
                  'all images provided collectively establish the same person’s recognizable facial identity, features and natural proportions.')
    elif game_character:
        identity=('<Subject 1> is '+game_subject(item)+' '
                  'all images provided collectively establish this character’s game-specific visual identity. '
                  'Preserve the recognizable anatomy, face, coloration, markings and physical proportions through every frame.'
                  +(f' Character-defining visual identity: {traits}' if traits else ''))
    elif broadcast:
        identity=(f'<Subject 1> is {actress}, appearing as themselves, known for their on-air role as {character} on {production}. all images provided collectively establish their recognizable facial identity, features and natural proportions.')
    elif character and production:
        identity=(f'<Subject 1> is {character} as portrayed by {actress} in {portrayal}. '
                  +portrayal_reference_authority(traits))
    else:
        identity=(f'<Subject 1> is {actress}, appearing as themselves. '
                  'all images provided collectively establish the same person’s recognizable facial identity, features and natural proportions.')
    wardrobe=flatten(t.get('wardrobe',''))
    if personal and wardrobe==flatten(SAMPLE_TEMPLATE['wardrobe']):
        wardrobe='Simple, appropriate everyday clothing, consistent throughout the presentation.'
    setting=PERSONAL_STUDIO if personal else flatten(t.get('setting',''))
    if game_character:setting=game_world_setting(item,setting)
    out=[]
    for v in range(1,max(1,min(4,int(t.get('video_count',2))))+1):
        acts=flatten(t.get('video%d_action'%v,''))
        sound=flatten(t.get('video%d_sound'%v,''))
        if personal and acts==flatten(SAMPLE_TEMPLATE[f'video{v}_action']):
            acts=PERSONAL_VIDEO_ACTIONS[v]
            if sound==flatten(SAMPLE_TEMPLATE[f'video{v}_sound']):
                sound='Quiet studio ambience and subtle natural movement.'
        live_character=bool(character and production and not personal and not broadcast and not game_character)
        if live_character:
            description='[reference generation] A photorealistic 15-second live-action shot of <Subject 1> in a new scene, following the action below.'
            keep=('<Subject 1> (throughout [Shot 1]): partially_preserved — Preserve performer facial identity and apparent age; '
                  'the defined character phenotype, anatomy, pigmentation, irises and permanent markings remain consistent from first frame to last. '
                  'Expressions, movement and scene presentation follow the shot direction.')
            dress=wardrobe
        else:
            if v==1:
                description=('[reference generation] A photorealistic continuous 15-second photography-studio shot of the same person, following the editable Video 1 actions.' if personal else '[reference generation] A photorealistic 15-second continuous shot featuring the selected character and the editable Video 1 actions.')
                if personal:
                    keep='<Subject 1> (throughout [Shot 1]): partially_preserved — Maintain the same recognizable person, facial features, anatomy and natural proportions throughout the studio shot.'
                elif game_character:
                    keep=('<Subject 1> (throughout [Shot 1]): fully_preserved — Maintain the fictional game character’s '
                          'defining anatomy, facial structure, colors, markings and proportions throughout the scene. '
                          'Preserve the established character identity through the editable actions.'
                          +(f' Character-defining visual identity: {traits}' if traits else ''))
                else:
                    keep='<Subject 1> (throughout [Shot 1]): partially_preserved — The same selected subject remains recognizably consistent through the entire continuous shot. Preserve the established identity and individual character-defining appearance throughout the editable actions.'
                dress=wardrobe
            else:
                description=(f'[reference generation] A photorealistic 15-second continuous studio shot following Video {v-1}, with editable Video {v} actions.' if personal else f'[reference generation] A photorealistic 15-second continuous shot following Video {v-1}, with editable Video {v} actions.')
                if personal:
                    keep=f'<Subject 1> (throughout [Shot 1]): partially_preserved — The same recognizable person remains consistent, with the same studio, natural proportions, and facial identity established at the end of Video {v-1}.'
                elif game_character:
                    keep='<Subject 1> (throughout [Shot 1]): fully_preserved — Continue the same fictional game character and established game-world environment across every segment.'
                else:
                    keep=f'<Subject 1> (throughout [Shot 1]): partially_preserved — Maintain performer identity, character-defining features, setting, and continuity established at the end of Video {v-1}.'
                dress=f'Use the independent wardrobe instructions for this segment: '+wardrobe
        music='N/A'
        if t.get('include_non_diegetic_music',False):
            source=clean_line(t.get('music_description') or SAMPLE_TEMPLATE['music_description'])
            music=flatten(source.replace('{production}',production or 'this original presentation'))
        if live_character:
            parts=[f'# {refmod} — Video {v}', 'subject_definitions:',identity,
                   'summary:',description,'retention_analysis:',keep,'detailed_description:',
                   '[Shot 1, 0.00s–15.00s] '+setting,acts,
                   'Maintain the defined character appearance across motion, angles and all exposed skin surfaces.',
                   '  wardrobe_description:',dress]
            parts+=['overall_soundscape:',sound,'non_diegetic_music:',music]
        else:
            parts=[f'# {refmod} — Video {v}', 'subject_definitions:',identity,
                'wardrobe_description:',dress,'summary:',description,
                'retention_analysis:',keep,'detailed_description:',
                '[Shot 1] '+setting,acts,
                'overall_soundscape:',sound,'non_diegetic_music:',music]
        out.append('\n'.join(generated_caption_parts(parts,t.get('include_caption',False),caption,video=True)))
    return '\n\n'.join(out)

# Exact old factory values are migrated field-by-field; personal edits are never parsed or rewritten.
LEGACY_IMAGE_SCENE_DEFAULTS={
 'scene1':'A production-authentic character portrait, framed chest-up with comfortable headroom. The subject looks toward the camera with a relaxed, confident expression.',
 'scene2':'A full-body character showcase, framed from head to feet with balanced space around the subject. The subject stands in a natural, confident pose.',
 'scene3':'A cinematic environmental portrait, with medium-wide framing that shows the surrounding location. The subject looks naturally toward a point of interest.',
 'scene4':'A natural action pose, captured in a medium or full-body composition with clear facial detail. The subject takes a purposeful step or makes a small expressive gesture.',
 'scene5':'A dramatic close-up portrait, with expressive eyes, a composed expression and natural facial detail. Use intimate framing and cinematic depth of field.',
}
IMAGE_SCENE_DEFAULTS={
 'scene1':'The subject stands facing the camera with a natural, relaxed posture.',
 'scene2':'The subject stands naturally with their weight balanced.',
 'scene3':'The subject looks toward a point of interest.',
 'scene4':'The subject takes a purposeful step or makes a small gesture.',
 'scene5':'The subject holds a steady pose facing the camera.',
}
IMAGE_FRAMING_DEFAULTS={
 'scene1':'Chest-up character portrait with comfortable headroom.',
 'scene2':'Full-body character showcase, from head to feet with balanced space.',
 'scene3':'Environmental portrait in a medium-wide shot showing the surroundings.',
 'scene4':'Medium or full-body composition for a natural action pose.',
 'scene5':'Dramatic close-up with intimate framing and shallow depth of field.',
}
IMAGE_EXPRESSION_DEFAULTS={
 'scene1':'Relaxed, confident expression.', 'scene2':'Natural, confident expression.',
 'scene3':'Natural, attentive gaze.', 'scene4':'Natural expression.', 'scene5':'Composed expression with expressive eyes.',
}
PERSONAL_IMAGE_ACTIONS=dict(IMAGE_SCENE_DEFAULTS)
IMAGE_MODEL_DIRECTIONS={
 'h3_image':'Cinematic, coherent photorealistic scene with high facial fidelity and production-authentic design.',
 'h3_image_pruned':'Cinematic, photorealistic portrait with high face detail and coherent natural lighting.',
 'p_h3_image':'Photorealistic original image of the selected subject, with recognizable character identity and coherent composition.',
 'flux2_dev':'Natural photographic materials, accurate illumination, cinematic lens composition and high identity fidelity.',
 'flux2_klein4':'Natural photographic light and accurate facial details.',
 'flux2_klein9':'Photorealistic photography with crisp facial details.',
 'pi_flux2':'Natural cinematic portrait lighting, accurate facial details and sharp photographic focus.',
 'flux3_klein':'Consistent photorealistic portrait with natural materials, cohesive background and clear facial detail.',
}
IMAGE_REFERENCE_LABEL={'h3_image_pruned':'<Picture 1>','p_h3_image':'<Picture 1>','h3_image':'<Picture 1>','flux2_dev':'image 1','flux2_klein4':'image 1',
 'flux2_klein9':'image 1','pi_flux2':'image 1','flux3_klein':'<ref_image_1>'}

class ImageShot(BaseModel):
    wardrobe: str = Field(default='', max_length=5000)
    action: str = Field(default='', max_length=5000)
    framing: str = Field(default='', max_length=2500)
    expression: str = Field(default='', max_length=2500)
    setting: str = Field(default='', max_length=3500)

class ImageTemplate(BaseModel):
    # Older installations store the first five images as scene1..scene5 and
    # two shared wardrobe strings. Retain those fields solely for migration.
    original_wardrobe: str = Field(default='Clothing faithful to the selected subject’s established visual appearance and appropriate to the scene. For a named production, match its wardrobe design and period. Maintain consistent clothing throughout this presentation.', max_length=5000)
    transformed_wardrobe: str = Field(default='Clothing faithful to the selected subject’s established visual appearance and appropriate to the scene. For a named production, match its wardrobe design and period. Maintain consistent clothing throughout this presentation.', max_length=5000)
    scene1: str = Field(default=IMAGE_SCENE_DEFAULTS['scene1'],max_length=5000)
    scene2: str = Field(default=IMAGE_SCENE_DEFAULTS['scene2'],max_length=5000)
    scene3: str = Field(default=IMAGE_SCENE_DEFAULTS['scene3'],max_length=5000)
    scene4: str = Field(default=IMAGE_SCENE_DEFAULTS['scene4'],max_length=5000)
    scene5: str = Field(default=IMAGE_SCENE_DEFAULTS['scene5'],max_length=5000)
    visual_style: str = Field(default='Photorealistic cinematic portrait, natural skin texture, high facial detail, coherent spatial lighting and production-appropriate setting.',max_length=5000)
    include_caption: bool = False
    image_count: int = Field(default=5, ge=1, le=10)
    shots: list[ImageShot] = Field(default_factory=list, max_length=10)


def image_template_normalized(raw=None):
    """Upgrade five-scene legacy templates without losing saved scene edits."""
    obj=ImageTemplate.model_validate(raw or {})
    data=obj.model_dump()
    count=data['image_count']
    if obj.shots:
        if len(obj.shots)!=count:
            raise ValueError(f'Expected exactly {count} image definitions; received {len(obj.shots)}')
        for i,shot in enumerate(data['shots'],1):
            k=f'scene{i}'
            if k in LEGACY_IMAGE_SCENE_DEFAULTS and shot['action']==LEGACY_IMAGE_SCENE_DEFAULTS[k]:
                shot['action']=IMAGE_SCENE_DEFAULTS[k]
                if not shot['framing']:shot['framing']=IMAGE_FRAMING_DEFAULTS[k]
                if not shot['expression']:shot['expression']=IMAGE_EXPRESSION_DEFAULTS[k]
        return data
    shots=[]
    for i in range(1,count+1):
        action=(data.get('scene'+str(i)) or IMAGE_SCENE_DEFAULTS.get('scene'+str(i)) or
                'The subject holds a natural pose.')
        wardrobe=data['original_wardrobe'] if i==1 else data['transformed_wardrobe']
        k=f'scene{i}'
        factory=action in (IMAGE_SCENE_DEFAULTS.get(k),LEGACY_IMAGE_SCENE_DEFAULTS.get(k))
        if factory:action=IMAGE_SCENE_DEFAULTS[k]
        shots.append(ImageShot(wardrobe=wardrobe,action=action,
            framing=IMAGE_FRAMING_DEFAULTS[k] if factory else '',
            expression=IMAGE_EXPRESSION_DEFAULTS[k] if factory else '').model_dump())
    data['shots']=shots
    return data


def stored_image_template(row):
    if not row:return image_template_normalized()
    try:
        raw=json.loads(row[0])
        if not isinstance(raw,dict):raise ValueError('Expected a template object')
        return image_template_normalized(raw)
    except (ValueError,TypeError):
        raise HTTPException(409,'Saved image template is damaged. Open the image template editor and reset or save a corrected template before generating.')

def image_template_for_model(model):
    selected_model(model)
    if MODEL_BY_ID[model]['kind']!='image':raise ValueError('Select an image model')
    with connect() as db:
        row=db.execute('SELECT payload FROM prompt_settings WHERE id=?',('image_'+model,)).fetchone()
    return stored_image_template(row)

@app.get('/api/prompts/image-template')
def get_image_template(model:str='h3_image'):
    try: return image_template_for_model(model)
    except ValueError as exc:raise HTTPException(400,str(exc))

@app.put('/api/prompts/image-template')
def put_image_template(payload:ImageTemplate,model:str='h3_image'):
    try:
        data=image_template_normalized(payload.model_dump())
        selected=selected_model(model)
        if selected['kind']!='image':raise ValueError('Select an image model')
    except ValueError as exc:raise HTTPException(422,str(exc))
    # New editor must supply every defined image; malformed partial updates
    # never overwrite a valid saved template.
    with lock,connect() as db:
        db.execute('INSERT OR REPLACE INTO prompt_settings VALUES (?,?)',('image_'+model,json.dumps(data)))
    return {'saved':True,'image_count':data['image_count']}

@app.post('/api/prompts/image-template/reset')
def reset_image_template(model:str='h3_image'):
    selected_model(model)
    if MODEL_BY_ID[model]['kind']!='image':raise HTTPException(400,'Select an image model')
    with lock,connect() as db:db.execute('DELETE FROM prompt_settings WHERE id=?',('image_'+model,))
    return image_template_normalized()

def image_prompts_for_selection(item,model,template,video_template,installed,personal=False,personal_mod=None):
    """Self-contained still-image jobs; no nonexistent output-image chaining."""
    template=image_template_normalized(template)
    performer=clean_line(item.get('person',''))
    character=clean_line(item.get('character',''))
    production=clean_line(item.get('production',''))
    person_mod=personal_mod if personal else installed.get(token(canonical_name(performer)),{}).get(MODEL_BY_ID[model]['family'])
    filepath=person_mod['path'] if person_mod else 'MISSING_COMPATIBLE_REFMOD'
    portrayal=portrayal_production_label(item) if character and production and not personal else ''
    broadcast=not personal and is_broadcast_credit(item)
    traits=character_identity_traits(character,production,item.get('person',''),item.get('year')) if character and production and not personal and not broadcast else ''
    game_character=not personal and is_video_game_character(performer)
    if personal:
        subject=f'{performer} appearing as themselves in a photography studio.'
    elif game_character:
        subject=game_subject(item)
    elif broadcast:
        subject=f'{performer} appearing as themselves, known for their on-air role as {character} on {production}.'
    else:
        subject=(f'{character} as portrayed by {performer} in {portrayal}.' if character and production
                 else f'{performer} appearing as themselves.')
    caption=' - '.join(filter(None,((performer,clean_line(item.get('relationship',''))) if personal else (performer,character,portrayal or production))))
    identity=('all images provided collectively establish the same person’s recognizable facial identity, natural anatomy and proportions.' if personal else
              'all images provided collectively establish the fictional game character’s defining facial features, colors, markings, anatomy and proportions.' if game_character else
              'all images provided collectively establish the performer’s recognizable facial likeness. The selected character’s on-screen species, anatomy, skin coloration and markings determine the finished appearance and take precedence over the performer’s everyday appearance.' if character and production and not broadcast else
              'all images provided collectively establish this same performer’s recognizable facial features and natural proportions.')
    direction=('Photorealistic studio portrait with accurate facial detail, soft balanced studio lighting and a neutral seamless backdrop.' if personal else IMAGE_MODEL_DIRECTIONS[model])
    # Each manifest entry starts from its selected RefMod and complete prompt.
    # Do NOT claim the preceding generated image is attached: WanGP gets
    # independent still-image jobs (not a sequential image-to-image workflow).
    refname=('<Picture 1>' if model.startswith('h3_') or model=='p_h3_image' else
             '<ref_image_1>' if model=='flux3_klein' else 'image 1')
    prompts=[]
    for n,shot in enumerate(template['shots'],1):
        scene=flatten(shot['action'])
        if personal and scene==flatten(IMAGE_SCENE_DEFAULTS.get(f'scene{n}','')) and n<=5:
            scene=PERSONAL_IMAGE_ACTIONS[f'scene{n}']
        wardrobe=flatten(shot['wardrobe'])
        if personal and wardrobe==flatten(ImageTemplate().original_wardrobe):
            wardrobe='Simple, appropriate everyday clothing.'
        setting=PERSONAL_STUDIO if personal else flatten(shot['setting'] or video_template.get('setting') or SAMPLE_TEMPLATE['setting'])
        if game_character:setting=game_world_setting(item,setting)
        live_character=bool(character and production and not personal and not broadcast and not game_character)
        if live_character:
            reference=portrayal_reference_authority(traits)
            if MODEL_BY_ID[model]['family']=='minimax_h3':
                reference='Reference roles: '+reference
            # Complete target image, not an edit/transform instruction. The same
            # natural-language reference scoping is valid across still models.
            fields=[f'### Image {n}/{template["image_count"]} — {MODEL_BY_ID[model]["label"]} — RefMod: {filepath}',
                    *(['subject_definitions:'] if model=='p_h3_image' else []),
                    subject+' A photorealistic live-action production still of this character in a new scene.',
                    reference,
                    'Maintain the defined anatomy and pigmentation across every visible exposed skin surface.',
                    ' '.join(x for x in (scene,flatten(shot['framing']),flatten(shot['expression'])) if x),
                    'wardrobe_description: '+wardrobe,
                    'Location: '+setting,
                    flatten(template.get('visual_style') or ImageTemplate().visual_style)]
        else:
            fields=[
                f'### Image {n}/{template["image_count"]} — {MODEL_BY_ID[model]["label"]} — RefMod: {filepath}',
                *(['subject_definitions:'] if model=='p_h3_image' else []),
                f'Subject: {subject}',
                f'The subject identity is defined by the selected RefMod ({refname}). '+identity,
                *([f'Character identity (fixed anatomy, coloration, markings and recognizable features): {traits}'] if traits else []),
                'Action and pose: '+scene,
                *(['Framing: '+flatten(shot['framing'])] if shot['framing'].strip() else []),
                *(['Expression: '+flatten(shot['expression'])] if shot['expression'].strip() else []),
                'wardrobe_description: '+wardrobe,
                'Location: '+setting,
                'Visual style: '+('Photorealistic professional studio photography, soft balanced light and a plain seamless background.' if personal else flatten(template.get('visual_style') or ImageTemplate().visual_style)),
                'Photographic direction: '+direction]
        prompts.append('\n'.join(generated_caption_parts(fields,template.get('include_caption',False),caption)))
    return '\n\n'.join(prompts)

def resolve_public_cast_model(item,family,models):
    """Use the exact saved reference or an unambiguous general cross-family match."""
    performer_mods=[m for m in models if token(canonical_name(m['name']))==token(canonical_name(item.get('person','')))]
    saved=item.get('refmod')
    available=[m for m in performer_mods if m['family']==family]
    exact=next((m for m in available if m['path']==saved),None)
    if exact:return exact
    original=next((m for m in performer_mods if m['path']==saved),None)
    if original and original['family']!=family and len(available)==1 and not original.get('role_specific') and not available[0].get('role_specific'):
        return available[0]
    if not available:raise ValueError('An installed RefMod for the selected model family is required')
    if original and original['family']!=family and (len(available)>1 or original.get('role_specific') or any(m.get('role_specific') for m in available)):
        raise ValueError('More than one compatible RefMod exists or the counterpart is character-specific; choose the intended file')
    raise ValueError(f"Saved RefMod is missing or belongs to an unrecognized model family: {saved or '(unset)'} for {item.get('person','unknown')}.")

@app.get('/api/prompts/export')
def export_prompts(filename:str=Query(default='RefMod_Prompts.txt',max_length=120),model:str='h3_video'):
    selected=selected_model(model)
    with connect() as db:
        choices,damaged=read_choices(db)
        if damaged:raise HTTPException(409,'Saved casting selections are damaged; repair or remove them before exporting.')
        tplrow=db.execute("SELECT payload FROM prompt_settings WHERE id='default'").fetchone()
        overrides={k:(v,) for k,v in db.execute('SELECT key,payload FROM prompt_overrides')}
        image_row=db.execute('SELECT payload FROM prompt_settings WHERE id=?',('image_'+model,)).fetchone() if selected['kind']=='image' else None
    template=stored_video_template(tplrow)
    texts=[]
    installed={}
    models=scan()
    image_template=stored_image_template(image_row) if selected['kind']=='image' else None
    # The backend, not the UI, is authoritative for Personal consent.
    personal_rows=get_personal_rows()
    by_id={r['id']:r for r in personal_rows}
    by_name={r['name_key']:r for r in personal_rows}
    available={m['path']:m for m in personal_refmod_inventory()}
    private_keys=personal_name_keys()
    for item in choices:
        pid=item.get('personal_id') or ''
        if not pid and (token(item['person']) in private_keys or token(canonical_name(item['person'])) in private_keys):continue
        private=by_id.get(pid) if pid else None
        if pid and not private:continue  # Deleted personal profile: never fall back to public export.
        t={**template,**{k:v for k,v in stored_video_template(overrides.get(item['key']),override=True).items() if k in TEMPLATE_FIELDS}}
        if private:
            if not private['consent']:continue
            linked=private['h3_refmod'] if selected['family']=='minimax_h3' else private['flux_refmod']
            if not linked or linked not in available:continue
            # Personal entries use their own neutral studio treatment, with zero production content.
            safe_item={'person':private['name'],'relationship':private['relationship'],'character':'','production':'','refmod':linked}
            t={**t,'setting':PERSONAL_STUDIO,
               'include_non_diegetic_music':False}
            if selected['kind']=='image':
                texts.append(image_prompts_for_selection(safe_item,model,image_template,t,installed,personal=True,personal_mod=available[linked]))
            else:
                # Editing actions remains possible, but original studio appearance and identity are fixed.
                texts.append(prompt_for_selection(safe_item,t,personal=True))
            continue
        try:personmod=resolve_public_cast_model(item,selected['family'],models)
        except ValueError:personmod=None
        role_models={token(canonical_name(item['person'])):{selected['family']:personmod}} if personmod else {}
        if selected['kind']=='image':texts.append(image_prompts_for_selection(item,model,image_template,t,role_models))
        else:
            video_item={**item,'refmod':personmod['path'] if personmod else 'MISSING_COMPATIBLE_REFMOD.safetensors'}
            texts.append(prompt_for_selection(video_item,t))
    text='\n\n'.join(texts)+('\n' if texts else '')
    filename=Path(filename).name
    filename=re.sub(r'[^a-zA-Z0-9 _().-]','_',filename).strip(' .')
    if not filename:filename='RefMod_Prompts.txt'
    if not filename.lower().endswith('.txt'):filename+='.txt'
    return Response(text,media_type='text/plain; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{filename}"'})


# v6.9 live WanGP queue bridge. Only the native plugin installs this service;
# export remains available when the native bridge is unavailable.
class CastTask(BaseModel):
    choice_key: str = Field(min_length=1,max_length=500)
    model: str = 'h3_video'
    model_type: str = ''
    scene: int = Field(default=1,ge=1,le=10)
    steps: int | None = Field(default=None,ge=1,le=100)
    resolution: str = Field(default='',max_length=30)
    seed: int = Field(default=-1,ge=-1,le=9007199254740991)
    strength: float = Field(default=1.0,gt=0,le=2)
    extra_settings: dict = Field(default_factory=dict)
    loras: list[dict] | None = None
    video_seconds: int = Field(default=15,ge=15,le=60)
    video_script_mode: str = Field(default='single',pattern='^(single|sequence)$')
    sliding: dict = Field(default_factory=dict)
    window_loras: dict = Field(default_factory=dict)
    fixed_windows: bool = False


def _casting_bridge():
    bridge=getattr(app.state,'casting_queue_bridge',None)
    if bridge is None:raise HTTPException(503,'WanGP integration is not running in this edition')
    return bridge


def final_prompt_key(req):
    # A continuous script has a distinct editing context; ordinary stills and
    # repeat-mode videos use their individual scene.
    sequence=req.model=='h3_video' and getattr(req,'video_seconds',15)>15 and getattr(req,'video_script_mode','single')=='sequence'
    return json.dumps([req.choice_key,req.model,req.model_type,0 if sequence else req.scene,req.video_seconds if sequence else 0],separators=(',',':'))

def build_live_cast_prompt(req, *, use_saved=True, monitor_details=None):
    """Re-read selection AND consent for every enqueue and worker start.

    Return (prompt, family, validated path), never user-provided path/notes.
    """
    selected=selected_model(req.model)
    with connect() as db:
        row=db.execute('SELECT payload FROM choices WHERE key=?',(req.choice_key,)).fetchone()
        tplrow=db.execute("SELECT payload FROM prompt_settings WHERE id='default'").fetchone()
        override=db.execute('SELECT payload FROM prompt_overrides WHERE key=?',(req.choice_key,)).fetchone()
        imgrow=db.execute('SELECT payload FROM prompt_settings WHERE id=?',('image_'+req.model,)).fetchone() if selected['kind']=='image' else None
        final_edit=db.execute('SELECT prompt,personal_id FROM final_prompt_edits WHERE key=?',(final_prompt_key(req),)).fetchone() if use_saved else None
    if not row:raise ValueError('Selection no longer exists; select that casting choice again')
    item=require_choice(req.choice_key,row[0]); family=selected['family']
    if not item.get('personal_id') and (token(item['person']) in personal_name_keys() or token(canonical_name(item['person'])) in personal_name_keys()):
        raise PermissionError('Use the Personal tab for this profile; re-select it explicitly')
    base=stored_video_template(tplrow)
    overrides=stored_video_template(override,override=True)
    template={**base,**{k:v for k,v in overrides.items() if k in TEMPLATE_FIELDS}}
    image_template=stored_image_template(imgrow) if selected['kind']=='image' else None
    pid=item.get('personal_id') or ''
    rows=get_personal_rows()
    by_id={r['id']:r for r in rows};by_name={r['name_key']:r for r in rows}
    personal=by_id.get(pid) if pid else None
    if pid and not personal:raise ValueError('Personal profile was deleted')
    if personal:
        if not personal['consent']:raise PermissionError('Consent revoked or missing: cannot generate Personal content')
        if token(item.get('person',''))!=personal['name_key']:
            raise ValueError('Stored personal profile and casting identity do not match')
        link=personal['h3_refmod'] if family=='minimax_h3' else personal['flux_refmod']
        available={m['path']:m for m in personal_refmod_inventory()}
        if not link or link not in available:
            raise ValueError('Personal RefMod is not installed for this model')
        safe={'person':personal['name'],'relationship':personal['relationship'],
              'character':'','production':'','refmod':link}
        template={**template,'setting':PERSONAL_STUDIO,
                  
                  'include_non_diegetic_music':False}
        modpath=link
        installed={}
        ref=available[link]
    else:
        installed={}
        ref=resolve_public_cast_model(item,family,scan())
        modpath=ref['path']
        safe={**item,'refmod':modpath}
        installed[token(canonical_name(item['person']))]={family:ref}
    if req.scene>(4 if selected['kind']=='video' else image_template['image_count']):
        raise ValueError('Unsupported scene number for model or saved image set')
    if selected['kind']=='image':
        joined=image_prompts_for_selection(safe,req.model,image_template,template,installed,
                                           personal=bool(personal),personal_mod=ref if personal else None)
        segments=joined.split('\n\n')
    else:
        segments=prompt_for_selection(safe,template,personal=bool(personal)).split('\n\n')
    if req.scene>len(segments):raise ValueError('Scene is not configured in the saved prompt template')
    # A generated prompt's first line is an export heading, not part of the
    # actual model prompt; leave identity/wardrobe/caption content intact.
    prompt=segments[req.scene-1].split('\n',1)[-1]
    if selected['kind']=='video' and getattr(req,'video_seconds',15)>15 and getattr(req,'video_script_mode','single')=='sequence':
        # The native WanGP PW mode treats each paragraph as one sliding-window
        # prompt, resulting in ONE continuous clip, not separate 15s jobs.
        # Preserve each user's independently edited Video 1–4 instructions.
        window_count=min(4,(int(req.video_seconds)+14)//15)
        # If a saved video template has fewer scenes, repeat the final edited
        # scene rather than dropping later seconds of the requested production.
        segments=segments or [prompt]
        script=[(segments[min(i,len(segments)-1)].split('\n',1)[-1])
                for i in range(window_count)]
        prompt='\n\n'.join(script)
    # Resolve against the same files the native plugin exposes; file checking
    # (including path-traversal checks) occurs again in queue_bridge.
    if family=='minimax_h3':
        base_dir=PERSONAL_H3 if personal else REFS
        relative=modpath.split('/',1)[1] if personal else modpath
        path=(base_dir/relative).resolve()
    else:
        base_dir=PERSONAL_FLUX if personal else FLUX_REFS
        relative=modpath[len('flux2/personal/'):] if personal else modpath[len('flux2/'):]
        if not personal and relative.startswith('celebs/'):
            base_dir=base_dir/'celebs';relative=relative[len('celebs/'):]
        path=(base_dir/relative).resolve()
    if not path.is_relative_to(base_dir.resolve()) or not path.is_file():
        raise ValueError('Selected RefMod file is missing or outside its allowed directory')
    if monitor_details is not None:
        monitor_details.update(person=safe['person'], character=safe.get('character',''), production=portrayal_production_label(item) if not personal and item.get('production') else '', kind=selected['kind'], scene=req.scene, personal=bool(personal))
    return (final_edit[0] if final_edit and final_edit[1]==(item.get('personal_id') or '') else prompt), family, path


# Portrait jobs are deliberately independent from casting choices and templates.
class PortraitRequest(BaseModel):
    model: str
    model_type: str = Field(min_length=1,max_length=200)
    loras: list[dict] | None = None
    replace: bool = False

portrait_jobs_lock=threading.Lock()
portrait_jobs={}

@app.get('/api/personal/{personal_id}/portrait-models')
def portrait_models(personal_id:str):
    profile=personal_row_by_id(personal_id)
    if not profile:raise HTTPException(404,'Personal profile not found')
    if not profile['consent']:raise HTTPException(403,'Consent required')
    known={m['path'] for m in personal_refmod_inventory()}
    bridge=_casting_bridge();out=[]
    for option in MODEL_OPTIONS:
        if option['kind']!='image':continue
        field='h3_refmod' if option['family']=='minimax_h3' else 'flux_refmod'
        if profile[field] not in known:continue
        try:models=bridge.models(option['id'])
        except (ValueError,RuntimeError):continue
        for model in models:
            if model['ready']:out.append({'model':option['id'],'model_type':model['model_type'],'name':model['name']})
    return out

def portrait_prompt(model):
    ref=('<Picture 1>' if model.startswith('h3_') or model=='p_h3_image' else '<ref_image_1>' if model=='flux3_klein' else 'image 1')
    return ('Subject: the same person as depicted in all images provided. The linked Personal RefMod ('+ref+') establishes the subject’s recognizable facial identity, hair, natural anatomy and proportions. '
            'A single realistic chest-up profile portrait, face centered, looking toward the camera with a relaxed friendly expression. '
            'wardrobe_description: Simple, appropriate everyday clothing. '
            'Location: A seamless neutral gray studio background with soft, balanced professional portrait lighting. '
            'Photographic direction: natural skin texture, sharp facial detail, comfortable headroom, centered composition suitable for a profile thumbnail.')

@app.post('/api/personal/{personal_id}/portrait-generate')
def generate_personal_portrait(personal_id:str,req:PortraitRequest):
    from ..queue_bridge import Submission
    bridge=_casting_bridge()
    selected=selected_model(req.model)
    if selected['kind']!='image':raise HTTPException(400,'Choose an image model')
    profile=personal_row_by_id(personal_id)
    if not profile:raise HTTPException(404,'Personal profile not found')
    if not profile['consent']:raise HTTPException(403,'Consent required')
    if profile['portrait'] and not req.replace:raise HTTPException(409,'Confirm replacement of the existing portrait')
    family=selected['family'];field='h3_refmod' if family=='minimax_h3' else 'flux_refmod'
    linked=profile[field]
    def check_profile():
        current=personal_row_by_id(personal_id)
        if not current or not current['consent']:raise PermissionError('Personal consent revoked or profile deleted')
        if current[field]!=linked or current['name_key']!=profile['name_key']:raise ValueError('Personal identity or RefMod changed')
        if current['portrait']!=profile['portrait']:raise ValueError('Portrait changed while this job was pending')
        return current
    def validate(submission):
        check_profile()
        if not linked or not any(m['path']==linked and m['family']==family for m in personal_refmod_inventory()):raise ValueError('Link an installed Personal RefMod for this image model')
        path=bridge.adapter.validate_refmod(relative_path=linked,family=family,personal=True)
        return portrait_prompt(req.model),family,path
    def complete(files):
        # Only consume paths returned by this native job, never client paths or inference previews.
        paths=[Path(f) for f in files if Path(f).suffix.lower() in ('.png','.jpg','.jpeg','.webp')]
        if len(paths)!=1:raise ValueError('Expected exactly one generated image; existing portrait retained')
        path=paths[0]
        if not path.is_absolute():path=bridge.adapter.root/path
        if not path.is_file():raise ValueError('WanGP output image could not be found')
        with Image.open(path) as pic:
            if pic.format not in ('JPEG','PNG','WEBP') or pic.width<100 or pic.height<100 or pic.width*pic.height>40_000_000:raise ValueError('Invalid generated portrait')
            rgb=pic.convert('RGB');rgb.thumbnail((1400,1400),Image.Resampling.LANCZOS)
        filename=personal_id+'-'+uuid.uuid4().hex[:10]+'.webp';dest=PERSONAL_PORTRAITS/filename
        with lock:
            current=check_profile()
            try:
                rgb.save(dest,format='WEBP',quality=90)
                with connect() as db:
                    changed=db.execute('UPDATE personal_profiles SET portrait=?,updated_at=? WHERE id=? AND consent=1 AND portrait=? AND '+field+'=? AND name_key=?',(filename,int(time.time()),personal_id,profile['portrait'],linked,profile['name_key'])).rowcount
                    if changed!=1:raise ValueError('Profile changed before portrait save')
            except Exception:
                dest.unlink(missing_ok=True);raise
            remove_owned_portrait(current['portrait'],current['id'])
        return 'api/personal/portraits/'+filename
    submission=Submission(model=req.model,model_type=req.model_type,choice_key='portrait:'+personal_id,loras=req.loras,portrait_completion=complete,monitor_details={'person':profile['name'],'kind':'image','scene':1,'personal':True})
    try:
        with portrait_jobs_lock:
            previous=portrait_jobs.get(personal_id)
            if previous and (bridge.status(previous) or {}).get('state') in ('queued','running'):raise HTTPException(409,'A portrait job is already active for this profile')
            job=bridge.enqueue(submission,validate);portrait_jobs[personal_id]=job
        return {'id':job,'state':'queued'}
    except PermissionError as exc:raise HTTPException(403,str(exc))
    except (ValueError,RuntimeError) as exc:raise HTTPException(400,str(exc))

@app.get('/api/generator/models',include_in_schema=False)
def generator_models(model:str='h3_video'):
    try:return {'models':_casting_bridge().models(model)}
    except ValueError as exc:raise HTTPException(400,str(exc))
    except RuntimeError as exc:raise HTTPException(503,str(exc))

@app.get('/api/generator/model-details',include_in_schema=False)
def generator_model_details(model:str='h3_video',model_type:str=''):
    if not model_type:raise HTTPException(400,'Choose a WanGP model first')
    try:return _casting_bridge().model_details(model,model_type)
    except ValueError as exc:raise HTTPException(400,str(exc))
    except RuntimeError as exc:raise HTTPException(503,str(exc))


def preview_window_loras(task,prompt):
    if not task.window_loras and not task.fixed_windows:return prompt
    bridge=_casting_bridge()
    loras=bridge._validate_loras(task,bridge._model_record(task.model_type)) if task.window_loras else None
    return bridge.apply_fixed_window_plan(bridge._apply_window_lora_multipliers(prompt,task,loras),task)

@app.post('/api/generator/preview',include_in_schema=False)
def generator_preview(task:CastTask):
    try:
        from types import SimpleNamespace
        raw,family,path=build_live_cast_prompt(task)
        prompt=preview_window_loras(task,raw)
        with connect() as db:edited=bool(db.execute('SELECT 1 FROM final_prompt_edits WHERE key=?',(final_prompt_key(task),)).fetchone())
        return {'prompt':prompt,'editable_prompt':raw,'edited':edited,'family':family,'refmod_filename':path.name,'scene':task.scene}
    except PermissionError as exc:raise HTTPException(403,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))

class FinalPromptEdit(BaseModel):
    task: CastTask
    prompt: str | None = Field(default=None,max_length=100000)

@app.put('/api/generator/prompt-edit',include_in_schema=False)
def save_final_prompt_edit(edit:FinalPromptEdit):
    task=edit.task
    try:
        # Validate the current choice and private consent before saving/resetting.
        build_live_cast_prompt(task,use_saved=False)
        if not task.model_type:raise ValueError('Choose an installed model first')
        key=final_prompt_key(task)
        text=edit.prompt
        if text is not None:
            text=text.replace('\r\n','\n').strip()
            if len(text)<12:raise ValueError('Enter a complete prompt (at least 12 characters)')
            sequence=task.model=='h3_video' and task.video_seconds>15 and task.video_script_mode=='sequence'
            if sequence and (len(text.split('\n\n'))!=(task.video_seconds+14)//15 or any(not x.strip() for x in text.split('\n\n'))):
                raise ValueError('Keep one prompt paragraph per sliding window, separated by a blank line')
            preview_window_loras(task,text)
        with lock,connect() as db:
            row=db.execute('SELECT payload FROM choices WHERE key=?',(task.choice_key,)).fetchone()
            if not row:raise ValueError('Casting selection no longer exists')
            current=require_choice(task.choice_key,row[0])
            pid=current.get('personal_id') or ''
            if not pid:assert_public_name(current['person'])
            if pid and not db.execute('SELECT 1 FROM personal_profiles WHERE id=? AND consent=1',(pid,)).fetchone():raise PermissionError('Personal consent is missing or revoked')
            if text is None:db.execute('DELETE FROM final_prompt_edits WHERE key=?',(key,))
            else:db.execute('INSERT OR REPLACE INTO final_prompt_edits(key,choice_key,personal_id,prompt) VALUES (?,?,?,?)',(key,task.choice_key,pid,text))
        return {'saved':text is not None}
    except PermissionError as exc:raise HTTPException(403,str(exc))
    except (ValueError,RuntimeError) as exc:raise HTTPException(400,str(exc))

def retry_choice_personal_id(key):
    with connect() as db:row=db.execute('SELECT payload FROM choices WHERE key=?',(key,)).fetchone()
    if not row:raise ValueError('Casting selection no longer exists')
    return require_choice(key,row[0]).get('personal_id') or ''

def snapshot_cast_validator():
    staged={}
    def validate(task):
        k=final_prompt_key(task)
        details={}
        prompt,family,path=build_live_cast_prompt(task,use_saved=k not in staged,monitor_details=details)
        if k not in staged:staged[k]=(prompt,family,path,details)
        saved,old_family,old_path,old_details=staged[k]
        task.monitor_details=dict(old_details)
        if (old_family,old_path)!=(family,path):raise ValueError('RefMod changed after staging; queue the task again')
        # Private snapshot kept in runtime DB only if native WanGP confirms failure.
        if not hasattr(task,'_retry_snapshot'):
            st=path.stat()
            task._retry_snapshot={'prompt':saved,'family':family,'path':str(path),'size':st.st_size,'mtime':st.st_mtime_ns,'details':dict(old_details),'personal_id':retry_choice_personal_id(task.choice_key)}
        else:
            snap=task._retry_snapshot;st=path.stat()
            if (st.st_size,st.st_mtime_ns,details,retry_choice_personal_id(task.choice_key))!=(snap['size'],snap['mtime'],snap['details'],snap.get('personal_id','')):raise ValueError('Original casting identity or RefMod changed; queue the task again')
        return saved,family,path
    return validate

@app.post('/api/generator/submit',include_in_schema=False)
def generator_submit(task:CastTask):
    bridge=_casting_bridge()
    if not task.model_type:raise HTTPException(400,'Choose a WanGP model')
    try:
        from types import SimpleNamespace
        from ..queue_bridge import Submission
        submission=Submission(model=task.model,model_type=task.model_type,
                              choice_key=task.choice_key,scene=task.scene,
                              steps=task.steps,resolution=task.resolution,seed=task.seed,
                              strength=task.strength,extra_settings=task.extra_settings,loras=task.loras,video_seconds=task.video_seconds,video_script_mode=task.video_script_mode,sliding=task.sliding,window_loras=task.window_loras,fixed_windows=task.fixed_windows)
        # Callable must be invoked for worker execution as well as preflight.
        job_id=bridge.enqueue(submission,snapshot_cast_validator())
        return {'id':job_id,'state':'queued'}
    except PermissionError as exc:raise HTTPException(403,str(exc))
    except (ValueError,RuntimeError) as exc:raise HTTPException(400,str(exc))

class CastBatchRequest(BaseModel):
    task:CastTask
    scope:str=Field(default='all',max_length=260)
    scene_mode:str=Field(default='first',pattern='^(first|all)$')


def expand_cast_batch(req:CastBatchRequest):
    selected=selected_model(req.task.model)
    with connect() as db:
        entries,damaged=read_choices(db)
        if damaged and (not req.scope.startswith('selection:') or req.scope[len('selection:'):] in damaged):
            raise HTTPException(409,'Saved casting selections are damaged; repair or remove them before queueing a batch.')
        row=db.execute("SELECT payload FROM prompt_settings WHERE id='default'").fetchone()
        overrides={k:(v,) for k,v in db.execute('SELECT key,payload FROM prompt_overrides')}
    if req.scope!='all':
        if req.scope.startswith('selection:') and req.scope[len('selection:'):]:
            selected_key=req.scope[len('selection:'):]
            entries=[it for it in entries if it.get('key')==selected_key]
        elif req.scope.startswith('production:') and req.scope[len('production:'):]:
            prod=req.scope[len('production:'):]
            entries=[it for it in entries if not it.get('personal_id') and
                     token(canonical_production(it.get('production','')))==prod]
        else:raise ValueError('Unknown queue scope')
    if not entries:raise ValueError('No saved selections match this batch scope')
    # Independent image-set tasks do not require output-image chaining.
    base=stored_video_template(row)
    tasks=[];labels=[]
    for entry in entries:
        count=1
        if req.scene_mode=='all':
            if selected['kind']=='image':
                count=image_template_for_model(req.task.model)['image_count']
            else:
                if req.task.video_seconds>15 and req.task.video_script_mode=='sequence':
                    count=1
                else:
                    ov=stored_video_template(overrides.get(entry.get('key','')),override=True)
                    count=max(1,min(4,int(ov.get('video_count',base.get('video_count',2)))))
        for index in range(1,count+1):
            task=req.task.model_copy(update={'choice_key':entry['key'],'scene':index})
            tasks.append(task)
            labels.append({'person':entry.get('person',''), 'character':entry.get('character',''),
                           'production':portrayal_production_label(entry) if entry.get('production') else '',
                           'scene':index,'kind':selected['kind'],'choice_key':entry['key']})
            if len(tasks)>2000:
                raise ValueError('Batch exceeds 2000 generation tasks; select fewer roles or images')
    return tasks,labels

@app.post('/api/generator/batch/preview',include_in_schema=False)
def generator_batch_preview(request:CastBatchRequest):
    from types import SimpleNamespace
    try:
        tasks,labels=expand_cast_batch(request)
        out=[]
        for task,label in zip(tasks,labels):
            prompt,family,path=build_live_cast_prompt(SimpleNamespace(**task.model_dump()))
            prompt=preview_window_loras(task,prompt)
            out.append({**label,'prompt':prompt,'refmod_filename':path.name})
        return {'count':len(out),'selections':len(set(x['choice_key'] for x in out)),
                'tasks':out,'model_type':request.task.model_type}
    except PermissionError as exc:raise HTTPException(403,str(exc))
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc))

@app.post('/api/generator/batch/submit',include_in_schema=False)
def generator_batch_submit(request:CastBatchRequest):
    bridge=_casting_bridge()
    if not request.task.model_type:raise HTTPException(400,'Choose a compatible WanGP model')
    from types import SimpleNamespace
    from ..queue_bridge import Submission
    try:
        tasks,labels=expand_cast_batch(request)
        submissions=[Submission(model=t.model,model_type=t.model_type,choice_key=t.choice_key,
                     scene=t.scene,steps=t.steps,resolution=t.resolution,seed=t.seed,
                     strength=t.strength,extra_settings=t.extra_settings,loras=t.loras,video_seconds=t.video_seconds,video_script_mode=t.video_script_mode,sliding=t.sliding,window_loras=t.window_loras,fixed_windows=t.fixed_windows)
                     for t in tasks]
        batch_id=bridge.enqueue_batch(submissions,snapshot_cast_validator())
        return {'id':batch_id,'state':'queued','task_count':len(tasks),'selections':len(set(x['choice_key'] for x in labels))}
    except PermissionError as exc:raise HTTPException(403,str(exc))
    except (ValueError,TypeError,RuntimeError) as exc:raise HTTPException(400,str(exc))

def persist_cast_gallery(records):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO casting_gallery VALUES (1,?)',(json.dumps(records,allow_nan=False),))


def load_cast_gallery():
    with connect() as db:row=db.execute('SELECT payload FROM casting_gallery WHERE id=1').fetchone()
    try:records=json.loads(row[0]) if row else []
    except (ValueError,TypeError):return []
    if not isinstance(records,list):return []
    # Do not restore private identities without current consent.
    consent={token(p['name']) for p in get_personal_rows() if p['consent']}
    out=[]
    for rec in records:
        if not isinstance(rec,dict) or not isinstance(rec.get('output'),dict):continue
        details=rec['output'].get('task_details') or {}
        if not isinstance(details,dict):continue
        if details.get('personal') and token(details.get('person','')) not in consent:continue
        out.append(rec)
    return out


historical_retry_lock=threading.RLock()

def historical_retry_tasks(record):
    tasks=record.get('_retry_tasks')
    indices=record.get('failed_task_indices')
    if record.get('state')!='failed' or record.get('retried_as') or record.get('_retry_pending') or not isinstance(tasks,list) or not tasks or not isinstance(indices,list):return []
    if any(not isinstance(t,dict) or not isinstance(t.get('snapshot'),dict) or not {'prompt','family','path','size','mtime','details','personal_id'}<=set(t['snapshot']) or not isinstance(t.get('settings'),dict) for t in tasks):return []
    if [t.get('index') for t in tasks]!=indices or any(type(i) is not int or i<1 for i in indices) or len(set(indices))!=len(indices):return []
    return tasks


def retry_historical_job(job_id,bridge):
    from ..queue_bridge import Submission
    with historical_retry_lock:
        with connect() as db:row=db.execute('SELECT payload FROM casting_job_history WHERE id=?',(job_id,)).fetchone()
        if not row:raise ValueError('Historical job not found')
        record=json.loads(row[0]);tasks=historical_retry_tasks(record)
        if not tasks:raise ValueError('No confirmed failed task snapshots available')
        subs=[]
        for t in tasks:
            sub=Submission(**t['settings']);sub._retry_snapshot=t['snapshot'];subs.append(sub)
        def validate(sub):
            snap=sub._retry_snapshot;details={}
            _,family,path=build_live_cast_prompt(sub,use_saved=False,monitor_details=details)
            st=path.stat()
            if (family,str(path),st.st_size,st.st_mtime_ns,details,retry_choice_personal_id(sub.choice_key))!=(snap['family'],snap['path'],snap['size'],snap['mtime'],snap['details'],snap['personal_id']):raise ValueError('Original casting identity or RefMod changed; create a new job instead')
            sub.monitor_details=dict(details)
            return snap['prompt'],family,path
        # Claim before staging, so an interruption cannot cause an automatic duplicate.
        # Explicitly rejected submissions release the claim; a crashed process leaves it blocked.
        for sub in subs:bridge.preflight(sub,validate)
        record['_retry_pending']=True
        persist_cast_job_history(record)
        try:
            jid=bridge.enqueue_batch(subs,validate) if record.get('_retry_batch') else bridge.enqueue(subs[0],validate)
        except Exception:
            record.pop('_retry_pending',None);persist_cast_job_history(record);raise
        record.pop('_retry_pending',None);record['retried_as']=jid;record.pop('_retry_tasks',None)
        persist_cast_job_history(record)
        return jid,len(subs)


def persist_cast_job_history(record):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO casting_job_history VALUES (?,?,?)',
                   (record['id'],time.time_ns(),json.dumps(record,allow_nan=False)))
        db.execute('DELETE FROM casting_job_history WHERE id NOT IN (SELECT id FROM casting_job_history ORDER BY updated DESC LIMIT 100)')

@app.get('/api/generator/history',include_in_schema=False)
def casting_job_history():
    bridge=getattr(app.state,'casting_queue_bridge',None)
    with connect() as db:rows=db.execute('SELECT updated,payload FROM casting_job_history ORDER BY updated DESC LIMIT 100').fetchall()
    results=[]
    for updated,payload in rows:
        try:record=json.loads(payload)
        except (TypeError,ValueError):continue
        if not isinstance(record,dict) or not isinstance(record.get('id'),str):continue
        record['updated']=updated//1_000_000
        record['retry_count']=(len(bridge.retryable_indices(record['id'])) if bridge and bridge.status(record['id']) else len(historical_retry_tasks(record))) if bridge else 0
        for k in list(record):
            if k.startswith('_retry_'):record.pop(k,None)
        if record.get('state') in ('queued','running') and (not bridge or not bridge.status(record['id'])):
            record['state']='unknown';record['message']='WanGP restarted or job expired; outcome is not confirmed.'
        results.append(record)
    return {'jobs':results}

@app.delete('/api/generator/history',include_in_schema=False)
def clear_casting_job_history():
    with connect() as db:db.execute('DELETE FROM casting_job_history')
    return {'cleared':True}

@app.post('/api/generator/jobs/{job_id}/retry-failed',include_in_schema=False)
def retry_failed_cast_job(job_id:str):
    try:
        bridge=_casting_bridge()
        new_id,count=bridge.retry_failed(job_id) if bridge.status(job_id) else retry_historical_job(job_id,bridge)
        return {'id':new_id,'task_count':count,'state':'queued'}
    except PermissionError as exc:raise HTTPException(403,str(exc))
    except (ValueError,TypeError,RuntimeError) as exc:raise HTTPException(400,str(exc))

@app.post('/api/generator/batch/preflight',include_in_schema=False)
def casting_batch_preflight(request:CastBatchRequest):
    from ..queue_bridge import Submission
    bridge=_casting_bridge()
    try:tasks,labels=expand_cast_batch(request)
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc))
    issues=[];blocked=0;ready=[]
    for task,label in zip(tasks,labels):
        try:
            sub=Submission(**task.model_dump())
            # Match the existing side-effect-free enqueue gate, never submit.
            bridge.preflight(sub,snapshot_cast_validator())
            ready.append({**label,'refmod': 'Installed and validated'})
        except (HTTPException,ValueError,TypeError,RuntimeError,PermissionError) as exc:
            blocked+=1
            if len(issues)<100:issues.append({**label,'issue':str(getattr(exc,'detail',exc))[:600]})
    relay=bridge.live_session_ready and callable(getattr(bridge.api_session,'submit_manifest',None))
    return {'count':len(tasks),'ready':len(ready),'blocked':blocked,'issues':issues,
            'relay_ready':bool(relay),'model_type':request.task.model_type,
            'loras':request.task.loras or [],'resolution':request.task.resolution or 'Model default',
            'steps':request.task.steps,'selections':len(set(x['choice_key'] for x in labels))}

@app.get('/api/generator/jobs/{job_id}',include_in_schema=False)
def generator_job_status(job_id:str, live_preview:bool|None=None, follow:bool=False):
    bridge=_casting_bridge()
    if follow:result=bridge.monitor_status(job_id,live_preview)
    else:
        if live_preview is not None:bridge.set_preview_interest(job_id,live_preview)
        result=bridge.status(job_id)
    if not result:raise HTTPException(404,'Generation job not found in this WanGP process')
    return result

@app.get('/api/generator/jobs/{job_id}/preview', include_in_schema=False)
def generator_job_preview(job_id: str, task: int | None = Query(default=None,ge=1), rev: int | None = Query(default=None,ge=1)):
    # Bytes are produced by WanGP's on_preview callback. They are never read
    # from user-supplied paths or other services on the host.
    preview = _casting_bridge().preview(job_id, task, rev)
    if preview is None:
        raise HTTPException(404, 'WanGP has not emitted a preview for this job')
    payload, media_type = preview
    return Response(content=payload, media_type=media_type,
                    headers={'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'})

@app.get('/api/generator/monitor-gallery',include_in_schema=False)
def generator_monitor_gallery():
    return {'results':_casting_bridge().monitor_gallery()}

@app.get('/api/generator/monitor-output/{token}',include_in_schema=False)
def generator_monitor_output(token:str):
    output=_casting_bridge().monitor_output(token)
    if not output:raise HTTPException(404,'Completed output unavailable')
    path,mime=output
    return FileResponse(path,media_type=mime,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

@app.post('/api/generator/jobs/{job_id}/abort-current',include_in_schema=False)
def generator_abort_current(job_id:str,task:int=Query(ge=1)):
    try:_casting_bridge().abort_current(job_id,task)
    except (ValueError,RuntimeError,KeyError,AttributeError) as exc:raise HTTPException(409,str(exc))
    return {'cancellation_requested':True}

@app.post('/api/generator/jobs/{job_id}/cancel',include_in_schema=False)
def generator_job_cancel(job_id:str):
    try:accepted=_casting_bridge().cancel(job_id)
    except Exception as exc:raise HTTPException(409,'WanGP did not accept cancellation; refresh the job and retry.') from exc
    if not accepted:raise HTTPException(409,'This job cannot currently be cancelled')
    return {'cancellation_requested':True}


# v6.4 Production explorer + optional reference-image collections.
class ProductionRequest(BaseModel):
    name:str=Field(min_length=2,max_length=180)
    kind:str='series'
    year:int|None=None

class CastRequest(BaseModel):
    production:str=Field(min_length=2,max_length=180)
    actress:str=Field(min_length=2,max_length=150)
    character:str=Field(default='',max_length=150)
    year:int|None=None
    image:str=Field(default='',max_length=2048)

def production_coverage(production,cast,model='h3_video'):
    family=selected_model(model)['family']
    all_models=scan()
    byname={}
    for m in all_models:
        k=token(canonical_name(m['name']))
        byname.setdefault(k,{})[m['family']]=m
    results=[]
    for r in cast:
        k=token(canonical_name(r['actress']))
        available=byname.get(k,{})
        matched=available.get(family)
        results.append({**r,'installed':bool(matched),'refmod':matched['path'] if matched else '',
                        'refmod_families':{key:v['path'] for key,v in available.items()}})
    return results

def production_credit_candidates(production, mapped_people=None):
    """Public installed performers with this legacy known credit but no mapped role.

    A title alone is not a character, so these are discovery leads, never
    synthetic casting entries. Personal profiles are excluded by normalized_catalog.
    """
    wanted=token(canonical_production(production))
    people,roles=normalized_catalog(discovery=True)
    mapped_people=(mapped_people if mapped_people is not None else
                   {token(role['actress']) for role in roles
                    if token(canonical_production(role.get('production','')))==wanted})
    return [person['name'] for person in people if token(person['name']) not in mapped_people
            and any(token(canonical_production(credit))==wanted
                    for credit in person.get('credits',[]) if isinstance(credit,str))]

@app.get('/api/productions')
def list_productions(q: str = ""):
    wanted=token(q)
    if not wanted:return []
    people,roles=normalized_catalog(discovery=True)
    result={}
    for r in roles:
        name=canonical_production(r.get('production',''))
        if name and (wanted in token(name) or wanted in token(r.get('character','')) or wanted in token(r.get('actress',''))):
            key=token(name)
            item=result.setdefault(key,{'name':name,'kind':'existing','year':None,'mapped_roles':0,'known_performers':[]})
            item['mapped_roles']+=1
            if r.get('year') and not item.get('year'):item['year']=r['year']
    # Seed metadata also supplies known years for roles with legacy title strings.
    for record in DB.get('productions',[]):
        name=canonical_production(record.get('title') or record.get('id') or '')
        k=token(name)
        if k not in result and (not name or wanted not in k):continue
        entry=result.setdefault(k,{'name':name,'kind':'known production','year':None,'mapped_roles':0,'known_performers':[]})
        year=record.get('year')
        if str(year).isdigit() and not entry.get('year'):entry['year']=int(year)
    counts={}
    for role in roles:
        k=token(canonical_production(role.get('production','')));counts[k]=counts.get(k,0)+1
    for k,entry in result.items():entry['mapped_roles']=counts.get(k,0)
    # Display legacy known credits as DISCOVERY LEADS. These previously appeared
    # on performer cards but never made it into the Productions tab at all.
    for person in people:
        for title in person.get('credits',[]):
            if not isinstance(title,str):continue
            name=canonical_production(title)
            if not (2<=len(name)<=180) or wanted not in token(name):continue
            k=token(name)
            entry=result.setdefault(k,{'name':name,'kind':'known credit','year':None,
                                       'mapped_roles':0,'known_performers':[]})
            if len(entry['known_performers'])<50 and person['name'] not in entry['known_performers']:
                entry['known_performers'].append(person['name'])
    with connect() as db:
        for key,name,year,kind in db.execute('SELECT key,name,year,kind FROM productions'):
            if wanted not in token(name):continue
            entry=result.setdefault(key,{'name':name,'kind':kind,'year':year,
                                         'mapped_roles':0,'known_performers':[]})
            entry.update(name=name,year=year or entry.get('year'),kind=kind)
    for entry in result.values():
        entry['needs_role_discovery']=bool(entry.get('known_performers')) and entry['mapped_roles']==0
    return sorted(result.values(),key=lambda r:r['name'].casefold())

# Television personalities: explicitly requested public research, separate from the
# installed-only performer browser. No network calls or mutations during local search.
TV_CATEGORIES={'TV personality','Presenter'}

@app.get('/api/television/people')
def television_people(q:str=Query(min_length=1,max_length=160),model:str='h3_video'):
    wanted=token(q)
    if not wanted:return []
    people,roles=normalized_catalog(discovery=True)
    tv=[p for p in people if TV_CATEGORIES.intersection(p.get('categories',[]))]
    by_person={}
    for r in roles:by_person.setdefault(token(r['actress']),[]).append(r)
    selected=[]
    for p in tv:
        credits=by_person.get(token(p['name']),[])
        if wanted not in token(p['name']) and not any(wanted in token(r.get('production','')) for r in credits) and not any(wanted in token(t) for t in p.get('credits',[])):continue
        selected.append({'name':p['name'],'categories':p['categories'],'credits':credits[:60]})
        if len(selected)>=100:break
    return selected

class TelevisionResearch(BaseModel):
    name:str=Field(min_length=2,max_length=150)
    station:str=Field(default='',max_length=180)

@app.post('/api/television/research')
def television_research(item:TelevisionResearch):
    name=canonical_name(item.name);assert_public_name(name)
    station=item.station.strip()
    if not token(name):raise HTTPException(400,'Enter a public name')
    candidates=[];warnings=[];seen=set()
    try:
        from ddgs import DDGS
        query=' '.join(x for x in ('"'+name.replace('"','')+'"',station,'television news anchor reporter presenter') if x)
        with DDGS(timeout=10) as ddg:
            for row in ddg.text(query,max_results=12):
                url=str(row.get('href') or row.get('url') or '')
                title=str(row.get('title') or '')[:300];snippet=str(row.get('body') or '')[:600]
                if not url.startswith('https://') or url in seen or token(name) not in token(title+' '+snippet):continue
                # Search snippets are leads, never proof of identity or employment.
                seen.add(url);candidates.append({'url':url[:2000],'title':title,'snippet':snippet})
    except Exception as exc:warnings.append('Public web search unavailable: '+type(exc).__name__)
    role_options=('morning news anchor','evening news anchor','news anchor','news reporter','broadcast journalist','meteorologist','weather presenter','television presenter','television host')
    suggested=''
    for candidate in candidates:
        evidence=(candidate['title']+' '+candidate['snippet']).casefold()
        # Station-specific suggestions require that station to appear in the lead.
        if station and token(station) not in token(evidence):continue
        suggested=next((r.capitalize() for r in role_options if re.search(r'\b'+re.escape(r)+r'\b',evidence)), '')
        if suggested:break
    return {'name':name,'station':station,'sources':candidates,'suggested_role':suggested,'warnings':warnings}

class TelevisionRegistration(BaseModel):
    name:str=Field(min_length=2,max_length=150)
    station:str=Field(default='',max_length=180)
    role:str=Field(default='',max_length=150)
    confirmed:bool=False

@app.post('/api/television/register')
def register_television(item:TelevisionRegistration):
    name=canonical_name(item.name);assert_public_name(name)
    if not item.confirmed:raise HTTPException(400,'Confirm the public identity first')
    if not token(name):raise HTTPException(400,'Enter a public name')
    station=canonical_production(item.station);role=item.role.strip()
    if role and not station:raise HTTPException(400,'Enter a station or program for the role')
    # Explicit confirmation is required for station/role. Preserve previous categories.
    people,_=normalized_catalog(discovery=True)
    existing=next((p.get('categories',[]) for p in people if token(p['name'])==token(name)),[])
    with lock,connect() as db:
        cats=list(dict.fromkeys([*existing,'TV personality']))
        db.execute('INSERT OR REPLACE INTO profile_categories(name,categories) VALUES (?,?)',(name,json.dumps(cats)))
        if station and role:
            entry={'production':station,'actress':name,'character':role,'year':None,'source':'user-confirmed broadcast credit'}
            db.execute('INSERT OR IGNORE INTO productions(key,name,year,kind) VALUES (?,?,?,?)',(token(station),station,None,'other'))
            db.execute('INSERT OR IGNORE INTO production_cast(key,payload) VALUES (?,?)',(canonical_role_key(name,role,station),json.dumps(entry)))
    return {'name':name,'station':station,'role':role,'saved':True}

class PublicPersonRequest(BaseModel):
    name:str=Field(min_length=1,max_length=150)

@app.get('/api/people/library')
def people_library():
    people,roles=normalized_catalog(discovery=True)
    return {'people':people,'roles':roles}

@app.post('/api/people/library')
def add_public_person(item:PublicPersonRequest):
    name=canonical_name(' '.join(item.name.split()))
    if not any(c.isalpha() for c in name) or any(ord(c)<32 or ord(c)==127 for c in item.name):
        raise HTTPException(400,'Enter a valid performer name')
    with lock:
        assert_public_name(name)
        people,_=normalized_catalog(discovery=True)
        existing=next((p for p in people if token(p['name'])==token(name)),None)
        # An explicit add must persist even when the identity already exists only
        # in the installed inventory. Do not overwrite any existing classification.
        if existing:name=existing['name']
        with connect() as db:
            registered=any(token(canonical_name(saved))==token(name) for (saved,) in db.execute('SELECT name FROM profile_categories'))
            if not registered:db.execute('INSERT INTO profile_categories(name,categories) VALUES (?,?)',(name,'[]'))
    return {'name':name,'created':existing is None}

@app.get('/api/discovery/people')
def discover_people(q:str=Query(min_length=1,max_length=160)):
    wanted=token(q)
    if not wanted:return []
    people,roles=normalized_catalog(discovery=True)
    role_names={token(r['actress']) for r in roles if wanted in token(r.get('character','')) or wanted in token(r.get('production',''))}
    return [{'name':p['name'],'categories':p.get('categories',[])} for p in people
            if wanted in token(p['name']) or token(p['name']) in role_names][:100]

@app.get('/api/discovery/credits')
def discover_credits(name:str=Query(min_length=2,max_length=160),online:bool=False,model:str='h3_video'):
    assert_public_name(name)
    people,roles=normalized_catalog(discovery=True)
    wanted=token(canonical_name(name))
    rows=[r for r in roles if token(r['actress'])==wanted]
    person=next((p for p in people if token(p['name'])==wanted),{})
    warnings=[]
    if online:
        if wanted in fictional_game_name_keys(include_damaged=True):
            raise HTTPException(400,'Video-game characters cannot be researched as human performers')
        try:
            remote,warnings=fetch_credits(name)
            for r in remote:
                if r.get('production') and r.get('character'):
                    entry={**r,'actress':canonical_name(name)}
                    rows.append(entry)
            with lock,connect() as conn:
                for entry in rows:
                    if not entry.get('production') or not entry.get('character'):continue
                    role_key=canonical_role_key(entry['actress'],entry['character'],entry['production'])
                    conn.execute('INSERT OR IGNORE INTO production_cast(key,payload) VALUES (?,?)',(role_key,json.dumps(entry)))
        except (RuntimeError,ValueError,httpx.HTTPError) as exc:warnings.append(str(exc))
    dedup={canonical_role_key(r['actress'],r.get('character',''),r['production']):r for r in rows}
    return {'name':name,'credits':production_coverage('',list(dedup.values()),model),
            'known_titles':person.get('credits',[]),'warnings':warnings}

@app.post('/api/productions')
def add_production(item:ProductionRequest):
    name=canonical_production(item.name)
    if not token(name):raise HTTPException(400,'Enter a valid production title')
    if item.year is not None and not 1880<=item.year<=2100:raise HTTPException(400,'Invalid release year')
    if item.kind not in ('series','film','other'):raise HTTPException(400,'Invalid production type')
    with lock,connect() as db:
        db.execute('INSERT OR REPLACE INTO productions(key,name,year,kind) VALUES (?,?,?,?)',(token(name),name,item.year,item.kind))
    return {'saved':True,'name':name}

@app.post('/api/productions/cast')
def add_production_cast(item:CastRequest):
    assert_public_name(item.actress)
    name=canonical_production(item.production)
    if not token(name) or not token(canonical_name(item.actress)):raise HTTPException(400,'Enter a valid production title and performer name')
    if item.year is not None and not 1880<=item.year<=2100:raise HTTPException(400,'Invalid release year')
    entry={'production':name,'actress':canonical_name(item.actress),'character':item.character,'year':item.year,'image':item.image if item.image.startswith('https://') else '', 'image_source':'character' if item.image.startswith('https://') else ''}
    key=canonical_role_key(entry['actress'],entry['character'],name)
    with lock,connect() as db:
        db.execute('INSERT OR IGNORE INTO productions(key,name,year,kind) VALUES(?,?,?,?)',(token(name),name,item.year,'other'))
        db.execute('INSERT OR REPLACE INTO production_cast(key,payload) VALUES(?,?)',(key,json.dumps(entry)))
    return {'saved':True,**entry}

@app.get('/api/productions/cast')
def get_production_cast(production:str=Query(min_length=2,max_length=180),model:str='h3_video'):
    wanted=token(canonical_production(production))
    _,allroles=normalized_catalog(discovery=True)
    entries=[r for r in allroles if token(canonical_production(r.get('production','')))==wanted]
    # normalized_catalog already includes custom roles and excludes private profiles.
    dedup={}
    for entry in entries:
        k=token(entry['actress'])+'|'+token(entry.get('character',''))
        dedup[k]=entry
    for k,entry in list(dedup.items()):
        numbered=re.fullmatch(r'(.+?)\s+([2-9]|[1-9][0-9])',str(entry.get('character') or '').strip())
        if numbered and (token(entry['actress'])+'|'+token(numbered.group(1))) in dedup:
            dedup.pop(k,None)
    missing=production_credit_candidates(production,{token(entry['actress']) for entry in dedup.values()})
    cast=production_coverage(production,list(dedup.values()),model)
    # Read only locally collected, approved and available photos. Never trigger research.
    people={token(canonical_name(r['actress'])) for r in cast}
    counts={}
    if people:
        with connect() as db:
            rows=db.execute("SELECT person,production,character,filename FROM reference_images WHERE quality_status IN ('passed','reviewed')").fetchall()
        private=personal_name_keys()
        for name,prod,char,file in rows:
            who=token(canonical_name(name))
            if who not in people or who in private:continue
            pk=token(canonical_production(prod)) if prod else ''
            if pk not in ('',wanted):continue
            if not reference_file_exists(file):continue
            k=(who,pk,token(char) if pk else '')
            counts[k]=counts.get(k,0)+1
    for role in cast:
        who=token(canonical_name(role['actress']))
        char=token(role.get('character') or '')
        role['reference_counts']={'performer':counts.get((who,'',''),0),
                                  'character':counts.get((who,wanted,char),0) if char else 0}
    return {'production':production,'cast':cast,
            'unmapped_credits':missing,'unmapped_count':len(missing)}

class ProductionCreditRefresh(BaseModel):
    production:str=Field(min_length=2,max_length=180)
    force:bool=False

@app.post('/api/productions/credits/refresh')
def refresh_production_credits(item:ProductionCreditRefresh):
    """Prioritize only public installed cast leads; no private-profile lookups.

    This never generates a character from a bare title. Existing records and
    manually curated roles remain intact regardless of provider failures.
    """
    name=canonical_production(item.production)
    pending=production_credit_candidates(name)[:25]
    if not pending:return {'scheduled':0,'pending':0,'reason':'No unmapped installed performers for this title'}
    with connect() as db:
        checks={k:(ts,status) for k,ts,status in db.execute('SELECT name_key,checked,status FROM credit_refresh')}
    now=int(time.time())
    due=[person for person in pending if item.force or token(person) not in checks or
         now-checks[token(person)][0]>(7*86400 if checks[token(person)][1]=='ok' else 12*3600)]
    if not due:return {'scheduled':0,'pending':len(pending),
                       'reason':'Recently checked. Use Refresh missing roles to retry.'}
    with CREDIT_LOCK:running=CREDIT_STATE['running']
    if running:
        for person in reversed(due):prioritize_credit_refresh(person)
        return {'scheduled':len(due),'pending':len(pending),'reason':'Prioritized during ongoing role sync'}
    started=launch_credit_sync(due)
    return {'scheduled':len(due) if started else 0,'pending':len(pending),
            'reason':'Finding verified role names' if started else 'Role sync busy'}

@app.get('/api/productions/lookup')
def search_production_online(q:str=Query(min_length=2,max_length=120)):
    # TVMaze is a public series index, not a comprehensive film database.
    try:
        with httpx.Client(timeout=12,trust_env=False) as client:
            r=client.get('https://api.tvmaze.com/search/shows',params={'q':q})
            r.raise_for_status()
            data=r.json()[:12]
        return {'provider':'TVMaze','shows':[{'id':it['show']['id'],'name':it['show']['name'],'year':int(it['show']['premiered'][:4]) if it['show'].get('premiered') else None} for it in data]}
    except Exception as e:
        raise HTTPException(502,'TV series lookup unavailable: '+type(e).__name__)

# Key-free film credit source. Match exact title or explicit "(film)" titles;
# treat cast lists as suggestions for human review, not verified installed mods.
WIKIPEDIA_API='https://en.wikipedia.org/w/api.php'
WIKI_AGENT='CastingStudio/1.0.0-rc.12.20 (personal local catalog; Wikimedia public credits)'
def wiki_api(client,params):
    r=client.get(WIKIPEDIA_API,params={**params,'format':'json','formatversion':2},headers={'User-Agent':WIKI_AGENT})
    r.raise_for_status();return r.json()

def film_cast_lookup(title):
    exact=canonical_production(title)
    with httpx.Client(timeout=16,trust_env=False,follow_redirects=True) as client:
        queries=[exact,exact+' (film)']
        page=None
        for query in queries:
            result=wiki_api(client,{'action':'query','titles':query,'redirects':1,'prop':'pageimages','pithumbsize':350})
            pages=result.get('query',{}).get('pages',[])
            if pages and not pages[0].get('missing'):
                candidate=pages[0]
                # Explicit film-title/parenthetical match; only exact title normalization.
                if token(re.sub(r'\s*\([^)]*\)$','',candidate.get('title','')))==token(exact):
                    page=candidate;break
        if not page:return {'cast':[],'source':'Wikipedia film credits','note':'No exact film title found on Wikipedia. Add cast manually or supply a more specific title.','artwork':''}
        page_title=page['title']
        sections=wiki_api(client,{'action':'parse','page':page_title,'prop':'sections'}).get('parse',{}).get('sections',[])
        section=next((x for x in sections if re.search(r'^(cast|cast and characters|voice cast)$',re.sub('<[^>]+>','',x.get('line','')).strip(),re.I)),None)
        if not section:return {'cast':[],'source':'Wikipedia film credits','note':'No identifiable Cast section on the film article. You can add credits manually.','artwork':page.get('thumbnail',{}).get('source','')}
        parsed=wiki_api(client,{'action':'parse','page':page_title,'prop':'text','section':section['index']})
        content=parsed.get('parse',{}).get('text','')
        soup=BeautifulSoup(content,'html.parser')
        # Keep only list items; credits in prose or complex multi-column tables are intentionally not guessed.
        found=[];seen=set()
        for li in soup.select('li')[:250]:
            raw=' '.join(li.stripped_strings)
            raw=re.sub(r'\[\d+\]','',raw).strip()
            match=re.match(r'^(.{3,80}?)\s+(?:as|portrays|voices)\s+(.{2,110}?)(?:[.;]|$)',raw,re.I)
            if not match:continue
            actor=re.sub(r'\s*\([^)]*\)$','',match.group(1)).strip()
            character=re.sub(r'\s*\([^)]*\)$','',match.group(2)).strip()
            if not (2<=len(actor)<=80 and 2<=len(character)<=110):continue
            key=token(actor)+'|'+token(character)
            if key in seen:continue
            seen.add(key)
            found.append({'actress':canonical_name(actor),'character':character,'image':'','source':'Wikipedia'})
        return {'cast':found,'source':'Wikipedia film credits','matched_show':page_title,
                'note':'' if found else 'The film article has a Cast section but its format was not readable automatically. Add cast manually.',
                'artwork':page.get('thumbnail',{}).get('source','')}

@app.get('/api/productions/artwork')
def production_artwork(name:str=Query(min_length=2,max_length=180),refresh:bool=False):
    name=canonical_production(name)
    key=token(name)
    with connect() as db:
        selected=db.execute('SELECT url FROM images WHERE key=?',('production|'+key,)).fetchone()
        cached=db.execute('SELECT url,checked FROM production_artwork WHERE name_key=?',(key,)).fetchone()
        meta=db.execute('SELECT year,kind FROM productions WHERE key=?',(key,)).fetchone()
    # Never let a remote lookup replace a manually selected cover.
    if selected and selected[0]:return {'image':local_photo_url(selected[0]),'source':'Manual selection'}
    if (not refresh and cached and isinstance(cached[1],(int,float)) and 0<=time.time()-cached[1]<(30*86400 if cached[0] else 86400)
            and isinstance(cached[0],str) and (not cached[0] or cached[0].startswith('https://'))):
        return {'image':cached[0],'source':'cached artwork' if cached[0] else 'Not available'}
    year=(meta[0] if meta else None)
    kind=(meta[1] if meta else '')
    url='';source='Not available'
    # TVMaze has a production-specific official show poster; exact title and
    # matching premiere year prevent misleading similarly named series.
    if kind!='film':
        try:
            with httpx.Client(timeout=10,trust_env=False,follow_redirects=True) as client:
                resp=client.get('https://api.tvmaze.com/search/shows',params={'q':name})
                resp.raise_for_status()
                shows=[x.get('show') or {} for x in resp.json()]
                exact=[x for x in shows if token(x.get('name',''))==key]
                if year is not None:
                    exact=[x for x in exact if str(x.get('premiered') or '').startswith(str(year))]
                if len(exact)==1:
                    image=exact[0].get('image') or {}
                    candidate=image.get('original') or image.get('medium') or ''
                    if isinstance(candidate,str) and candidate.startswith('https://'):
                        url=candidate;source='TVMaze series poster'
        except (httpx.HTTPError,ValueError,TypeError,KeyError):pass
    if not url:
        variants=[name]
        if year:
            if kind=='film':variants.extend([f'{name} ({year} film)',f'{name} (film)'])
            else:variants.extend([f'{name} ({year} TV series)',f'{name} (TV series)'])
        else:variants.extend([f'{name} (TV series)',f'{name} (film)'])
        try:
            with httpx.Client(timeout=10,trust_env=False,follow_redirects=True) as client:
                for title in dict.fromkeys(variants):
                    result=wiki_api(client,{'action':'query','titles':title,'redirects':1,'prop':'pageimages','pithumbsize':350})
                    pages=result.get('query',{}).get('pages',[])
                    if pages and not pages[0].get('missing'):
                        page=pages[0]
                        if token(re.sub(r'\s*\([^)]*\)$','',page.get('title','')))!=key:continue
                        candidate=page.get('thumbnail',{}).get('source','')
                        if candidate.startswith('https://'):
                            url=candidate;source='Wikimedia';break
        except (httpx.HTTPError,ValueError,TypeError,KeyError):pass
    with lock,connect() as db:
        db.execute('INSERT OR REPLACE INTO production_artwork(name_key,url,checked) VALUES (?,?,?)',(key,url,int(time.time())))
        selected=db.execute('SELECT url FROM images WHERE key=?',('production|'+key,)).fetchone()
    if selected and selected[0]:return {'image':local_photo_url(selected[0]),'source':'Manual selection'}
    return {'image':url,'source':source}

# v6.5: TV-series cast suggestions for a visual, multi-select picker.
# The production title must match exactly before any TVMaze cast is offered as a candidate.
CAST_SUGGEST_CACHE={}
CAST_SUGGEST_LOCK=threading.Lock()
@app.get('/api/productions/cast-suggestions')
def production_cast_suggestions(production:str=Query(min_length=2,max_length=180)):
    target=canonical_production(production)
    cache_key=token(target)
    with CAST_SUGGEST_LOCK:
        prior=CAST_SUGGEST_CACHE.get(cache_key)
    if prior and time.time()-prior[0]<1800:
        source=prior[1]
    else:
        source={'source':'TVMaze','matched_show':None,'cast':[], 'note':''}
        try:
            with httpx.Client(timeout=15,trust_env=False) as client:
                found=client.get('https://api.tvmaze.com/search/shows',params={'q':target})
                found.raise_for_status()
                exact=[x['show'] for x in found.json() if token(x.get('show',{}).get('name',''))==cache_key]
                if exact:
                    show=exact[0]
                    response=client.get(f"https://api.tvmaze.com/shows/{int(show['id'])}/cast")
                    response.raise_for_status()
                    source['matched_show']=show['name']
                    for item in response.json():
                        person=item.get('person') or {}
                        character=item.get('character') or {}
                        name=str(person.get('name') or '').strip()
                        if not name:continue
                        name=canonical_name(name)
                        role=str(character.get('name') or '').strip()
                        photo=((character.get('image') or {}).get('medium') or '')
                        if not isinstance(photo,str) or not photo.startswith('https://'):photo=''
                        source['cast'].append({'actress':name,'character':role,'image':photo,'image_source':'character' if photo else ''})
                else:
                    source['note']='No exact TVMaze series match. Add a performer manually or select another production.'
        except Exception:
            source['note']='Cast lookup is temporarily unavailable. Manual entry remains available.'
        if not source['cast'] and not source['matched_show']:
            try:
                movie=film_cast_lookup(target)
                if movie['cast']:
                    source.update(movie)
                elif not source['note'] or 'No exact' in source['note']:
                    source['note']=movie.get('note') or source['note']
            except (httpx.HTTPError,ValueError,KeyError) as ex:
                source['note']='Film lookup unavailable ('+type(ex).__name__+'); manual entry remains available.'
        with CAST_SUGGEST_LOCK:CAST_SUGGEST_CACHE[cache_key]=(time.time(),source)
    existing=get_production_cast(production)['cast']
    existing_keys={canonical_role_key(it['actress'],it.get('character',''),production) for it in existing}
    installed={token(canonical_name(model['name'])):model['path'] for model in scan()}
    candidates=[];seen=set()
    for item in source['cast']:
        k=canonical_role_key(item['actress'],item['character'],production)
        if k in seen:continue
        seen.add(k)
        candidates.append({**item,'id':k,'already_added':k in existing_keys,
                           'installed':token(canonical_name(item['actress'])) in installed})
    return {'production':production,'source':source['source'],
            'matched_show':source['matched_show'],'note':source['note'],
            'candidates':candidates}

class CastBulkRequest(BaseModel):
    production:str=Field(min_length=2,max_length=180)
    members:list[CastRequest]=Field(min_length=1,max_length=250)

@app.post('/api/productions/cast/bulk')
def add_production_cast_bulk(payload:CastBulkRequest):
    production=canonical_production(payload.production)
    values=[]
    for member in payload.members:
        if token(canonical_production(member.production))!=token(production):
            raise HTTPException(400,'All cast members must belong to the current production')
        person=canonical_name(member.actress)
        role=member.character.strip()
        key=canonical_role_key(person,role,production)
        entry={'production':production,'actress':person,'character':role,'year':member.year,'image':member.image if member.image.startswith('https://') else '', 'image_source':'character' if member.image.startswith('https://') else ''}
        values.append((key,json.dumps(entry)))
    with lock,connect() as db:
        db.execute('INSERT OR IGNORE INTO productions(key,name,year,kind) VALUES(?,?,?,?)',
                   (token(production),production,None,'other'))
        db.executemany('INSERT OR REPLACE INTO production_cast(key,payload) VALUES(?,?)',values)
    return {'saved':len(values),'production':production}

@app.post('/api/productions/import-tvmaze/{show_id}')
def import_tvmaze(show_id:int):
    if show_id<1:raise HTTPException(400,'Invalid series ID')
    try:
        with httpx.Client(timeout=16,trust_env=False) as client:
            show=client.get(f'https://api.tvmaze.com/shows/{show_id}')
            cast=client.get(f'https://api.tvmaze.com/shows/{show_id}/cast')
            show.raise_for_status();cast.raise_for_status()
            info=show.json();roles=cast.json()
    except Exception as e:
        raise HTTPException(502,'TVMaze cast lookup unavailable: '+type(e).__name__)
    name=canonical_production(info['name']); year=int(info['premiered'][:4]) if info.get('premiered') else None
    with lock,connect() as db:
        db.execute('INSERT OR REPLACE INTO productions(key,name,year,kind) VALUES(?,?,?,?)',(token(name),name,year,'series'))
        for role in roles:
            actress=role.get('person',{}).get('name','').strip()
            char=role.get('character',{}).get('name','').strip()
            if not actress:continue
            entry={'production':name,'actress':actress,'character':char,'year':year,'image':((role.get('character') or {}).get('image') or {}).get('medium',''), 'image_source':'character' if (role.get('character') or {}).get('image') else ''}
            key=canonical_role_key(actress,char,name)
            db.execute('INSERT OR IGNORE INTO production_cast(key,payload) VALUES(?,?)',(key,json.dumps(entry)))
    return get_production_cast(name)

REFERENCE_DIR=external_data_path(DATA/'reference_images')
REFERENCE_DIR.mkdir(parents=True,exist_ok=True)

# Technical image QA is not a guarantee of a correct person's identity. A face detector
# can miss profiles, prosthetics or unusual makeup. Those cases require human review.
def image_fingerprint(image):
    gray=image.convert('L').resize((9,8),Image.Resampling.LANCZOS)
    px=list(gray.getdata())
    value=0
    for y in range(8):
        for x in range(8):value=(value<<1)|int(px[y*9+x]>px[y*9+x+1])
    return f'{value:016x}'

def analyze_reference_image(image):
    import numpy as np
    import cv2
    w,h=image.size;hard=[];review=[]
    if min(w,h)<600 or w*h<500_000:hard.append('Source resolution is too small (minimum 600px on shortest side and 0.5 megapixels)')
    if w*h>40_000_000:hard.append('Source exceeds 40 megapixels')
    if max(w,h)/max(1,min(w,h))>2.5:hard.append('Extreme panoramic crop')
    thumb=image.convert('RGB');thumb.thumbnail((1200,1200),Image.Resampling.LANCZOS)
    gray=cv2.cvtColor(np.asarray(thumb),cv2.COLOR_RGB2GRAY)
    blur=float(cv2.Laplacian(gray,cv2.CV_64F).var())
    if blur<24:hard.append('Image appears heavily blurred or lacks fine detail')
    if float(gray.mean())<28 or float(gray.mean())>238:hard.append('Image is severely underexposed or overexposed')
    if float(gray.std())<18:hard.append('Image has too little visible contrast or detail')
    cascade=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    faces=cascade.detectMultiScale(gray,scaleFactor=1.13,minNeighbors=5,minSize=(45,45)) if not cascade.empty() else []
    fc=len(faces)
    if fc==0:review.append('A clear face was not automatically detected; confirm the correct performer and usable face detail')
    elif fc>1:review.append(f'{fc} faces detected; confirm only the intended performer is present')
    elif max(faces[0][2],faces[0][3])<85:review.append('Detected face is small in the frame')
    return {'width':w,'height':h,'sharpness':round(blur,2),'face_count':fc,'fingerprint':image_fingerprint(image),
            'hard_reasons':hard,'review_reasons':review}

def hash_distance(a,b):
    try:return (int(a,16)^int(b,16)).bit_count()
    except (ValueError,TypeError):return 65

class ReferenceImageRequest(BaseModel):
    person:str=Field(min_length=2,max_length=150)
    production:str=Field(default='',max_length=180)
    character:str=Field(default='',max_length=150)
    image_url:str=Field(min_length=10,max_length=2000)
    source_page:str=Field(default='',max_length=2000)
    accept_review:bool=False

def safe_media_file(folder,filename,pattern=None):
    if not isinstance(filename,str) or not filename or '\x00' in filename or Path(filename).name!=filename or '/' in filename or '\\' in filename:return None
    if pattern and not re.fullmatch(pattern,filename):return None
    try:
        path=folder/filename
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(folder.resolve()):return None
        return path
    except (OSError,ValueError,RuntimeError):return None


def reference_file_exists(filename):
    return safe_media_file(REFERENCE_DIR,filename) is not None


def compatible_reference_year(requested, stored):
    # Legacy undated references remain eligible for manual confirmation, but
    # explicitly different adaptations must not collide or be audited together.
    def year(value):
        match=re.search(r'\b((?:18|19|20)\d{2})\)?\s*$',value or '')
        return match.group(1) if match else None
    a,b=year(requested),year(stored)
    return not (a and b and a!=b)


def same_reference_collection(person,production,character=None):
    # Normalize aliases, case and a trailing production year consistently with casting.
    wanted=(token(canonical_name(person)),token(canonical_production(production)))
    with connect() as db:
        rows=db.execute('SELECT id,person,production,source_url,filename,width,height,quality_status,perceptual_hash,character FROM reference_images').fetchall()
    return [r for r in rows if (token(canonical_name(r[1])),token(canonical_production(r[2])))==wanted and (character is None or token(r[9])==token(character)) and compatible_reference_year(production,r[2])]


def existing_reference_response(row):
    return {'saved':True,'duplicate':True,'id':row[0],'width':row[5],'height':row[6],
            'quality_status':row[7]}


def save_reference_pixels(image,person,production,character,source_url,page_url,accept_review):
    image=ImageOps.exif_transpose(image)
    analysis=analyze_reference_image(image)
    if analysis['hard_reasons']:
        raise HTTPException(422,{'status':'rejected','reasons':analysis['hard_reasons']})
    with lock:
        assert_public_name(person)
        rows=same_reference_collection(person,production,character)
        # Exact URL and near-duplicate checks only block within this collection,
        # and only when the existing file actually exists and can be used.
        for row in rows:
            if not reference_file_exists(row[4]) or row[7] not in ('passed','reviewed','review','pending'):continue
            exact=bool(source_url and row[3]==source_url)
            near=bool(row[8] and hash_distance(analysis['fingerprint'],row[8])<=5)
            if exact or near:
                return existing_reference_response(row)
        if analysis['review_reasons'] and not accept_review:
            raise HTTPException(409,{'status':'review','reasons':analysis['review_reasons']})
        missing=next((row for row in rows if not reference_file_exists(row[4]) and ((source_url and row[3]==source_url) or (row[8] and hash_distance(analysis['fingerprint'],row[8])<=5))),None)
        image_id=missing[0] if missing else uuid.uuid4().hex[:24]
        filename=uuid.uuid4().hex[:24]+'.jpg';tmp=REFERENCE_DIR/(filename+'.tmp')
        status='reviewed' if analysis['review_reasons'] else 'passed'
        notes='; '.join(analysis['review_reasons'])
        created=False;published=False
        try:
            with tmp.open('xb') as stream:
                created=True
                image.convert('RGB').save(stream,format='JPEG',quality=95,subsampling=0)
            tmp.replace(REFERENCE_DIR/filename);published=True
            with connect() as db:
                db.execute('INSERT OR REPLACE INTO reference_images (id,person,production,character,source_url,page_url,filename,width,height,quality_status,quality_notes,perceptual_hash,sharpness,face_count) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (image_id,person,production,character,source_url or 'local-upload:'+image_id,page_url,filename,analysis['width'],analysis['height'],status,notes,analysis['fingerprint'],analysis['sharpness'],analysis['face_count']))
        except (OSError,sqlite3.Error) as exc:
            if created:tmp.unlink(missing_ok=True)
            if published:(REFERENCE_DIR/filename).unlink(missing_ok=True)
            raise HTTPException(503,'Could not save reference image. Existing collection retained.') from exc
        return {'saved':True,'id':image_id,'width':analysis['width'],'height':analysis['height'],'sharpness':analysis['sharpness'],'face_count':analysis['face_count'],'quality_status':status,'quality_notes':notes}


@app.post('/api/reference-images')
def save_reference_image(item:ReferenceImageRequest):
    assert_public_name(item.person)
    for row in same_reference_collection(item.person,item.production,item.character):
        if row[3]==item.image_url and reference_file_exists(row[4]) and row[7] in ('passed','reviewed','review','pending'):
            return existing_reference_response(row)
    try:
        with connect() as db:
            previous=db.execute("SELECT person,filename FROM reference_images WHERE source_url=? AND quality_status IN ('passed','reviewed')",(item.image_url,)).fetchall()
        for person,filename in previous:
            if token(canonical_name(person))!=token(canonical_name(item.person)) or not reference_file_exists(filename):continue
            try:
                with Image.open(REFERENCE_DIR/filename) as existing:rgb=existing.convert('RGB')
            except (OSError,ValueError):continue
            result=save_reference_pixels(rgb,item.person,item.production,item.character,item.image_url,item.source_page,item.accept_review)
            return {**result,'reused_local':True}
        try:validate_public_url(item.image_url)
        except Exception as e:raise HTTPException(400,str(e))
        with httpx.Client(timeout=20,follow_redirects=False,trust_env=False,headers={'User-Agent':'CastingStudio/1.0.0-rc.12.20'}) as client:
            with client.stream('GET',item.image_url) as r:
                if r.status_code!=200 or not r.headers.get('content-type','').lower().startswith('image/'):
                    raise HTTPException(422,'Image host did not return an image')
                if int(r.headers.get('content-length') or 0)>15_000_000:raise HTTPException(413,'Image exceeds 15 MB limit')
                buffer=io.BytesIO()
                for chunk in r.iter_bytes():
                    if buffer.tell()+len(chunk)>15_000_000:raise HTTPException(413,'Image exceeds 15 MB limit')
                    buffer.write(chunk)
        buffer.seek(0)
        with Image.open(buffer) as img:
            if img.width*img.height>40_000_000:raise HTTPException(422,'Source exceeds 40 megapixels')
            return save_reference_pixels(img,item.person,item.production,item.character,item.image_url,item.source_page,item.accept_review)
    except HTTPException:raise
    except Exception as e:raise HTTPException(422,'Image could not be retrieved: '+type(e).__name__)

async def read_local_image_upload(request:Request,max_bytes:int=15_000_000):
    if request.headers.get('content-type','').split(';')[0].lower() not in ('image/jpeg','image/png','image/webp'):
        raise HTTPException(415,'Upload a JPEG, PNG, or WebP image')
    try:declared=int(request.headers.get('content-length') or 0)
    except ValueError:raise HTTPException(400,'Invalid upload length')
    if declared<0:raise HTTPException(400,'Invalid upload length')
    if declared>max_bytes:raise HTTPException(413,'Image exceeds upload size limit')
    raw=bytearray()
    async for part in request.stream():
        if len(raw)+len(part)>max_bytes:raise HTTPException(413,'Image exceeds upload size limit')
        raw.extend(part)
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in ('JPEG','PNG','WEBP') or image.width*image.height>40_000_000:
                raise HTTPException(422,'Unsupported image type or dimensions')
            rgb=ImageOps.exif_transpose(image).convert('RGB')
        return rgb
    except HTTPException:raise
    except (OSError,UnidentifiedImageError,ValueError,Image.DecompressionBombError):
        raise HTTPException(422,'Uploaded file is not a readable image')

@app.post('/api/reference-images/upload')
async def upload_reference_image(request:Request,person:str=Query(min_length=2,max_length=150),
                                 production:str='',character:str='',accept_review:bool=False):
    assert_public_name(person)
    image=await read_local_image_upload(request)
    return await run_in_threadpool(save_reference_pixels,image,person,production,character,'','',accept_review)

def stale_temporary_files():
    cutoff=time.time()-24*3600
    roots=((DATA,re.compile(r'^(?:local_paths\.json|catalog_last_scan|workshop_last_scan|local_paths)(?:\.[a-f0-9]{32})?\.tmp$')),
           (PHOTO_DIR,re.compile(r'^[a-f0-9]{64}\.jpg(?:\.[a-f0-9]{32})?\.tmp$')),
           (REFERENCE_DIR,re.compile(r'^[a-f0-9]{24}\.jpg\.tmp$')))
    for folder,pattern in roots:
        if not folder.is_dir() or folder.resolve().is_relative_to(ROOT.parent.resolve()):continue
        for path in folder.iterdir():
            if not pattern.fullmatch(path.name) or path.is_symlink() or not path.is_file():continue
            try:
                st=path.stat()
                if st.st_mtime<cutoff and path.resolve().parent==folder.resolve():yield path,st.st_size
            except OSError:continue

@app.get('/api/settings/temporary-files')
def temporary_files_status():
    files=list(stale_temporary_files())
    return {'count':len(files),'bytes':sum(size for _,size in files),'minimum_age_hours':24}

@app.post('/api/settings/temporary-files/cleanup')
def cleanup_temporary_files():
    count=total=failed=0
    with lock:
        for path,size in stale_temporary_files():
            try:path.unlink();count+=1;total+=size
            except OSError:failed+=1
    return {'removed':count,'bytes':total,'failed':failed}

@app.post('/api/images/upload')
async def upload_selected_photo(request:Request,key:str=Query(min_length=4,max_length=500)):
    key=canonical_photo_key(key)
    image=await read_local_image_upload(request,8_000_000)
    if image.width<80 or image.height<80:raise HTTPException(422,'Picture is too small')
    image.thumbnail((1400,1400),Image.Resampling.LANCZOS)
    filename=hashlib.sha256(uuid.uuid4().bytes).hexdigest()+'.jpg'
    tmp=PHOTO_DIR/(filename+'.tmp')
    value='api/photos/'+filename
    dest=PHOTO_DIR/filename
    with lock:
        created=False;published=False
        try:
            with tmp.open('xb') as stream:
                created=True
                image.save(stream,format='JPEG',quality=91)
            tmp.replace(dest);published=True
            with connect() as db:
                db.execute('INSERT OR REPLACE INTO images(key,url) VALUES (?,?)',(key,value))
        except (OSError,sqlite3.Error) as exc:
            if created:tmp.unlink(missing_ok=True)
            if published:dest.unlink(missing_ok=True)
            raise HTTPException(503,'Could not save artwork. Previous artwork retained.') from exc
    return {'saved':True,'url':value,'key':key}

@app.get('/api/reference-images')
def list_reference_images(person:str=Query(min_length=2),production:str='',character:str|None=None):
    cols=('id','person','production','character','source_url','page_url','filename','width','height','quality_status','quality_notes','perceptual_hash','sharpness','face_count')
    assert_public_name(person)
    wanted=(token(canonical_name(person)),token(canonical_production(production)))
    with connect() as db:
        rows=db.execute('SELECT '+','.join(cols)+' FROM reference_images').fetchall()
    result=[]
    for r in rows:
        if (token(canonical_name(r[1])),token(canonical_production(r[2])))!=wanted or (character is not None and token(r[3])!=token(character)) or not compatible_reference_year(production,r[2]):continue
        item=dict(zip(cols,r))
        if not reference_file_exists(item['filename']):item.update(quality_status='missing',quality_notes='Saved image file missing; add it again or remove this record.')
        result.append(item)
    return rank_reference_photos(result)

@app.post('/api/reference-images/audit')
def audit_reference_images(person:str=Query(min_length=2),production:str='',character:str|None=None):
    """Re-score existing files. Never delete previously collected images automatically."""
    rows=list_reference_images(person,production,character)
    counts={'passed':0,'review':0,'rejected':0,'missing':0,'duplicates':0,'changed':0}
    prior=[]
    for r in rows:
        duplicate=False
        file=safe_media_file(REFERENCE_DIR,r['filename'])
        if not file:
            status='missing';notes='Saved file not found';a=None
        else:
            try:
                with Image.open(file) as im:a=analyze_reference_image(im)
                reasons=list(a['hard_reasons']+a['review_reasons'])
                if a['hard_reasons']:
                    status='rejected'
                elif any(hash_distance(a['fingerprint'],ph)<=5 for ph in prior):
                    reasons.append('Near-duplicate of another collected image');duplicate=True
                    status='review'
                else:
                    status='rejected' if a['hard_reasons'] else ('review' if a['review_reasons'] else 'passed')
                notes='; '.join(reasons)
            except Exception:
                status='rejected';notes='Saved image unreadable';a=None
        with lock,connect() as db:
            # A repaired reference can retain its ID but receive a new filename.
            # Do not write a stale score over that new file or a removed record.
            assert_public_name(person)
            changed=db.execute('UPDATE reference_images SET quality_status=?,quality_notes=?,perceptual_hash=?,sharpness=?,face_count=? WHERE id=? AND filename=?',
                       (status,notes,a['fingerprint'] if a else '',a['sharpness'] if a else 0,a['face_count'] if a else -1,r['id'],r['filename'])).rowcount
        if not changed:
            counts['changed']+=1
            continue
        counts[status]+=1
        if duplicate:counts['duplicates']+=1
        if status=='passed' and a:prior.append(a['fingerprint'])
    return {'audited':len(rows),'counts':counts,'images':list_reference_images(person,production,character)}

class ReferenceReviewAction(BaseModel):
    approved:bool

@app.put('/api/reference-images/{image_id}/review')
def set_reference_review(image_id:str, action:ReferenceReviewAction):
    with lock,connect() as db:
        row=db.execute('SELECT quality_status,quality_notes,filename,person FROM reference_images WHERE id=?',(image_id,)).fetchone()
        if not row:raise HTTPException(404,'Reference not found')
        assert_public_name(row[3])
        if row[0] not in ('review','passed','reviewed') or not reference_file_exists(row[2]):
            raise HTTPException(422,'Run the image audit first; failed or unscanned images cannot be approved')
        db.execute('UPDATE reference_images SET quality_status=? WHERE id=?',('reviewed' if action.approved else 'review',image_id))
    return {'saved':True}

@app.get('/api/reference-images/file/{image_id}')
def serve_reference_image(image_id:str):
    with connect() as db:
        row=db.execute('SELECT filename,person FROM reference_images WHERE id=?',(image_id,)).fetchone()
    if not row:raise HTTPException(404,'Reference not found')
    assert_public_name(row[1])
    filename=row[0]
    if not reference_file_exists(filename):raise HTTPException(404,'Local reference file missing')
    file=REFERENCE_DIR/filename
    return FileResponse(file,media_type='image/jpeg',headers={'Cache-Control':'private, no-store'})

@app.delete('/api/reference-images/{image_id}')
def delete_reference_image(image_id:str):
    with lock:
        with connect() as db:
            row=db.execute('SELECT filename,person FROM reference_images WHERE id=?',(image_id,)).fetchone()
            if not row:raise HTTPException(404,'Image not found')
            assert_public_name(row[1])
            db.execute('DELETE FROM reference_images WHERE id=?',(image_id,))
            shared=db.execute('SELECT 1 FROM reference_images WHERE filename=? LIMIT 1',(row[0],)).fetchone()
        if not shared and reference_file_exists(row[0]):(REFERENCE_DIR/row[0]).unlink(missing_ok=True)
    return {'deleted':True}

@app.get('/api/reference-images/export')
def export_reference_images(person:str=Query(min_length=2),production:str='',character:str|None=None):
    rows=[x for x in list_reference_images(person,production,character) if x['quality_status'] in ('passed','reviewed')]
    if not rows:raise HTTPException(409,'No quality-approved images to export. Audit older images and review flagged files first.')
    if len(rows)>60:raise HTTPException(400,'Limit export to 60 collected images')
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=2) as z:
        manifest=[]
        for idx,item in enumerate(rows,1):
            path=safe_media_file(REFERENCE_DIR,item['filename'])
            if not path:continue
            name=f'{idx:03d}_{item["filename"]}'
            z.write(path,name)
            manifest.append({**item,'export_file':name})
        z.writestr('sources.json',json.dumps(manifest,indent=2,ensure_ascii=False))
    output.seek(0)
    safe=re.sub('[^A-Za-z0-9_-]+','_',person)[:60]
    return StreamingResponse(output,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="{safe}_RefMod_References.zip"'})


# ── RefMod Workshop: public collected photos -> fork H3 Extract / Decompile ──
# Only operations available via the fork's stable extraction job wrapper are
# automated. Never import/mutate the Refmod-Fork installation or existing mods.
try:
    from ..workshop_bridge import WorkshopTask, safe_mod_name, build_extract_spec, read_header, public_workshop_path
except ImportError:
    # Top-level smoke tests have no parent package.
    import sys
    if str(ROOT.parent) not in sys.path:
        sys.path.insert(0, str(ROOT.parent))
    from workshop_bridge import WorkshopTask, safe_mod_name, build_extract_spec, read_header, public_workshop_path


def workshop_relay():
    bridge=getattr(app.state,'casting_queue_bridge',None)
    if bridge is None:raise HTTPException(503,'Workshop generation requires the native WanGP plugin')
    return bridge


def workshop_public_mod_root():
    bridge=workshop_relay()
    return bridge.adapter.refmod_root/'minimax_h3'/'celebs'


def workshop_photo_rows(person=None, production=None, character=None):
    with connect() as db:
        results=db.execute('''SELECT id,person,production,character,filename,width,height,quality_status,sharpness,face_count,perceptual_hash
            FROM reference_images WHERE quality_status IN ('passed','reviewed')
            ORDER BY person COLLATE NOCASE, production COLLATE NOCASE, filename''').fetchall()
    rows=[]
    private=personal_name_keys()
    for row in results:
        id_,name,prod,char,file,w,h,quality,sharp,faces,fingerprint=row
        if token(name) in private:continue
        if person is not None and token(canonical_name(name))!=token(canonical_name(person)):continue
        if production is not None and token(canonical_production(prod))!=token(canonical_production(production)):continue
        if character is not None and token(char)!=token(character):continue
        path=safe_media_file(REFERENCE_DIR,file)
        if path:
            rows.append({'id':id_,'person':name,'production':prod,'character':char,'path':path,
                         'width':w,'height':h,'quality':quality,'sharpness':sharp,'face_count':faces,'perceptual_hash':fingerprint})
    return rows


def rank_reference_photos(rows):
    # Technical ranking, not identity or aesthetic validation. Group by a
    # 64-bit perceptual fingerprint within this collection only.
    import math
    def score(r):
        try:
            sharp=max(0,min(1000,float(r.get('sharpness') or 0)))
            pixels=max(0,min(16_000_000,int(r.get('width') or 0)*int(r.get('height') or 0)))
            if not math.isfinite(sharp):sharp=0
        except (ValueError,TypeError,OverflowError):sharp=pixels=0
        face=r.get('face_count');status=r.get('quality',r.get('quality_status'))
        return (2 if status in ('passed','reviewed') else 1 if status=='review' else 0, 2 if face==1 else 1 if face in (-1,None) else 0, round(math.log1p(sharp)*12+math.log1p(pixels)*3,3))
    ranked=sorted(rows,key=lambda r:(score(r),str(r.get('id',''))),reverse=True)
    groups=[]
    for i,r in enumerate(ranked):
        r['quality_rank']=i+1;r['duplicate_group']=None;r['duplicate_of']=None
        h=r.get('perceptual_hash') or ''
        if not isinstance(h,str) or not re.fullmatch(r'[0-9a-fA-F]{16}',h):continue
        scope=(token(r.get('person','')),token(r.get('production','')),token(r.get('character','')))
        match=next((g for g in groups if g[2]==scope and hash_distance(h,g[0])<=6),None)
        if match:
            r['duplicate_group']=match[1]['id'];r['duplicate_of']=match[1]['id'];match[1]['duplicate_group']=match[1]['id']
        else:groups.append((h,r,scope))
    return ranked


@app.get('/api/workshop/sources')
def workshop_sources(role_aware:bool=False):
    options={}
    for r in workshop_photo_rows():
        key=(r['person'],r['production'],r['character'] if role_aware else None)
        options[key]=options.get(key,0)+1
    return {'sources':[{'person':p,'production':prod,'count':n,**({'character':char} if role_aware else {})} for (p,prod,char),n in
                       sorted(options.items(),key=lambda z:tuple(str(x or '').casefold() for x in z[0]))]}


@app.get('/api/workshop/photos')
def workshop_photos(person:str=Query(min_length=2),production:str='',character:str|None=None):
    rows=rank_reference_photos(workshop_photo_rows(person,production,character))
    return {'photos':[{'id':r['id'],'person':r['person'],'production':r['production'],
                       'character':r['character'],'width':r['width'],'height':r['height'],
                       'quality':r['quality'],'quality_rank':r['quality_rank'],'duplicate_group':r['duplicate_group'],'duplicate_of':r['duplicate_of'],'sharpness':r.get('sharpness',0),'face_count':r.get('face_count',-1),'url':'api/reference-images/file/'+r['id']} for r in rows]}


# Local-only, explicit appearance analysis. Only current saved public casting roles
# and their exact character artwork or approved character photos can be resolved.
def appearance_bridge():
    bridge=getattr(app.state,'casting_vision_bridge',None)
    if bridge is None:raise HTTPException(503,'Open Casting Studio inside a compatible WanGP host.')
    return bridge

def appearance_role(key):
    if key.startswith('catalog:'):
        # Resolve the displayed portrayal from the local catalog, not a fabricated
        # casting choice. No model scan, selection mutation or online research.
        try:
            person,character,production,year=json.loads(key[len('catalog:'):])
            if not all(isinstance(v,str) and v.strip() for v in (person,character,production)) or (year is not None and (type(year) is not int or not 1880<=year<=2100)):raise ValueError()
        except (ValueError,TypeError,RecursionError):raise HTTPException(400,'Invalid catalog portrayal')
        wanted=canonical_role_key(person,character,production)
        _,roles=normalized_catalog(models=[],discovery=True)
        choice=None
        for role in roles:
            if canonical_role_key(role['actress'],role['character'],role['production'])!=wanted:continue
            candidate={**role,'person':role['actress']}
            label=portrayal_production_label(candidate)
            if year is not None and not label.endswith(f'({year})'):continue
            choice=candidate;break
    else:
        with connect() as db:
            row=db.execute('SELECT payload FROM choices WHERE key=?',(key,)).fetchone()
        choice=decoded_choice(key,row[0]) if row else None
    if not choice or choice.get('personal_id') or not choice.get('character') or not choice.get('production') or is_broadcast_credit(choice):
        raise HTTPException(400,'Choose a known public character role, not a personal or broadcast profile.')
    for name in (choice['person'],choice['character'],choice['production']):assert_public_name(name)
    label=portrayal_production_label(choice)
    match=re.search(r'\((\d{4})\)$',label)
    if not match:raise HTTPException(409,'Set the production year in the catalog before analyzing this portrayal.')
    year=int(match.group(1))
    return {'choice_key':key,'person':choice['person'],'character':choice['character'],'production':choice['production'],'year':year,
            'label':f"{choice['character']} portrayed by {choice['person']} in {label}",
            'profile_key':portrayal_identity_key(choice['character'],choice['production'],choice['person'],year)}

def appearance_photo_rows(role):
    rows=rank_reference_photos([r for r in workshop_photo_rows(role['person'],role['production'],role['character']) if compatible_reference_year(str(role['year']),r['production'])])
    out=[]
    with connect() as db:
        sources={r[0]:r[1:] for r in db.execute('SELECT id,source_url,page_url,quality_notes FROM reference_images')}
    for row in rows:
        explicit=re.search(r'\b((?:18|19|20)\d{2})\)?\s*$',row['production'])
        if explicit and int(explicit.group(1))!=role['year']:continue
        source,page,notes=sources.get(row['id'],('','',''))
        from urllib.parse import urlsplit
        try:host=urlsplit(page or source).hostname if (page or source).startswith('https://') else None
        except ValueError:host=None
        origin='Local upload' if source.startswith('local-upload:') else ('Collected from '+host if host else 'Saved character collection')
        out.append({'id':row['id'],'path':row['path'],'url':'api/reference-images/file/'+row['id'],'label':'Approved character reference '+str(row['quality_rank']),'dated':bool(explicit),
                    'source':origin,'width':row['width'],'height':row['height'],'quality':row['quality'],'quality_rank':row['quality_rank'],
                    'sharpness':row['sharpness'],'face_count':row['face_count'],'quality_notes':notes})
    # Only already archived local character artwork. Never download an image to run analysis.
    with connect() as db:
        row=db.execute('SELECT url FROM images WHERE key=?',('role|'+canonical_role_key(role['person'],role['character'],role['production']),)).fetchone()
        if row and row[0].startswith('https://'):
            local=db.execute('SELECT filename FROM photo_files WHERE url=?',(row[0],)).fetchone()
            row=('api/photos/'+local[0],) if local else None
    if row and row[0].startswith('api/photos/'):
        filename=row[0].removeprefix('api/photos/')
        path=safe_media_file(PHOTO_DIR,filename,r'[0-9a-f]{64}\.jpg')
        if path:
            width=height=None
            try:
                with Image.open(path) as image:width,height=image.size
            except (OSError,ValueError,Image.DecompressionBombError):return out
            out.insert(0,{'id':'portrait','path':path,'url':row[0],'label':'Saved character artwork','dated':False,
                          'source':'Local character portrait','width':width,'height':height,'quality':None,
                          'low_resolution':bool(width and height and (min(width,height)<600 or width*height<500_000))})
    return out

@app.get('/api/appearance/options')
def appearance_options():
    bridge=getattr(app.state,'casting_vision_bridge',None)
    return bridge.options() if bridge else {'ready':False,'models':[],'reason':'Native WanGP vision bridge unavailable.'}

@app.get('/api/appearance/references')
def appearance_references(choice_key:str=Query(min_length=1,max_length=1200)):
    role=appearance_role(choice_key)
    rows=appearance_photo_rows(role)
    with connect() as db:
        saved=db.execute('SELECT payload FROM appearance_analysis WHERE key=?',(role['profile_key'],)).fetchone()
    return {'role':role,'photos':[{k:v for k,v in r.items() if k!='path'} for r in rows], 'saved':json.loads(saved[0]) if saved else None}

class AppearanceSelection(BaseModel):
    choice_key:str=Field(min_length=1,max_length=1200)
    image_ids:list[str]=Field(min_length=1,max_length=4)
class AppearanceBatch(BaseModel):
    engine:str=Field(min_length=1,max_length=20)
    selections:list[AppearanceSelection]=Field(min_length=1,max_length=20)
class AppearanceApproval(BaseModel):
    index:int=Field(ge=0,le=19)
    traits:str=Field(min_length=1,max_length=2200)

def appearance_source_bytes(task):
    current=appearance_role(task['choice_key'])
    if current['profile_key']!=task['profile_key']:raise HTTPException(409,'Casting portrayal changed; start a new analysis.')
    available={r['id']:r for r in appearance_photo_rows(current)}
    if any(i not in available for i in task['image_ids']):raise HTTPException(409,'A selected reference is no longer available or approved.')
    data=[]; fingerprints=[]
    for i in task['image_ids']:
        path=available[i]['path']
        with path.open('rb') as stream:raw=stream.read(16_000_001)
        if len(raw)>16_000_000:raise HTTPException(422,'Reference is too large for vision analysis.')
        data.append(raw);fingerprints.append(hashlib.sha256(raw).hexdigest())
    return data,fingerprints

def resolve_appearance_images(task):
    data,fingerprints=appearance_source_bytes(task);images=[]
    if fingerprints!=task['staged_fingerprints']:raise HTTPException(409,'Source images changed after selection; review and analyze again.')
    try:
        for raw in data:
            with Image.open(io.BytesIO(raw)) as image:
                if image.width*image.height>25_000_000:raise ValueError('Reference dimensions too large')
                image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((1024,1024),Image.Resampling.LANCZOS);images.append(image)
        return images,fingerprints
    except Exception:
        for image in images:image.close()
        raise

@app.post('/api/appearance/batch')
def appearance_batch(req:AppearanceBatch):
    bridge=appearance_bridge(); tasks=[];seen=set()
    for selection in req.selections:
        role=appearance_role(selection.choice_key)
        if role['profile_key'] in seen:raise HTTPException(400,'Duplicate portrayal in batch')
        seen.add(role['profile_key'])
        available={r['id'] for r in appearance_photo_rows(role)}
        if len(set(selection.image_ids))!=len(selection.image_ids) or not set(selection.image_ids)<=available:raise HTTPException(400,'Select 1–4 available character-specific references per role')
        task={**role,'image_ids':selection.image_ids,'baseline':exact_identity_snapshot(role['profile_key'])}
        _,task['staged_fingerprints']=appearance_source_bytes(task)
        tasks.append(task)
    try:return bridge.stage(req.engine,tasks)
    except Exception as exc:raise HTTPException(409,str(exc)[:400]) from exc

# Conservative review guard, not a semantic clothing classifier.
# Never strip text or conflate integrated mechanical anatomy with removable armor.
_APPEARANCE_WARDROBE = re.compile(
    r"\b(?:clothing|costumes?|wardrobe|outfits?|uniforms|(?:a|an|military|school|dress|flight)\s+uniform|shirts?|jackets?|(?:leather|wool|winter|trench|lab)\s+coats?|"
    r"trousers|pants|skirts?|dresses|robes?|cloaks?|boots?|shoes?|"
    r"leather\s+straps?|utility\s+belts?|belts?|gauntlets?|gloves?|helmets?|goggles?|"
    r"necklaces?|earrings?|bracelets?|jewelry|jewellery|holsters?|"
    r"shoulder\s+(?:armor|armour)|chest\s+(?:armor|armour))\b",
    re.IGNORECASE,
)

def appearance_wardrobe_flags(traits):
    return list(dict.fromkeys(m.group(0).lower() for m in _APPEARANCE_WARDROBE.finditer(traits)))

@app.get('/api/appearance/batch/{job_id}')
def appearance_status(job_id:str):
    result=appearance_bridge().status(job_id)
    if result is None:raise HTTPException(404,'Appearance batch unavailable; run it again.')
    for draft in result.get('results',[]):
        if draft.get('state')=='review':draft['wardrobe_flags']=appearance_wardrobe_flags(draft.get('traits',''))
    return result

@app.post('/api/appearance/batch/{job_id}/cancel')
def appearance_cancel(job_id:str):
    if not appearance_bridge().cancel(job_id):raise HTTPException(404,'Appearance batch unavailable')
    return {'cancelled':True}

@app.post('/api/appearance/batch/{job_id}/approve')
def appearance_approve(job_id:str,req:AppearanceApproval):
    bridge=appearance_bridge();traits=req.traits.strip();validate_appearance_traits(traits)
    if not traits:raise HTTPException(400,'Enter an appearance description')
    flags=appearance_wardrobe_flags(traits)
    if flags:raise HTTPException(400,'Possible wardrobe or removable equipment in identity: '+', '.join(flags)+'. Edit the draft to describe physical traits only; keep wardrobe in its own field.')
    with bridge.lock:
        job=bridge.job
        if not job or job['id']!=job_id or job['state'] not in ('completed','cancelled','failed'):raise HTTPException(409,'Wait for the batch to finish before approving drafts')
        result=next((r for r in job['results'] if r['index']==req.index and r['state']=='review'),None)
        if not result:raise HTTPException(409,'No pending draft for this portrayal')
        key=result['profile_key']
        with lock,connect() as db:
            _,fingerprints=appearance_source_bytes(result)
            if fingerprints!=result['fingerprints']:raise HTTPException(409,'Source images changed; analyze again.')
            row=db.execute('SELECT traits,updated_at FROM character_identity WHERE key=?',(key,)).fetchone()
            if (list(row) if row else None)!=result['baseline']:raise HTTPException(409,'A saved profile changed since analysis; existing edits retained.')
            meta={'engine':job['engine'],'backend':job['backend'],'year':result['year'],'person':result['person'],'character':result['character'],'production':result['production'],'image_ids':result['image_ids'],'fingerprints':fingerprints,'approved_at':int(time.time())}
            db.execute('INSERT OR REPLACE INTO character_identity VALUES (?,?,?)',(key,traits,int(time.time())))
            db.execute('INSERT OR REPLACE INTO appearance_analysis VALUES (?,?)',(key,json.dumps(meta)))
        result.update(state='approved',traits=traits)
    return {'saved':True,'traits':traits}

def workshop_portrait_candidates(bridge,family):
    candidates=[]
    for option in MODEL_OPTIONS:
        if option['kind']!='image' or option['family']!=family:continue
        try:models=bridge.models(option['id'])
        except (ValueError,RuntimeError):continue
        for model in models:
            if model['ready']:
                candidates.append({'model':option['id'],'model_type':model['model_type'],'name':model['name']})
    return candidates


@app.get('/api/workshop/portrait-models')
def workshop_portrait_models(family:str='minimax_h3'):
    if family not in ('minimax_h3','flux2'):raise HTTPException(400,'Unknown RefMod family')
    return {'models':workshop_portrait_candidates(workshop_relay(),family)}


@app.get('/api/workshop/models')
def workshop_models(family:str='minimax_h3'):
    if family not in ('minimax_h3','flux2'):
        raise HTTPException(400,'Unknown RefMod family')
    try:
        relay=workshop_relay()
        if family=='minimax_h3':return {'models':relay.models('h3_video')}
        all_models=[];seen=set()
        for board in ('flux2_dev','flux2_klein4','flux2_klein9','pi_flux2','flux3_klein'):
            try: group=relay.models(board)
            except (ValueError,RuntimeError):continue  # other family members may be absent
            for model in group:
                if model['model_type'] not in seen:
                    all_models.append(model);seen.add(model['model_type'])
        return {'models':all_models}
    except (ValueError,RuntimeError) as exc:raise HTTPException(503,str(exc))


WORKSHOP_SCAN_LOCK=threading.RLock()
WORKSHOP_SCAN_STATE={'running':False,'started':None,'last_scanned':None,
                     'total':0,'checked':0,'valid':0,'invalid':0,'error':'',
                     'phase':'Not scanned this session'}
WORKSHOP_MOD_CACHE={'created':0,'items':[],'skipped':[]}
WORKSHOP_SCAN_HISTORY=external_data_path(DATA/'workshop_last_scan.json')
try:
    previous=json.loads(WORKSHOP_SCAN_HISTORY.read_text(encoding='utf-8'))
    if isinstance(previous,dict):
        for k in ('last_scanned','total','checked','valid','invalid'):
            if k in previous:WORKSHOP_SCAN_STATE[k]=previous[k]
        if WORKSHOP_SCAN_STATE['last_scanned']:
            WORKSHOP_SCAN_STATE['phase']='Previous scan completed'
except (OSError,ValueError):pass

@app.get('/api/workshop/scan-status')
def workshop_scan_status():
    with WORKSHOP_SCAN_LOCK:
        state=WORKSHOP_SCAN_STATE.copy()
        state['progress']=round(state['checked']*100/state['total'],1) if state['total'] else 0
        return state

@app.get('/api/workshop/mods')
def workshop_mods(force:bool=False):
    # RLock protects the index and status, but a slow filesystem scan should
    # expose progress to independent GET /scan-status requests. See lock below.
    now=time.monotonic()
    if not force and WORKSHOP_MOD_CACHE['created'] and now-WORKSHOP_MOD_CACHE['created']<90:
        with WORKSHOP_SCAN_LOCK:
            return {'mods':list(WORKSHOP_MOD_CACHE['items']),
                    'skipped':list(WORKSHOP_MOD_CACHE['skipped']),
                    'filter':'.safetensors files with valid H3 metadata only'}
    root=workshop_public_mod_root().resolve()
    selected_root=effective_local_paths()['public_h3'].resolve()
    with WORKSHOP_SCAN_LOCK:
        if WORKSHOP_SCAN_STATE['running']:
            # A simultaneous refresh never starts a duplicate scan.
            return {'mods':list(WORKSHOP_MOD_CACHE['items']),
                    'skipped':list(WORKSHOP_MOD_CACHE['skipped']),
                    'filter':'.safetensors files with valid H3 metadata only',
                    'refreshing':True}
        WORKSHOP_SCAN_STATE.update(running=True,started=int(time.time()),
             total=0,checked=0,valid=0,invalid=0,error='',phase='Discovering files')
    try:
        files=[]
        if root.is_dir():
            files=[f for f in root.rglob('*.safetensors') if f.is_file()
                   and not f.is_symlink() and f.resolve().is_relative_to(root)
                   and f.resolve().is_relative_to(selected_root)
                   and not f.name.startswith('._')]
        with WORKSHOP_SCAN_LOCK:
            WORKSHOP_SCAN_STATE.update(total=len(files),phase='Validating safetensors headers')
        items=[];skipped=[]
        for index,file in enumerate(sorted(files),1):
            try:
                metadata=read_header(file)
                rel=file.relative_to(root).with_suffix('').as_posix()
                items.append({'name':'celebs/'+rel,'filename':file.name,
                              'bytes':file.stat().st_size,'metadata':metadata})
            except (ValueError,OSError,UnicodeError) as e:
                skipped.append({'filename':file.name,'reason':str(e)[:140]})
            with WORKSHOP_SCAN_LOCK:
                WORKSHOP_SCAN_STATE.update(checked=index,valid=len(items),invalid=len(skipped))
        stamp=int(time.time())
        with WORKSHOP_SCAN_LOCK:
            WORKSHOP_MOD_CACHE.update(created=time.monotonic(),items=items,skipped=skipped)
            WORKSHOP_SCAN_STATE.update(last_scanned=stamp,phase='Scan complete')
            document={k:WORKSHOP_SCAN_STATE[k] for k in ('last_scanned','total','checked','valid','invalid')}
        try:
            atomic_state_write(WORKSHOP_SCAN_HISTORY,json.dumps(document,indent=2))
        except OSError:pass # read-only filesystem must not block scanning
        return {'mods':items,'skipped':skipped,
                'filter':'.safetensors files with valid H3 metadata only'}
    except Exception as e:
        with WORKSHOP_SCAN_LOCK:
            WORKSHOP_SCAN_STATE.update(error=str(e)[:200],phase='Scan failed')
        raise
    finally:
        with WORKSHOP_SCAN_LOCK:WORKSHOP_SCAN_STATE['running']=False


class WorkshopCreateRequest(BaseModel):
    person:str=Field(min_length=2,max_length=160)
    production:str=''
    character:str|None=Field(default=None,max_length=150)
    image_ids:list[str]=Field(min_length=1,max_length=20)
    name:str=Field(min_length=2,max_length=120)
    model_type:str=Field(min_length=2,max_length=160)
    mode:str='encode'
    family:str='minimax_h3'
    layout:str='separate'
    budget:int=4096
    test_portrait:bool=False
    test_portrait_model:str|None=Field(default=None,max_length=160)
    test_portrait_model_type:str|None=Field(default=None,max_length=200)


class WorkshopDecompileRequest(BaseModel):
    name:str=Field(min_length=3,max_length=260)
    model_type:str=Field(min_length=2,max_length=160)


def validate_workshop_task(task):
    bridge=workshop_relay()
    base=bridge.adapter.refmod_root.resolve()
    if not (task.model_type and task.op in ('extract','extract_flux','decompile')):
        raise ValueError('Unsupported workshop operation')
    fork=bridge.adapter.discover()
    if (fork.get('fork_revision') or 0)<39:
        raise ValueError('This workshop requires Refmod-Fork fork.39 or newer')
    if task.op in ('extract','extract_flux'):
        family='flux2' if task.op=='extract_flux' else 'minimax_h3'
        if family!=task.family:raise ValueError('Extraction family mismatch')
        expected=public_workshop_path(base,family,task.name,'.safetensors')
        if task.expected!=expected or task.spec.get('name')!=task.name:
            raise ValueError('RefMod output directory or name changed after staging; submit again')
        if expected.exists():
            raise ValueError('That RefMod already exists. Choose another name; existing mods are never overwritten')
        current={str(r['path']):r for r in workshop_photo_rows()}
        if not task.sources or any(p not in current for p in task.sources):
            raise ValueError('A source photo is missing, no longer approved, or belongs to Personal')
        key='images' if task.op=='extract_flux' else 'image_paths'
        if [str(p) for p in task.spec.get(key,[])]!=list(task.sources):
            raise ValueError('Photo selection changed after approval')
    else:
        expected=public_workshop_path(base,'decompiled',task.name)
        file=public_workshop_path(base,'minimax_h3',task.name,'.safetensors')
        if not file.is_file():
            raise ValueError('The selected public H3 RefMod is missing')
        if task.expected!=expected or task.spec.get('name')!=task.name:
            raise ValueError('Invalid decompile output folder')
        read_header(file)
    return True


@app.post('/api/workshop/create')
def workshop_create(item:WorkshopCreateRequest):
    bridge=workshop_relay()
    if item.family not in ('minimax_h3','flux2'):raise HTTPException(400,'Unsupported RefMod family')
    if item.family=='minimax_h3' and item.mode not in ('encode','training'):
        raise HTTPException(400,'Unsupported H3 extraction mode')
    try:name=safe_mod_name(item.name,False)
    except ValueError as exc:raise HTTPException(400,str(exc))
    photos=workshop_photo_rows(item.person,item.production,item.character)
    photo_map={r['id']:r for r in photos}
    if len(set(item.image_ids))!=len(item.image_ids) or any(k not in photo_map for k in item.image_ids):
        raise HTTPException(400,'Select approved photos belonging to this public performer/production')
    paths=[photo_map[k]['path'] for k in item.image_ids]
    try:expected=public_workshop_path(bridge.adapter.refmod_root,item.family,name,'.safetensors')
    except (ValueError,OSError,RuntimeError) as exc:raise HTTPException(409,str(exc))
    try:
        if item.family=='flux2':
            from ..workshop_bridge import build_flux_extract_spec
            spec=build_flux_extract_spec(name,paths,item.layout,item.budget)
            op='extract_flux'
        else:
            spec=build_extract_spec(name,paths,item.mode)
            op='extract'
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc))
    task=WorkshopTask(op,item.model_type,name,spec,expected,tuple(map(str,paths)),item.family)
    if item.test_portrait:
        candidates=workshop_portrait_candidates(bridge,item.family)
        if item.test_portrait_model is None and item.test_portrait_model_type is None and len(candidates)==1:
            # Backward compatibility for older clients with exactly one valid choice.
            chosen=candidates[0]
        else:
            chosen=next((c for c in candidates if c['model']==item.test_portrait_model and c['model_type']==item.test_portrait_model_type),None)
        if chosen is None:raise HTTPException(400,'Choose a compatible installed image model for the test portrait, or turn the test portrait off')
        board,checkpoint=chosen['model'],chosen['model_type']
        def test_portrait():
            from ..queue_bridge import Submission
            if not any(c['model']==board and c['model_type']==checkpoint for c in workshop_portrait_candidates(bridge,item.family)):
                raise ValueError('Selected test portrait model is no longer available; no substitute was used')
            stat=expected.stat()
            def validate(sub):
                assert_public_name(item.person)
                current=public_workshop_path(bridge.adapter.refmod_root,item.family,name,'.safetensors')
                if current!=expected or not current.is_file() or (current.stat().st_size,current.stat().st_mtime_ns)!=(stat.st_size,stat.st_mtime_ns):raise ValueError('New RefMod changed before test generation')
                return portrait_prompt(board).replace('linked Personal RefMod','newly created RefMod'),item.family,current
            sub=Submission(model=board,model_type=checkpoint,choice_key='workshop-test:'+name,monitor_details={'person':item.person,'character':item.character or '', 'production':item.production,'kind':'image','scene':1})
            return sub,validate
        task.test_portrait=test_portrait
    try:job=bridge.enqueue_workshop(task,validate_workshop_task)
    except (ValueError,RuntimeError) as e:raise HTTPException(409,str(e))
    return {'job_id':job,'operation':'extract','target':name}


@app.post('/api/workshop/decompile')
def workshop_decompile(item:WorkshopDecompileRequest):
    bridge=workshop_relay()
    if not re.fullmatch(r'celebs/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+',item.name):
        raise HTTPException(400,'Invalid public H3 RefMod identifier')
    try:expected=public_workshop_path(bridge.adapter.refmod_root,'decompiled',item.name)
    except (ValueError,OSError,RuntimeError) as exc:raise HTTPException(409,str(exc))
    task=WorkshopTask('decompile',item.model_type,item.name,{'op':'decompile','name':item.name},expected)
    try:job=bridge.enqueue_workshop(task,validate_workshop_task)
    except (ValueError,RuntimeError) as e:raise HTTPException(409,str(e))
    return {'job_id':job,'operation':'decompile','target':item.name}


@app.get('/api/workshop/jobs/{job_id}')
def workshop_job_status(job_id:str):
    bridge=workshop_relay()
    job=bridge.status(job_id)
    if not job or job.get('operation') not in ('extract','decompile','extract_flux'):
        raise HTTPException(404,'Workshop job not found')
    return job


def _safe_decompiled(name:str):
    if not re.fullmatch(r'celebs/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+',name):
        raise HTTPException(400,'Invalid public H3 RefMod name')
    try:folder=public_workshop_path(workshop_relay().adapter.refmod_root,'decompiled',name)
    except (ValueError,OSError,RuntimeError) as exc:raise HTTPException(404,str(exc))
    if not folder.is_dir():
        raise HTTPException(404,'No reconstructed media found')
    return folder

DECOMPILED_TYPES={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg',
                  '.webp':'image/webp','.mp4':'video/mp4','.wav':'audio/wav'}

@app.get('/api/workshop/decompiled')
def workshop_decompiled_listing(name:str=Query(min_length=3,max_length=260)):
    folder=_safe_decompiled(name)
    entries=[]
    for file in sorted(folder.iterdir()):
        if (not file.is_file() or file.is_symlink() or
            file.suffix.lower() not in DECOMPILED_TYPES or
            not file.resolve().is_relative_to(folder)):
            continue
        entries.append({'filename':file.name,'media_type':DECOMPILED_TYPES[file.suffix.lower()],
                        'size':file.stat().st_size,
                        'url':'api/workshop/decompiled/file?'+urlencode({'name':name,'file':file.name})})
    return {'name':name,'files':entries}

@app.get('/api/workshop/decompiled/file')
def workshop_decompiled_file(name:str=Query(min_length=3,max_length=260),
                             file:str=Query(min_length=1,max_length=256)):
    folder=_safe_decompiled(name)
    if Path(file).name!=file or Path(file).suffix.lower() not in DECOMPILED_TYPES:
        raise HTTPException(400,'Invalid reconstructed media filename')
    path=folder/file
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(folder):
        raise HTTPException(404,'Reconstructed media not found')
    return FileResponse(path,media_type=DECOMPILED_TYPES[path.suffix.lower()],
                        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@app.get('/api/workshop/decompiled.zip')
def workshop_decompiled_zip(name:str=Query(min_length=3,max_length=260)):
    if not re.fullmatch(r'celebs/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+',name):
        raise HTTPException(400,'Invalid public H3 RefMod name')
    folder=_safe_decompiled(name)
    found=[p for p in sorted(folder.iterdir()) if p.is_file() and not p.is_symlink()
           and p.suffix.casefold() in DECOMPILED_TYPES]
    if not found:raise HTTPException(404,'No decompiled files found')
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=2) as z:
        for p in found:z.write(p,p.name)
    output.seek(0)
    return StreamingResponse(output,media_type='application/zip',headers={
        'Content-Disposition':f'attachment; filename="{Path(name).name}_Decompiled.zip"'})


# Generation preferences live outside the git-installed plugin, independent of browser origin.
def model_preferences_path():
    return external_data_path(DATA/'model_preferences.json')


def validate_model_preferences(data):
    if not isinstance(data,dict) or set(data)!={'generator','global_loras'}:
        raise ValueError('Invalid model preference envelope')
    def safe(value,depth=0):
        if depth>12:raise ValueError('Preferences nested too deeply')
        if value is None or type(value) in (bool,int,str):return
        if type(value) is float:
            import math
            if not math.isfinite(value):raise ValueError('Nonfinite preference')
            return
        if isinstance(value,list):
            for item in value:safe(item,depth+1)
            return
        if isinstance(value,dict):
            for key,item in value.items():
                if key in ('__proto__','constructor','prototype'):raise ValueError('Invalid preference key')
                safe(item,depth+1)
            return
        raise ValueError('Invalid preference value')
    safe(data)
    gen=data['generator'];loras=data['global_loras']
    if not isinstance(gen,dict) or gen.get('version')!=1 or not isinstance(loras,dict) or loras.get('version')!=2:
        raise ValueError('Unsupported model preference version')
    if set(gen)-{'version','boardModel','lastImageBoard','selectedModels','modelSettings'} or set(loras)-{'version','profiles','legacy'}:
        raise ValueError('Unknown preference field')
    for field in ('boardModel','lastImageBoard'):
        if not isinstance(gen.get(field),str):raise ValueError('Invalid model selection')
    if not isinstance(gen.get('selectedModels'),dict) or not all(isinstance(v,str) for v in gen['selectedModels'].values()):raise ValueError('Invalid model selections')
    if not isinstance(gen.get('modelSettings'),dict) or not all(isinstance(v,dict) and '::' in k for k,v in gen['modelSettings'].items()):raise ValueError('Invalid model settings')
    for field in ('profiles','legacy'):
        if not isinstance(loras.get(field),dict) or not all(isinstance(v,list) for v in loras[field].values()):raise ValueError('Invalid LoRA preferences')
    return data


@app.get('/api/settings/model-preferences')
def get_model_preferences():
    with lock:
        path=model_preferences_path()
        try:
            data=validate_model_preferences(json.loads(path.read_text(encoding='utf-8'))) if path.exists() else None
        except (OSError,ValueError,TypeError,RecursionError) as exc:
            raise HTTPException(409,'Saved model settings are unreadable; original file retained.') from exc
    return JSONResponse({'preferences':data},headers={'Cache-Control':'no-store'})


@app.put('/api/settings/model-preferences')
async def put_model_preferences(request:Request):
    raw=bytearray()
    async for chunk in request.stream():
        if len(raw)+len(chunk)>2_000_000:raise HTTPException(413,'Model settings exceed 2 MB')
        raw.extend(chunk)
    try:
        data=validate_model_preferences(json.loads(raw))
        content=json.dumps(data,allow_nan=False,indent=2)+'\n'
    except (ValueError,TypeError,RecursionError) as exc:raise HTTPException(422,'Invalid model settings') from exc
    with lock:
        path=model_preferences_path()
        # Do not silently replace an unreadable existing settings file.
        if path.exists():
            try:validate_model_preferences(json.loads(path.read_text(encoding='utf-8')))
            except (OSError,ValueError,TypeError,RecursionError) as exc:raise HTTPException(409,'Saved model settings are unreadable; original file retained.') from exc
        atomic_state_write(path,content)
    return {'saved':True}


# User-owned settings backups are never part of the distributable plugin.
@app.get('/api/settings/prompt-backup')
def export_prompt_backup():
    try:
        with lock,connect() as db:
            data={
                'templates':{k:json.loads(v) for k,v in db.execute('SELECT id,payload FROM prompt_settings')},
                'overrides':{k:json.loads(v) for k,v in db.execute('SELECT key,payload FROM prompt_overrides')},
                'final_edits':[dict(zip(('key','choice_key','personal_id','prompt'),row)) for row in db.execute('SELECT key,choice_key,personal_id,prompt FROM final_prompt_edits')],
                'character_traits':dict(db.execute('SELECT key,traits FROM character_identity')),
                'production_sets':[{'production':p,'family':f,'choices':json.loads(v)} for p,f,v in db.execute('SELECT production,family,payload FROM production_selection_sets')]}
        return JSONResponse(data,headers={'Cache-Control':'no-store'})
    except (ValueError,TypeError) as exc:
        raise HTTPException(409,'Saved prompt data is damaged. Repair the affected template before exporting; no data has been changed.') from exc

@app.post('/api/settings/prompt-backup')
async def import_prompt_backup(request:Request):
    raw=bytearray()
    async for chunk in request.stream():
        if len(raw)+len(chunk)>16_000_000:raise HTTPException(413,'Backup exceeds 16 MB')
        raw.extend(chunk)
    try:
        data=json.loads(raw)
        if not isinstance(data,dict) or set(data)-{'templates','overrides','final_edits','character_traits','production_sets'} or not {'templates','overrides','final_edits','character_traits'}<=set(data):raise ValueError('Unrecognized prompt backup structure')
        sets=data.get('production_sets',[]);production_sets=[];seen=set();private=personal_name_keys()
        if not isinstance(sets,list) or len(sets)>10000:raise ValueError('Invalid production collections')
        for rec in sets:
            if not isinstance(rec,dict) or set(rec)!={'production','family','choices'}:raise ValueError('Invalid production collection')
            prod,family,choices=rec['production'],rec['family'],rec['choices']
            if not isinstance(prod,str) or not prod or len(prod)>180 or token(prod)!=prod or not isinstance(family,str) or family not in ('minimax_h3','flux2') or (prod,family) in seen or not isinstance(choices,list) or not 1<=len(choices)<=2000:raise ValueError('Invalid production collection')
            keys=set()
            for c in choices:
                if not isinstance(c,dict) or not decoded_choice(c.get('key'),json.dumps(c)) or c.get('personal_id') or token(canonical_name(c['person'])) in private or token(canonical_production(c['production']))!=prod or c['key']!=canonical_role_key(c['person'],c['character'],c['production']) or c['key'] in keys:raise ValueError('Invalid production collection selection')
                # Store only the known selection fields. Actual availability and family are checked on restore.
                ref=c['refmod'];parts=Path(ref).parts
                if not parts or Path(ref).is_absolute() or '..' in parts or '\\' in ref or not ref.endswith('.safetensors'):raise ValueError('Invalid collection RefMod identifier')
                keys.add(c['key'])
            seen.add((prod,family));production_sets.append((prod,family,json.dumps([{k:c[k] for k in ('key','person','character','production','refmod','year') if k in c} for c in choices])))
        def mapping(name):
            value=data[name]
            if not isinstance(value,dict) or len(value)>10000 or any(not isinstance(k,str) or not k or len(k)>500 for k in value):raise ValueError('Invalid '+name)
            return value
        templates=[];overrides=[];traits=[];edits=[]
        for k,v in mapping('templates').items():
            if not isinstance(v,dict):raise ValueError('Invalid template')
            if k=='default':value=TemplatePayload.model_validate({**SAMPLE_TEMPLATE,**v}).model_dump()
            elif k.startswith('image_') and MODEL_BY_ID.get(k[6:],{}).get('kind')=='image':value=image_template_normalized(v)
            else:raise ValueError('Unknown template model: '+k)
            templates.append((k,json.dumps(value)))
        for k,v in mapping('overrides').items():
            if not isinstance(v,dict):raise ValueError('Invalid override')
            overrides.append((k,json.dumps(TemplatePayload.model_validate(v).model_dump(exclude_unset=True))))
        for k,v in mapping('character_traits').items():
            if not isinstance(v,str) or len(v)>2200 or any(x in v for x in ('<Subject 2>','wardrobe_description:','detailed_description:')):raise ValueError('Invalid character traits')
            traits.append((k,v,int(time.time())))
        if not isinstance(data['final_edits'],list) or len(data['final_edits'])>10000:raise ValueError('Invalid final prompt edits')
        for row in data['final_edits']:
            if not isinstance(row,dict) or set(row)!={'key','choice_key','personal_id','prompt'} or any(not isinstance(v,str) for v in row.values()):raise ValueError('Invalid final prompt entry')
            k,choice,pid,prompt=(row[x] for x in ('key','choice_key','personal_id','prompt'))
            parts=json.loads(k)
            if not isinstance(parts,list) or len(parts)!=5 or parts[0]!=choice or len(choice)>500 or len(pid)>150 or len(k)>2000 or not 12<=len(prompt)<=100000 or not isinstance(parts[1],str) or parts[1] not in MODEL_BY_ID or not isinstance(parts[2],str) or not all(type(x) is int for x in parts[3:]):raise ValueError('Invalid final prompt key')
            edits.append((k,choice,pid,prompt))
    except (ValueError,TypeError,KeyError) as exc:raise HTTPException(422,'Invalid backup: '+str(exc)[:240]) from exc
    skipped=0
    with lock,connect() as db:
        db.executemany('INSERT OR REPLACE INTO prompt_settings VALUES (?,?)',templates)
        db.executemany('INSERT OR REPLACE INTO prompt_overrides VALUES (?,?)',overrides)
        db.executemany('INSERT OR REPLACE INTO character_identity VALUES (?,?,?)',traits)
        db.executemany('DELETE FROM appearance_analysis WHERE key=?',[(row[0],) for row in traits])
        db.executemany('INSERT OR REPLACE INTO production_selection_sets VALUES (?,?,?)',production_sets)
        for row in edits:
            if row[2] and not db.execute('SELECT 1 FROM personal_profiles WHERE id=? AND consent=1',(row[2],)).fetchone():
                skipped+=1;continue
            db.execute('INSERT OR REPLACE INTO final_prompt_edits VALUES (?,?,?,?)',row)
    return {'saved':True,'templates':len(templates),'overrides':len(overrides),'final_edits':len(edits)-skipped,'skipped_private_edits':skipped,'character_traits':len(traits),'production_sets':len(production_sets)}

from flask import Blueprint, jsonify, request
import os
import json
import requests
import urllib.parse
import urllib.request
import time

import shared

radio_bp = Blueprint('radio_bp', __name__)

# (cache de l'API Radio France : voir la section « INTÉGRATION API RADIO FRANCE » plus bas)

def load_radios():
    if os.path.exists(shared.RADIOS_FILE):
        try:
            with open(shared.RADIOS_FILE, 'r') as f: shared.radios_list = json.load(f)
        except: shared.radios_list = []
    else:
        shared.radios_list = [
            {"name": "RTL2", "uuid": "034d52a3-30dc-4017-8495-004cd65383b1"}, 
            {"name": "101 SMOOTH JAZZ", "uuid": "d28420a4-eccf-47a2-ace1-088c7e7cb7e0"}
        ]
        save_radios()

def save_radios():
    try:
        with open(shared.RADIOS_FILE, 'w') as f: json.dump(shared.radios_list, f)
    except: pass

# =========================================================
# INTÉGRATION API RADIO FRANCE (GraphQL)
# =========================================================
import re
import unicodedata

RF_GRAPHQL_URL = "https://openapi.radiofrance.fr/v1/graphql"
RF_CACHE_TTL = 90      # s : réponse valide (quota Open API : 1000 requêtes / jour / clé)
RF_ERROR_TTL = 300     # s : échec (évite de retaper l'API à chaque événement de l'enceinte)
rf_cache = {}          # { "FIP": {"expires": timestamp, "data": {...} ou None} }

# Valeurs de StationsEnum (les mêmes que celles utilisées par radiofrance_downloader)
RF_NATIONAL = ("FRANCEINTER", "FRANCEINFO", "FRANCECULTURE", "FRANCEMUSIQUE", "FIP", "MOUV", "FRANCEBLEU")
# Locales « ici » (ex-France Bleu) : FRANCEBLEU_<NOM> — nom de l'enum à confirmer avec /api/radios/rf_test
RF_LOCAL_RE = re.compile(r"^FRANCEBLEU_[A-Z0-9_]{2,40}$")

# FIP est une radio musicale : l'API GraphQL n'y annonce presque jamais d'émission.
# Le morceau en cours vient de l'endpoint public « livemeta » (sans clé, hors quota).
RF_LIVEMETA = {
    "FIP": "https://api.radiofrance.fr/livemeta/pull/7",
}
RF_UA = "Mozilla/5.0 (X11; Linux aarch64) SoundCork/1.0"

RF_LOGOS = {
    "FRANCEINTER": "https://www.radiofrance.fr/build/images/logos/franceinter-1.svg",
}

_RF_PATTERNS = [
    (re.compile(r"\bFRANCE ?INTER\b"),   "FRANCEINTER"),
    (re.compile(r"\bFRANCE ?INFO\b"),    "FRANCEINFO"),
    (re.compile(r"\bFRANCE ?CULTURE\b"), "FRANCECULTURE"),
    (re.compile(r"\bFRANCE ?MUSIQUE\b"), "FRANCEMUSIQUE"),
    (re.compile(r"\bMOUV\b"),            "MOUV"),
    (re.compile(r"\bFIP\b"),             "FIP"),
]
_RF_ICI = re.compile(r"^(?:ICI|FRANCE ?BLEU)\b")   # "ici Toulouse", "France Bleu Occitanie"
_RF_IGNORABLE = {"DIRECT", "LIVE", "RADIO", "FM", "HIFI", "MIDFI", "LOFI", "AAC", "MP3", "PARIS", "STREAM", "EN",
                 "FRANCE", "FR", "HLS", "M3U8", "ICECAST"}
_RF_LOCAL_NOISE = {"DIRECT", "LIVE", "RADIO", "FM", "HIFI", "MIDFI", "LOFI", "AAC", "MP3", "STREAM"}


def _rf_norm(text):
    """Majuscules, sans accents ni ponctuation : "Mouv'" -> "MOUV"."""
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", " ", s.upper()).strip()


def _rf_valid(station):
    return station in RF_NATIONAL or bool(RF_LOCAL_RE.match(station))


def _rf_local_enum(reste):
    mots = [w for w in reste.split() if w not in _RF_LOCAL_NOISE]
    if not mots:
        return "FRANCEBLEU"
    candidat = "FRANCEBLEU_" + "_".join(mots)
    return candidat if RF_LOCAL_RE.match(candidat) else None


def detect_radiofrance_station(playlist="", track_artist=""):
    """
    Retourne la valeur StationsEnum (ex. 'FIP') si l'enceinte joue une antenne
    Radio France, sinon None.
      1) on regarde d'abord le nom de la station choisie dans l'appli (playlist) ;
         les webradios ("FIP Rock", "France Musique Jazz"...) sont écartées, car
         elles n'ont pas le programme de l'antenne principale ;
      2) à défaut, on retombe sur titre + artiste du flux (comportement d'origine).
    """
    name = _rf_norm(playlist)

    m = _RF_ICI.match(name)
    if m:
        return _rf_local_enum(name[m.end():])

    for rx, enum in _RF_PATTERNS:
        m = rx.search(name)
        if m:
            reste = (name[:m.start()] + " " + name[m.end():]).split()
            return enum if all(w in _RF_IGNORABLE or w.isdigit() for w in reste) else None

    flux = _rf_norm(track_artist)
    for rx, enum in _RF_PATTERNS:
        if rx.search(flux):
            return enum
    return None


def _rf_pretty(text):
    """FIP publie souvent en MAJUSCULES : on remet une casse lisible (sans toucher à "R.E.M.", "AC/DC")."""
    text = (text or "").strip()
    if not text or not text.isupper():
        return text
    return " ".join(w if any(c in w for c in "./&") else w[:1] + w[1:].lower() for w in text.split(" "))


def _rf_livemeta_step(payload, now):
    """Morceau en cours dans une réponse livemeta (levels/items/position -> steps), ou None."""
    steps = (payload or {}).get("steps") or {}
    try:
        level = payload["levels"][0]
        step = steps.get(level["items"][level["position"]])
        if isinstance(step, dict) and step.get("title"):
            return step
    except Exception:
        pass
    # Secours : le morceau dont l'intervalle [start, end] contient l'instant présent
    cands = [s for s in steps.values()
             if isinstance(s, dict) and s.get("title") and s.get("embedType", "song") == "song"
             and (s.get("start") or 0) <= now <= (s.get("end") or 0)]
    return max(cands, key=lambda s: s.get("start") or 0) if cands else None


def _rf_fetch_livemeta(station, now):
    """(data, ttl) depuis livemeta ; data = None si indisponible."""
    url = RF_LIVEMETA.get(station)
    if not url:
        return None, RF_ERROR_TTL
    try:
        r = requests.get(url, headers={"User-Agent": RF_UA, "Accept": "application/json"}, timeout=5)
        if r.status_code != 200:
            print(f"[RadioFrance] livemeta {station} : HTTP {r.status_code}")
            return None, RF_ERROR_TTL
        step = _rf_livemeta_step(r.json(), now)
        if not step:
            return None, RF_ERROR_TTL

        titre = _rf_pretty(step.get("title"))
        artiste = _rf_pretty(step.get("performers") or step.get("authors") or "")
        album = _rf_pretty(step.get("titreAlbum") or "")
        annee = step.get("anneeEditionMusique")
        if album and annee:
            album = f"{album} ({annee})"
        elif annee:
            album = str(annee)
        visual = step.get("visual")
        data = {
            "show_title": titre,
            "show_desc": " · ".join(p for p in (artiste, album) if p),
            "show_image": visual if isinstance(visual, str) and visual.startswith("http") else None,
        }
        end = step.get("end")
        # on redemande à la fin du morceau (entre 10 s et RF_CACHE_TTL)
        ttl = max(10, min(RF_CACHE_TTL, int(end - now) + 2)) if isinstance(end, (int, float)) and end > now else 10
        return data, ttl
    except Exception as e:
        print(f"[RadioFrance] livemeta {station} : {e}")
        return None, RF_ERROR_TTL


def _rf_query(station):
    # station est validée par _rf_valid() (liste blanche / [A-Z0-9_]) avant d'arriver ici
    return """
    query {
      live(station: __STATION__) {
        show {
          ... on BlankStep { title }
          ... on DiffusionStep {
            diffusion {
              title
              standFirst
              show { title }
            }
          }
        }
      }
    }
    """.replace("__STATION__", station)


def _rf_extract(payload):
    """(titre, description) de l'émission en cours, ou (None, "") s'il n'y en a pas."""
    live = ((payload or {}).get("data") or {}).get("live") or {}
    step = live.get("show") or {}
    titre, desc = None, ""
    diffusion = step.get("diffusion")
    if diffusion:
        show_obj = diffusion.get("show") or {}
        if show_obj.get("title"):
            # Ex: titre = "La Terre au carré", desc = titre de l'épisode
            titre = show_obj["title"]
            desc = diffusion.get("title") or diffusion.get("standFirst") or ""
        else:
            titre = diffusion.get("title")
            desc = diffusion.get("standFirst") or ""
    elif step.get("title"):
        titre = step["title"]          # créneau simple (ex: "Le Journal de 13h")
    return titre, desc


def get_radiofrance_live(station="FRANCEINTER"):
    """
    Émission en cours d'une antenne Radio France (API GraphQL).
    Cache par station (RF_CACHE_TTL) pour protéger le quota de 1000 requêtes/jour ;
    un échec est mémorisé plus longtemps (RF_ERROR_TTL). Renvoie None s'il n'y a rien à afficher.
    """
    station = str(station or "").upper()
    if not _rf_valid(station):
        return None

    now = time.time()
    entry = rf_cache.get(station)
    if entry and now < entry["expires"]:
        return entry["data"]

    data, ttl = None, RF_ERROR_TTL

    # FIP : le morceau en cours (sans clé API)
    if station in RF_LIVEMETA:
        data, ttl = _rf_fetch_livemeta(station, now)
        if data:
            rf_cache[station] = {"expires": now + ttl, "data": data}
            return data

    token = os.environ.get('RF_TOKEN')
    if not token:
        if station in RF_LIVEMETA:
            rf_cache[station] = {"expires": now + RF_ERROR_TTL, "data": None}
        return None

    try:
        response = requests.post(
            RF_GRAPHQL_URL,
            headers={"x-token": token, "Content-Type": "application/json"},
            json={'query': _rf_query(station)},
            timeout=5
        )
        if response.status_code == 200:
            payload = response.json()
            titre, desc = _rf_extract(payload)
            if titre:
                # Clés attendues par le Frontend (now.html -> .np-live-show)
                data = {
                    "show_title": titre,
                    "show_desc": desc,
                    "show_image": RF_LOGOS.get(station)
                }
                ttl = RF_CACHE_TTL
            elif payload.get("errors"):
                print(f"[RadioFrance] {station} : {str(payload['errors'])[:200]}")
            else:
                ttl = RF_CACHE_TTL      # API OK mais aucune émission annoncée (ex: FIP) : rien à afficher
        else:
            print(f"[RadioFrance] {station} : HTTP {response.status_code}")
    except Exception as e:
        print(f"Erreur API Radio France: {e}")

    rf_cache[station] = {"expires": now + ttl, "data": data}
    return data

@radio_bp.route('/api/radios/rf_live', methods=['GET'])
def rf_live_debug():
    """Diagnostic : /api/radios/rf_live?station=FIP  ou  ?name=FIP (Paris) pour tester la détection."""
    name = request.args.get('name')
    station = (request.args.get('station') or '').upper()
    if not station and name:
        station = detect_radiofrance_station(name, '') or ''
    if not _rf_valid(station):
        return jsonify({"status": "ERREUR", "name": name, "station_detectee": station or None,
                        "stations": list(RF_NATIONAL)}), 400
    rf_cache.pop(station, None)          # on force un vrai appel
    return jsonify({"station": station, "data": get_radiofrance_live(station)})


@radio_bp.route('/api/radios/rf_test', methods=['GET'])
def test_rf_api():
    token = os.environ.get('RF_TOKEN')
    url = RF_GRAPHQL_URL
    
    station = (request.args.get('station') or 'FRANCEINTER').upper()
    if not _rf_valid(station):
        return jsonify({"status": "ERREUR", "details": f"Station inconnue : {station}", "stations": list(RF_NATIONAL)}), 400
    query = _rf_query(station)
    
    try:
        response = requests.post(
            url, 
            headers={"x-token": token, "Content-Type": "application/json"}, 
            json={'query': query}, 
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # --- LOGIQUE D'EXTRACTION FINALE ---
            step = data.get('data', {}).get('live', {}).get('show', {})
            
            titre_final = "Direct"
            desc_finale = ""
            
            if step:
                # 1. Si c'est une grosse émission (DiffusionStep)
                if 'diffusion' in step and step['diffusion']:
                    diffusion = step['diffusion']
                    show_obj = diffusion.get('show', {})
                    
                    if show_obj and show_obj.get('title'):
                        # Ex: Titre = "La Terre au carré", Desc = "L'actualité de la planète..."
                        titre_final = show_obj.get('title')
                        desc_finale = diffusion.get('title', diffusion.get('standFirst', ''))
                    else:
                        titre_final = diffusion.get('title', 'Direct')
                        desc_finale = diffusion.get('standFirst', '')
                
                # 2. Si c'est un créneau simple (BlankStep, ex: "Le Journal de 13h")
                elif 'title' in step:
                    titre_final = step.get('title')
                    
            return jsonify({
                "status": "VICTOIRE", 
                "station": station,
                "emission_en_cours": titre_final,
                "description": desc_finale,
                "json_brut": data
            })
        else:
            return jsonify({"status": "ERREUR", "details": response.text})
            
    except Exception as e:
        return jsonify({"status": "CRASH", "erreur": str(e)})

@radio_bp.route('/api/play_radio', methods=['POST'])
def play_radio():
    data = request.json
    xml = f'<ContentItem source="RADIO_BROWSER" type="stationurl" location="/stations/byuuid/{data.get("uuid")}"><itemName>{data.get("name", "Radio")}</itemName></ContentItem>'
    for ip in data.get('ips', []):
        # --- FIX : On vide la file d'attente DLNA pour libérer l'enceinte ---
        if ip in shared.server_queues:
            shared.server_queues[ip] = {}
        # --------------------------------------------------------------------
        try: requests.post(f"http://{ip}:8090/select", data=xml, headers={"Content-Type": "application/xml"}, timeout=5)
        except: pass
    return jsonify({"status": "ok"})

@radio_bp.route('/api/radios/search', methods=['GET'])
def search_radio():
    query = request.args.get('q', '')
    country_filter = request.args.get('country', 'FR')
    if not query or len(query) < 2: return jsonify([])
    try:
        params = {"name": query, "countrycode": country_filter, "order": "clickcount", "reverse": "true", "limit": 30}
        url = f"https://de1.api.radio-browser.info/json/stations/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "SoundCorkApp/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # On extrait le favicon, sinon on renvoie notre code de secours
            return jsonify([{
                "name": s.get("name"), 
                "uuid": s.get("stationuuid"), 
                "country": s.get("countrycode", "").upper(),
                "logo": s.get("favicon") if s.get("favicon") else "FA_ICON"
            } for s in data])
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

@radio_bp.route('/api/radios/save', methods=['POST'])
def api_save_radios():
    data = request.json
    shared.radios_list = data['radios'] if isinstance(data, dict) and 'radios' in data else data
    save_radios()
    return jsonify({"status": "ok"})

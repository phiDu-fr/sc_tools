from flask import Blueprint, jsonify, request
import os
import json
import requests
import urllib.parse
import urllib.request
import time

import shared

radio_bp = Blueprint('radio_bp', __name__)

# --- CACHE EN MÉMOIRE (Évite de spammer l'API Radio France) ---
rf_cache = {"time": 0, "data": None}

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
rf_cache = {"time": 0, "data": None}

def get_radiofrance_live(station="FRANCEINTER"):
    """
    Interroge l'API GraphQL de Radio France.
    Utilise un cache de 60s pour protéger les quotas de l'API.
    """
    global rf_cache
    import time
    
    # Vérification du cache (60 secondes)
    if time.time() - rf_cache["time"] < 60 and rf_cache["data"]:
        return rf_cache["data"]

    token = os.environ.get('RF_TOKEN')
    if not token:
        return None
        
    url = "https://openapi.radiofrance.fr/v1/graphql"
    
    # La requête parfaite avec les "Fragments"
    query = """
    query {
      live(station: FRANCEINTER) {
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
    """
    
    try:
        response = requests.post(
            url, headers={"x-token": token, "Content-Type": "application/json"}, json={'query': query}, timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            step = data.get('data', {}).get('live', {}).get('show', {})
            
            titre_final = "Direct"
            desc_finale = ""
            
            if step:
                if 'diffusion' in step and step['diffusion']:
                    diffusion = step['diffusion']
                    show_obj = diffusion.get('show', {})
                    if show_obj and show_obj.get('title'):
                        titre_final = show_obj.get('title')
                        desc_finale = diffusion.get('title', diffusion.get('standFirst', ''))
                    else:
                        titre_final = diffusion.get('title', 'Direct')
                        desc_finale = diffusion.get('standFirst', '')
                elif 'title' in step:
                    titre_final = step.get('title')
            
            # Mise en cache et formatage des clés attendues par le Frontend
            rf_cache["data"] = {
                "show_title": titre_final,
                "show_desc": desc_finale,
                "show_image": "https://www.radiofrance.fr/build/images/logos/franceinter-1.svg"
            }
            rf_cache["time"] = time.time()
            return rf_cache["data"]
            
    except Exception as e:
        print(f"Erreur API Radio France: {e}")
        
    return None
    
@radio_bp.route('/api/radios/rf_test', methods=['GET'])
def test_rf_api():
    token = os.environ.get('RF_TOKEN')
    url = "https://openapi.radiofrance.fr/v1/graphql"
    
    # La requête parfaite basée sur ton introspection
    query = """
    query {
      live(station: FRANCEINTER) {
        show {
          ... on BlankStep {
            title
          }
          ... on DiffusionStep {
            diffusion {
              title
              standFirst
              show {
                title
              }
            }
          }
        }
      }
    }
    """
    
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
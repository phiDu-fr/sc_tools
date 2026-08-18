from flask import Blueprint, jsonify, request, send_from_directory
import os
import requests
import urllib.parse
import urllib.request
import json
import base64
import threading
import shared
from xml.sax.saxutils import escape
from werkzeug.utils import secure_filename

podcast_bp = Blueprint('podcast_bp', __name__)

# =========================================================================
# 1. MODULE RADIO FRANCE DOWNLOADER (Natif Flask)
# =========================================================================
# Transféré dans  rf_dwl.py
# =========================================================================
# 2. APPLE PODCASTS (EXISTANT)
# =========================================================================
@podcast_bp.route('/api/podcasts/search', methods=['GET'])
def search_podcast():
    query = request.args.get('q', '')
    if len(query) < 2: return jsonify([])
    try:
        params = {"term": query, "country": request.args.get('country', 'fr'), "entity": "podcastEpisode", "limit": 30}
        url = f"https://itunes.apple.com/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Soundtouch-Pi/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as response:
            data = json.loads(response.read().decode('utf-8'))
            return jsonify([{"title": item.get("trackName"), "emission": item.get("collectionName"), "url": item.get("episodeUrl") or item.get("previewUrl")} for item in data.get("results", []) if item.get("episodeUrl") or item.get("previewUrl")])
    except Exception as e: return jsonify({"error": str(e)}), 500

@podcast_bp.route('/local_podcast/<filename>')
def serve_local_podcast(filename):
    return send_from_directory(shared.DATA_PATH, filename)

@podcast_bp.route('/api/play_podcast', methods=['POST'])
def play_podcast():
    data = request.json
    local_filename = "podcast.mp3"
    try:
        r = requests.get(data.get('url'), headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=15)
        r.raise_for_status()
        with open(os.path.join(shared.DATA_PATH, local_filename), 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

    media_server_host = request.host.split(':')[0] 
    orion_data = {"name": data.get('name', 'Podcast'), "imageUrl": "", "streamUrl": f"http://{media_server_host}/local_podcast/{local_filename}"}
    b64 = base64.b64encode(json.dumps(orion_data, separators=(',', ':')).encode()).decode()
    xml_data = f'<?xml version="1.0" encoding="UTF-8"?><ContentItem source="LOCAL_INTERNET_RADIO" type="stationurl" location="http://{media_server_host}:{shared.SOUNDCORK_PORT}/core02/svc-bmx-adapter-orion/prod/orion/station?data={b64}"><itemName>{escape(data.get("name", "Podcast"))}</itemName></ContentItem>'

    for ip in data.get('ips', []):
        # --- FIX : Libération de la file DLNA ---
        if ip in shared.server_queues:
            shared.server_queues[ip] = {}
            
        try: requests.post(f"http://{ip}:8090/select", data=xml_data.encode('utf-8'), headers={"Content-Type": "text/xml; charset=utf-8"}, timeout=3.0)
        except: pass
    return jsonify({"status": "ok"})

# =========================================================================
# 3. LECTURE DES FICHIERS LOCAUX RF (EXISTANT)
# =========================================================================
@podcast_bp.route('/rf_podcast/<path:filename>')
def serve_rf_podcast(filename):
    return send_from_directory(shared.RF_PODCASTS_PATH, filename)

@podcast_bp.route('/api/local_rf_downloads', methods=['GET'])
def list_local_rf_downloads():
    if not os.path.exists(shared.RF_PODCASTS_PATH): return jsonify({})
    downloads = {}
    try:
        for show_dir in os.listdir(shared.RF_PODCASTS_PATH):
            dir_path = os.path.join(shared.RF_PODCASTS_PATH, show_dir)
            if os.path.isdir(dir_path):
                mp3s = [f for f in os.listdir(dir_path) if f.endswith('.mp3')]
                if mp3s: downloads[show_dir] = sorted(mp3s)
    except: pass
    return jsonify(downloads)

@podcast_bp.route('/api/play_local_rf', methods=['POST'])
def play_local_rf():
    data = request.json
    media_server_host = request.host.split(':')[0] 
    mp3_url = f"http://{media_server_host}/rf_podcast/{urllib.parse.quote(data.get('path'))}"
    
    orion_data = {"name": data.get('name', 'Podcast RF'), "imageUrl": "", "streamUrl": mp3_url}
    b64 = base64.b64encode(json.dumps(orion_data, separators=(',', ':')).encode()).decode()
    xml_data = f'<?xml version="1.0" encoding="UTF-8"?><ContentItem source="LOCAL_INTERNET_RADIO" type="stationurl" location="http://{media_server_host}:{shared.SOUNDCORK_PORT}/core02/svc-bmx-adapter-orion/prod/orion/station?data={b64}"><itemName>{escape(data.get("name", "Podcast RF"))}</itemName></ContentItem>'

    for ip in data.get('ips', []):
        # --- FIX : Libération de la file DLNA ---
        if ip in shared.server_queues:
            shared.server_queues[ip] = {}
            
        try: requests.post(f"http://{ip}:8090/select", data=xml_data.encode('utf-8'), headers={"Content-Type": "text/xml; charset=utf-8"}, timeout=3.0)
        except: pass
    return jsonify({"status": "ok"})
    
@podcast_bp.route('/api/delete_local_rf', methods=['POST'])
def delete_local_rf():
    data = request.json
    file_path = data.get('path')
    
    # Sécurité : empêcher de remonter dans les dossiers parents
    if not file_path or '..' in file_path:
        return jsonify({"status": "error", "message": "Chemin de fichier invalide"}), 400
        
    full_path = os.path.join(shared.RF_PODCASTS_PATH, file_path)
    
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
            
            # Nettoyage automatique : supprimer le dossier de l'émission s'il est maintenant vide
            folder_path = os.path.dirname(full_path)
            if not os.listdir(folder_path):
                os.rmdir(folder_path)
                
            return jsonify({"status": "ok"})
        else:
            return jsonify({"status": "error", "message": "Fichier introuvable"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@podcast_bp.route('/api/upload_play', methods=['POST'])
def upload_play():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "Aucun fichier reçu"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "Fichier invalide"}), 400

    ips_str = request.form.get('ips', '[]')
    try:
        ips = json.loads(ips_str)
    except:
        ips = []

    if not ips:
        return jsonify({"status": "error", "message": "Aucune enceinte ciblée"}), 400

    # Nettoie le nom de fichier (retire les accents et caractères spéciaux)
    filename = secure_filename(file.filename)
    
    # Écrase le précédent "upload" pour ne pas saturer la mémoire du Raspberry
    # On ajoute un préfixe pour le dissocier des podcasts iTunes
    temp_filename = f"upload_{filename}"
    filepath = os.path.join(shared.DATA_PATH, temp_filename)
    
    try:
        file.save(filepath)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur d'écriture disque: {str(e)}"}), 500

    media_server_host = request.host.split(':')[0] 
    
    # On exploite la route existante serve_local_podcast pour exposer le fichier à l'enceinte
    file_url = f"http://{media_server_host}/local_podcast/{urllib.parse.quote(temp_filename)}"

    # Utilisation du Hack Orion (idem que pour les webradios et podcasts)
    orion_data = {"name": file.filename, "imageUrl": "", "streamUrl": file_url}
    b64 = base64.b64encode(json.dumps(orion_data, separators=(',', ':')).encode()).decode()
    xml_data = f'<?xml version="1.0" encoding="UTF-8"?><ContentItem source="LOCAL_INTERNET_RADIO" type="stationurl" location="http://{media_server_host}:{shared.SOUNDCORK_PORT}/core02/svc-bmx-adapter-orion/prod/orion/station?data={b64}"><itemName>{escape(file.filename)}</itemName></ContentItem>'

    for ip in ips:
        # Libération de la file DLNA locale si elle était en cours de lecture
        if ip in shared.server_queues:
            shared.server_queues[ip] = {}
            
        try: 
            requests.post(f"http://{ip}:8090/select", data=xml_data.encode('utf-8'), headers={"Content-Type": "text/xml; charset=utf-8"}, timeout=3.0)
        except Exception as e: 
            print(f"Erreur d'envoi à {ip}: {e}")
            
    return jsonify({"status": "ok"})

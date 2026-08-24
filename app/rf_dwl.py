# /app/rf_dwl.py
import os
import re
import traceback
import threading
import dataclasses
import requests
from flask import Blueprint, jsonify, request
from radiofrance_downloader.api import RadioFranceAPI
from radiofrance_downloader.config import Config
from radiofrance_downloader.downloader import EpisodeDownloader
from radiofrance_downloader.models import StationId
from radiofrance_downloader.rss import RSSParser
import shared

# Initialisation du Blueprint isolé
rf_dwl_bp = Blueprint('rf_dwl_bp', __name__)

config = Config.load()
config.output_dir = shared.RF_PODCASTS_PATH 

api_key = os.environ.get('RF_TOKEN') or config.api_key
api = RadioFranceAPI(api_key) if api_key else None

downloader = EpisodeDownloader(output_dir=shared.RF_PODCASTS_PATH)

@rf_dwl_bp.route('/api/rf/config-check', methods=['GET'])
def check_config():
    return jsonify({"api_key_set": api is not None, "output_dir": shared.RF_PODCASTS_PATH})

@rf_dwl_bp.route('/api/rf/shows', methods=['GET'])
def search_shows():
    print(f"\n--- 📡 NOUVELLE RECHERCHE RADIO FRANCE ---")
    
    if not api:
        print("❌ CRASH : API non initialisée")
        return jsonify({"error": "API non initialisée"}), 500
        
    query = request.args.get('query', '')
    station = request.args.get('station', '')
    print(f"🔍 Paramètres reçus : query='{query}', station='{station}'")

    try:
        station_id = StationId(station.upper()) if station else None
        shows = api.search_shows(query, station=station_id)
        print(f"✅ Succès API : {len(shows)} émissions trouvées !")
        
        return jsonify([{
            "id": show.id,
            "title": show.title,
            "description": show.description,
            "url": show.url,
            "station": show.station.name if show.station else "Inconnue"
        } for show in shows])
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def safe_download_v9(ep, show_url):
    """Téléchargement V9 - Interception ciblée balises <audio> et format .m4a."""
    try:
        print(f"[V9-START] Début du traitement : {ep.title}")
        
        if not ep.audio_url:
            print(f"[V9-INFO] API muette. Analyse ciblée du code source de la page...")
            audio_url = None
            
            if ep.page_url:
                page_url = ep.page_url
                for d in ['franceinter.fr', 'franceculture.fr', 'franceinfo.fr', 'francemusique.fr', 'francebleu.fr', 'mouv.fr', 'fip.fr']:
                    page_url = page_url.replace(f"www.{d}", "www.radiofrance.fr")
                
                try:
                    r = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    
                    # 1. On cible spécifiquement la nouvelle balise <audio> de Radio France
                    m_audio = re.search(r'<audio[^>]*src=["\']([^"\']+)["\']', r.text)
                    if m_audio:
                        audio_url = m_audio.group(1).replace('\\/', '/')
                    else:
                        # 2. Secours : on cherche les .mp3 OU les nouveaux .m4a
                        m_ext = re.search(r'(https?://[^"\']+\.(?:mp3|m4a))', r.text)
                        if m_ext: 
                            audio_url = m_ext.group(1).replace('\\/', '/')
                except Exception as e:
                    print(f"[V9-WARNING] Analyse de la page a échoué : {e}")
            
            if audio_url:
                ep = dataclasses.replace(ep, audio_url=audio_url)
                print(f"[V9-SUCCESS-SCRAPER] URL Audio trouvée : {audio_url}")
            else:
                print(f"[V9-ERROR] Impossible de trouver l'audio (.mp3 ou .m4a) sur la page.")

        result = downloader.download_episode(ep)
        
        if result.success:
            if result.already_existed:
                print(f"[V9-INFO] Fichier déjà présent sur le SSD : {ep.title}")
            else:
                print(f"[V9-SUCCESS] Téléchargement terminé : {ep.title} ({result.file_size} octets)")
        else:
            print(f"[V9-ERROR] Échec final : {result.error}")
            
    except Exception as e:
        print(f"[V9-CRITICAL] Exception fatale : {e}")
        traceback.print_exc()

@rf_dwl_bp.route('/api/rf/download', methods=['POST'])
def download_episode():
    if not api:
        return jsonify({"error": "Clé API manquante"}), 500
    
    data = request.json or {}
    show_url = data.get('show_url')
    latest_n = int(data.get('latest_n', 1))
    
    if not show_url:
        return jsonify({"error": "URL manquante."}), 400
        
    try:
        print(f"[V9-INFO] Demande reçue pour : {show_url}")
        
        web_url = show_url
        for d in ['franceinter.fr', 'franceculture.fr', 'franceinfo.fr', 'francemusique.fr', 'francebleu.fr', 'mouv.fr', 'fip.fr']:
            web_url = web_url.replace(f"www.{d}", "www.radiofrance.fr")
            
        eps_to_download = []
        rss_url = None
        
        print(f"[V9-INFO] Interception du lien RSS officiel dans le HTML...")
        try:
            r = requests.get(web_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code == 200:
                # On cible leur nouveau format exact d'URL (podcast_UUID.xml)
                m_rss = re.search(r'href=["\'](https?://radiofrance-podcast\.net/[^"\']+\.xml)["\']', r.text)
                if m_rss:
                    rss_url = m_rss.group(1)
        except Exception as e:
            print(f"[V9-WARNING] Échec de la lecture HTML : {e}")

        if rss_url:
            print(f"[V9-SUCCESS] Flux RSS intercepté : {rss_url}")
            parser = RSSParser()
            try:
                all_eps = parser.fetch_episodes(rss_url)
                eps_to_download = all_eps[:latest_n]
                print(f"[V9-INFO] Épisodes extraits du flux RSS avec succès.")
            except Exception as e:
                print(f"[V9-WARNING] Lecture du flux RSS échouée ({e}).")
        
        if not eps_to_download:
            print(f"[V9-INFO] Bascule sur l'API GraphQL pour avoir au moins les titres...")
            base_eps, _ = api.get_show_episodes(show_url, fetch_all=False)
            if not base_eps:
                return jsonify({"error": "Aucun épisode trouvé."}), 404
            eps_to_download = base_eps[:latest_n]

        for ep in eps_to_download:
            print(f"[V9-INFO] Planification : {ep.title}")
            threading.Thread(target=safe_download_v9, args=(ep, web_url), daemon=True).start()
            
        return jsonify({"message": f"Téléchargement lancé !"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400
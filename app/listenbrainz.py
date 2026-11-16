import os
import requests
import time
import threading
from shared import speakers

LISTENBRAINZ_API_URL = "https://api.listenbrainz.org/1/submit-listens"

# Dictionnaire en mémoire pour mémoriser le dernier titre scrobblé par enceinte
# Format : { ip: { "artist": "...", "track": "..." } }
last_scrobbled = {}

def scrobble_track(ip, artist, track, release=None):
    """
    Envoie une écoute (listen) à l'API ListenBrainz si le titre a changé.
    """
    # Vérification de l'activation globale (désactivé si 'off', 'false', '0')
    lb_status = os.environ.get('LISTENBRAINZ', 'on').strip().lower()
    if lb_status in ['off', 'false', '0']:
        return False

    token = os.environ.get('LISTENBRAINZ_TOKEN', '').strip()
    if not token or token == "blabla-blabla-blabla-blabla":
        return False

    if not track or not artist:
        return False
        
    # Nettoyage des valeurs par défaut de l'API SoundTouch
    if track in ["Prêt", "Inconnu", ""] or artist in ["Inconnu", ""]:
        return False

    # Anti-doublon strict : si c'est exactement le même artiste et le même titre, on ignore
    if ip in last_scrobbled:
        last = last_scrobbled[ip]
        if last.get("track") == track and last.get("artist") == artist:
            return False

    now = time.time()
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "listen_type": "single",
        "payload": [
            {
                "listened_at": int(now),
                "track_metadata": {
                    "artist_name": artist,
                    "track_name": track,
                    "release_name": release or ""
                }
            }
        ]
    }
    
    try:
        resp = requests.post(LISTENBRAINZ_API_URL, json=payload, headers=headers, timeout=5)
        if resp.status_code in [200, 204]:
            print(f"[ListenBrainz] 🎵 Scrobble validé ({ip}) : {artist} - {track}")
            # Mémorisation du titre actuel pour éviter les envois répétés
            last_scrobbled[ip] = {
                "artist": artist,
                "track": track
            }
            return True
        else:
            print(f"[ListenBrainz] ❌ Erreur API ({resp.status_code}) : {resp.text}")
            return False
    except Exception as e:
        print(f"[ListenBrainz] ❌ Exception réseau : {e}")
        return False

def _listenbrainz_loop():
    """
    Boucle d'arrière-plan vérifiant l'état des enceintes toutes les 60 secondes.
    """
    while True:
        time.sleep(60)
        try:
            lb_status = os.environ.get('LISTENBRAINZ', 'on').strip().lower()
            if lb_status in ['off', 'false', '0']:
                continue

            for ip, spk in list(speakers.items()):
                if spk.get('state') == 'ON' and spk.get('playStatus') == 'PLAY_STATE':
                    artist = spk.get('artist', '')
                    track = spk.get('track', '')
                    album = spk.get('album', '')
                    
                    if artist and track:
                        scrobble_track(ip, artist, track, album)
        except Exception:
            pass

# Démarrage du thread d'arrière-plan ListenBrainz
threading.Thread(target=_listenbrainz_loop, daemon=True).start()
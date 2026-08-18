import requests
import os
import urllib.parse
import sys
import re

if len(sys.argv) < 2:
    print("Usage : python radio_logos.py <nom_de_la_radio>")
    sys.exit(1)

radio_name = sys.argv[1]
LOGOS_DIR = '/home/pi/tmp'
os.makedirs(LOGOS_DIR, exist_ok=True)

NAVIGATOR_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def clean_wikimedia_url(url):
    """
    Si l'URL vient de Wikimedia et demande une taille de miniature problématique,
    on la nettoie pour demander une taille standard ou l'image originale.
    """
    if "upload.wikimedia.org" in url and "/thumb/" in url:
        # Option la plus sûre : on descend à une taille standard de 500px souvent acceptée
        url_modifiee = re.sub(r'/\d+px-', '/500px-', url)
        return url_modifiee
    return url

def get_radio_browser_logo(radio_name):
    """ Tente de récupérer le logo sur les serveurs mondiaux de Radio-Browser """
    print(f"[Radio-Browser] Recherche de '{radio_name}'...")
    try:
        search_query = urllib.parse.quote(radio_name)
        url = f"https://de1.api.radio-browser.info/json/stations/byname/{search_query}"
        
        response = requests.get(url, headers=NAVIGATOR_HEADERS, timeout=4)
        if response.status_code == 200:
            data = response.json()
            valid_stations = [s for s in data if s.get('favicon') and s['favicon'].startswith('http')]
            if valid_stations:
                valid_stations.sort(key=lambda x: x.get('clickcount', 0), reverse=True)
                return valid_stations[0]['favicon']
    except Exception as e:
        print(f"[Radio-Browser] Erreur : {e}")
    return None

def get_itunes_clean_logo(radio_name):
    """ Fallback iTunes si Radio-Browser fait chou blanc """
    print(f"[iTunes Fallback] Recherche de '{radio_name}'...")
    try:
        search_query = urllib.parse.quote(radio_name)
        url = f"https://itunes.apple.com/search?term={search_query}&limit=10&country=fr"
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            if results:
                for item in results:
                    collection = item.get('collectionName', '').lower()
                    track = item.get('trackName', '').lower()
                    
                    if radio_name.lower() in collection or radio_name.lower() in track:
                        img_url = item.get('artworkUrl100') or item.get('artworkUrl600')
                        if img_url:
                            return img_url.replace("100x100", "600x600")
                
                return results[0].get('artworkUrl600') or results[0].get('artworkUrl100')
    except Exception as e:
        print(f"[iTunes Fallback] Erreur : {e}")
    return None

def fetch_live_radio_logo(radio_name):
    """ Centralise le téléchargement du logo de la station """
    if not radio_name:
        return None

    safe_name = "".join([c for c in radio_name if c.isalnum()]).lower()
    file_name = f"{safe_name}.jpg"
    local_file_path = os.path.join(LOGOS_DIR, file_name)
    frontend_path = f"/img/radios/{file_name}"

    if os.path.exists(local_file_path):
        print(f"[Cache] Logo déjà présent localement : {local_file_path}")
        return frontend_path

    # Étape 1 : Radio-Browser
    image_url = get_radio_browser_logo(radio_name)

    # Étape 2 : Fallback iTunes
    if not image_url:
        print("[Info] Logo non trouvé sur Radio-Browser, bascule sur iTunes...")
        image_url = get_itunes_clean_logo(radio_name)

    # Étape 3 : Téléchargement final avec nettoyage d'URL
    if image_url:
        # Nettoyage spécifique pour Wikimedia
        image_url = clean_wikimedia_url(image_url)
        
        try:
            print(f"[Téléchargement] Récupération de l'image : {image_url}")
            img_response = requests.get(image_url, headers=NAVIGATOR_HEADERS, timeout=5)
            img_response.raise_for_status()
            
            with open(local_file_path, 'wb') as handler:
                handler.write(img_response.content)
            
            print(f"[Succès] Logo de la station enregistré dans : {local_file_path}")
            return frontend_path
        except Exception as e:
            print(f"[Erreur] Échec du téléchargement physique de l'image : {e}")
    else:
        print(f"[Échec] Impossible de trouver un logo pour '{radio_name}'")

    return None

if __name__ == "__main__":
    chemin_frontend = fetch_live_radio_logo(radio_name)
    print("\n--- Résultat Final ---")
    if chemin_frontend:
        print(f"Chemin pour ton Frontend : {chemin_frontend}")
    else:
        print("Opération avortée.")
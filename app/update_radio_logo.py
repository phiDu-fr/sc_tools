import requests
import os
import urllib.parse
import json
import re

# ==========================================
# CONFIGURATION DE PRODUCTION
# ==========================================
LOGOS_CACHE_FILE = '/home/pi/sc_tools/data/radio_logos_cache.json' 
LOGOS_DIR = '/home/pi/sc_tools/www/img/radios' 

# User-Agent pour passer les sécurités des serveurs d'images
NAVIGATOR_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ==========================================
# FONCTIONS DE RECHERCHE (Par ordre de qualité)
# ==========================================

def get_itunes_clean_logo(radio_name):
    """ Priorité 1 : API iTunes (Haute résolution 600x600) """
    try:
        search_query = urllib.parse.quote(radio_name)
        url = f"https://itunes.apple.com/search?term={search_query}&limit=5&country=fr"
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            if results:
                # Cherche une correspondance exacte d'abord
                for item in results:
                    collection = item.get('collectionName', '').lower()
                    track = item.get('trackName', '').lower()
                    if radio_name.lower() in collection or radio_name.lower() in track:
                        img_url = item.get('artworkUrl100') or item.get('artworkUrl600')
                        if img_url:
                            return img_url.replace("100x100", "600x600")
                # Sinon prend le premier résultat
                return results[0].get('artworkUrl600') or results[0].get('artworkUrl100')
    except Exception:
        pass
    return None

def get_wikipedia_logo(radio_name):
    """ Priorité 2 : API Wikipédia (Logos officiels détourés) """
    try:
        # 1. Chercher la page Wikipedia de la radio
        search_query = urllib.parse.quote(radio_name + " radio")
        search_url = f"https://fr.wikipedia.org/w/api.php?action=query&list=search&srsearch={search_query}&utf8=&format=json&srlimit=1"
        r = requests.get(search_url, headers=NAVIGATOR_HEADERS, timeout=4)
        
        if r.status_code == 200 and r.json().get('query', {}).get('search'):
            title = r.json()['query']['search'][0]['title']
            
            # 2. Récupérer l'image principale de cette page (Taille 500px)
            img_url = f"https://fr.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(title)}&prop=pageimages&format=json&pithumbsize=500"
            r_img = requests.get(img_url, headers=NAVIGATOR_HEADERS, timeout=4)
            pages = r_img.json().get('query', {}).get('pages', {})
            
            for page_id, page_data in pages.items():
                if 'thumbnail' in page_data:
                    return page_data['thumbnail']['source']
    except Exception:
        pass
    return None

def get_radio_browser_logo(radio_name):
    """ Priorité 3 (Dernier recours) : Radio-Browser """
    try:
        search_query = urllib.parse.quote(radio_name)
        url = f"https://de1.api.radio-browser.info/json/stations/byname/{search_query}"
        response = requests.get(url, headers=NAVIGATOR_HEADERS, timeout=4)
        if response.status_code == 200:
            data = response.json()
            valid_stations = [s for s in data if s.get('favicon') and s['favicon'].startswith('http') and "default" not in s['favicon']]
            if valid_stations:
                valid_stations.sort(key=lambda x: x.get('clickcount', 0), reverse=True)
                return valid_stations[0]['favicon']
    except Exception:
        pass
    return None

def download_logo(radio_name, image_url):
    """ Télécharge l'image physiquement et retourne le chemin relatif pour le JSON """
    safe_name = "".join([c for c in radio_name if c.isalnum()]).lower()
    file_name = f"{safe_name}.jpg"
    local_file_path = os.path.join(LOGOS_DIR, file_name)
    json_target_address = f"/www/img/radios/{file_name}"

    try:
        img_response = requests.get(image_url, headers=NAVIGATOR_HEADERS, timeout=5)
        img_response.raise_for_status()
        
        with open(local_file_path, 'wb') as handler:
            handler.write(img_response.content)
        
        return json_target_address
    except Exception as e:
        print(f"  -> [Erreur Téléchargement] {e}")
        return None

# ==========================================
# MOTEUR PRINCIPAL (TRAITEMENT DU JSON)
# ==========================================
def process_cache_updates():
    if not os.path.exists(LOGOS_CACHE_FILE):
        print(f"[Erreur] Fichier JSON introuvable : {LOGOS_CACHE_FILE}")
        return

    os.makedirs(LOGOS_DIR, exist_ok=True)

    with open(LOGOS_CACHE_FILE, 'r', encoding='utf-8') as f:
        cache_data = json.load(f)

    print(f"📡 Analyse du cache : {len(cache_data)} stations trouvées...")
    has_changes = False

    for station_name, target_address in cache_data.items():
        if target_address == "FA_ICON" or target_address == "":
            print(f"\n🔍 Recherche requise pour : '{station_name}'")
            
            # CASCADE DE RECHERCHE : iTunes -> Wikipedia -> Radio-Browser
            img_url = get_itunes_clean_logo(station_name)
            
            if not img_url:
                print("  -> iTunes échoué, tentative Wikipédia...")
                img_url = get_wikipedia_logo(station_name)
                
            if not img_url:
                print("  -> Wikipédia échoué, tentative Radio-Browser...")
                img_url = get_radio_browser_logo(station_name)

            if img_url:
                new_target_address = download_logo(station_name, img_url)
                if new_target_address:
                    print(f"  ✅ Succès : {new_target_address}")
                    cache_data[station_name] = new_target_address
                    has_changes = True
            else:
                print(f"  ❌ Aucun logo trouvé. Conservé en l'état.")

    if has_changes:
        print("\n💾 Mise à jour du fichier JSON en cours...")
        with open(LOGOS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        print("🎉 Fichier mis à jour avec succès !")
    else:
        print("\n✨ Terminé. Le cache est déjà à jour, aucune action nécessaire.")

if __name__ == "__main__":
    process_cache_updates()
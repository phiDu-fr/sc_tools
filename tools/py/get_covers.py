import os
import re
import requests
import musicbrainzngs
from datetime import datetime
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3

# --- CONFIGURATION PRINCIPALE ---
MUSIC_DIR = "/home/pi/sc_tools/Music/mp3"
COVER_NAME = "Cover.jpg"
LOG_FILE = "/home/pi/sc_tools/Music/missing_covers.log"

# --- CONFIGURATION MUSICBRAINZ ---
musicbrainzngs.set_useragent("RaspberryPi_CoverFetcher", "2.1", "ton.email@exemple.com")
# -----------------------------

def clean_for_api(text):
    """Nettoie les parenthèses, crochets et caractères gênants pour les API."""
    if not text:
        return ""
    # 1. Enlever tout ce qui est entre () ou [] (ex: "(Live 73)", "[Deluxe Edition]")
    text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
    # 2. Remplacer les tirets et underscores par des espaces
    text = text.replace('_', ' ').replace('-', ' ')
    # 3. Enlever les apostrophes qui cassent parfois les recherches (ex: Somethin's)
    text = text.replace("'", "").replace("’", "")
    # 4. Supprimer les espaces en double
    return ' '.join(text.split()).strip()

def clean_artist_for_deezer(artist):
    """Ne garde que le premier artiste (Deezer ne trouve rien s'il y a des '&' ou des virgules)."""
    if not artist:
        return ""
    # Coupe la chaîne au premier séparateur trouvé (ignorer la casse pour and/et/feat/vs)
    artist = re.split(r'(?i)\s+&\s+|\s+and\s+|\s+et\s+|,\s*|\s+feat\.?\s+|\s+ft\.?\s+|\s+vs\.?\s+', artist)[0]
    return clean_for_api(artist)

def fetch_fallback_cover_deezer(artist, save_path):
    """Cherche l'artiste sur Deezer et télécharge sa photo (Format moyen/léger)."""
    search_url = "https://api.deezer.com/search/artist"
    params = {'q': artist, 'limit': 1}
    headers = {'User-Agent': 'RaspberryPi_CoverFetcher/2.1'}

    try:
        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('data'):
                img_url = data['data'][0].get('picture_medium')
                if img_url:
                    img_response = requests.get(img_url, headers=headers, timeout=10)
                    if img_response.status_code == 200:
                        with open(save_path, 'wb') as f:
                            f.write(img_response.content)
                        if os.getuid() == 0: 
                            try: os.chown(save_path, 1025, 100)
                            except Exception: pass
                        return True, "Succès (Deezer - Image moyenne)"
                    else:
                        return False, "Erreur lors du téléchargement de l'image Deezer"
                return False, "Artiste trouvé mais aucune photo disponible sur Deezer"
            return False, "Artiste introuvable sur Deezer"
        return False, f"Erreur API Deezer ({response.status_code})"
    except Exception as e:
        return False, f"Erreur Deezer : {e}"

def fetch_cover_art_musicbrainz(artist, album, save_path):
    """Cherche l'album sur MusicBrainz et télécharge la pochette allégée (500px)."""
    try:
        result = musicbrainzngs.search_releases(artist=artist, release=album, limit=1)
        if not result['release-list']:
            return False, "Album introuvable"

        release_id = result['release-list'][0]['id']
        
        caa_url_500 = f"http://coverartarchive.org/release/{release_id}/front-500"
        caa_url_raw = f"http://coverartarchive.org/release/{release_id}/front"

        response = requests.get(caa_url_500, allow_redirects=True, timeout=10)
        
        if response.status_code != 200:
            response = requests.get(caa_url_raw, allow_redirects=True, timeout=10)

        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            if os.getuid() == 0: 
                try: os.chown(save_path, 1025, 100)
                except Exception: pass
            return True, "Succès (MusicBrainz)"
        else:
            return False, f"Pas de pochette sur Cover Art Archive (HTTP {response.status_code})"
    except Exception as e:
        return False, f"Erreur MusicBrainz : {e}"

def get_album_info(folder_path):
    """Extrait l'artiste et l'album via les tags ID3."""
    for file in os.listdir(folder_path):
        if file.lower().endswith('.mp3'):
            try:
                audio = MP3(os.path.join(folder_path, file), ID3=EasyID3)
                artist = audio.get('artist', [''])[0]
                album = audio.get('album', [''])[0]
                if artist and album:
                    return artist, album
            except Exception:
                pass 
    return None, None

def get_info_from_path(folder_path, base_dir):
    """Extrait l'artiste et l'album via le nom des dossiers en prenant les deux DERNIERS dossiers."""
    rel_path = os.path.relpath(folder_path, base_dir)
    parts = rel_path.split(os.sep)
    if len(parts) >= 2:
        # On prend l'avant-dernier (-2) et le dernier (-1) pour gérer les dossiers profonds comme "Compil/Jazz/Artiste/Album"
        return parts[-2], parts[-1]
    return None, None

def main():
    if not os.path.exists(MUSIC_DIR):
        print(f"Erreur : Le dossier {MUSIC_DIR} n'existe pas.")
        return

    print(f"Début du scan dans {MUSIC_DIR}...")
    
    with open(LOG_FILE, 'a', encoding='utf-8') as log_f:
        log_f.write(f"\n{'='*40}\n--- Scan lancé le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n{'='*40}\n")

        for root, dirs, files in os.walk(MUSIC_DIR):
            dirs[:] = [d for d in dirs if d != '@eaDir']

            cover_path = os.path.join(root, COVER_NAME)
            has_mp3 = any(f.lower().endswith('.mp3') for f in files)

            if has_mp3 and not os.path.exists(cover_path):
                print(f"\n--- Dossier : {root}")
                artist, album = get_album_info(root)

                if not artist or not album:
                    artist, album = get_info_from_path(root, MUSIC_DIR)

                if not artist:
                    print("  -> ❌ Impossible d'identifier l'artiste (Dossier ignoré).")
                    continue
                
                print(f"  Dossier/Tag original : Artiste='{artist}' | Album='{album}'")
                
                # --- NETTOYAGE DES CHAÎNES POUR LES API ---
                search_artist_mb = clean_for_api(artist)
                search_album_mb = clean_for_api(album)
                search_artist_dz = clean_artist_for_deezer(artist)
                
                # PLAN A
                print(f"  [Plan A] Recherche pochette MusicBrainz ('{search_album_mb}')...")
                success, reason = fetch_cover_art_musicbrainz(search_artist_mb, search_album_mb, cover_path)
                
                if success:
                    print(f"  -> ✅ Pochette téléchargée avec succès !")
                else:
                    print(f"  -> ⚠️ Échec Plan A ({reason})")
                    
                    # PLAN B (DEEZER)
                    print(f"  [Plan B] Recherche photo de '{search_artist_dz}' sur Deezer...")
                    success_dz, reason_dz = fetch_fallback_cover_deezer(search_artist_dz, cover_path)
                    
                    if success_dz:
                        print(f"  -> ✅ Photo artiste téléchargée et nommée Cover.jpg !")
                    else:
                        print(f"  -> ❌ Échec Plan B ({reason_dz})")
                        log_f.write(f"[SANS POCHETTE] {root} | MB: {reason} | DZ: {reason_dz}\n")

        log_f.write("--- Fin du scan ---\n")
    print(f"\nScan terminé ! Consulte {LOG_FILE} pour les détails.")

if __name__ == "__main__":
    main()
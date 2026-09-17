#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import argparse
import requests
from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError


DISCOGS_API_URL = "https://api.discogs.com/database/search"
DEFAULT_MUSIC_DIR = "/home/pi/sc_tools/Music/mp3"
ENV_FILE_PATH = Path("/home/pi/sc_tools/.env")
USER_AGENT = "sc_tools_cover_fetcher/1.0"


def get_token_from_env() -> str:
    if not ENV_FILE_PATH.exists():
        print(f"[-] Erreur : Le fichier {ENV_FILE_PATH} est introuvable.")
        sys.exit(1)
        
    try:
        with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("discogs_TOKEN="):
                    token = line.split("=", 1)[1].strip(" '\"")
                    if token:
                        print(f"[+] Jeton Discogs chargé depuis {ENV_FILE_PATH}")
                        return token
                    else:
                        print("[-] Erreur : discogs_TOKEN est vide dans le .env.")
                        sys.exit(1)
    except Exception as e:
        print(f"[-] Erreur de lecture du .env : {e}")
        sys.exit(1)

    print("[-] Erreur : 'discogs_TOKEN=' introuvable dans le .env.")
    sys.exit(1)


def search_discogs_cover(artist: str, album: str, token: str) -> str | None:
    headers = {"User-Agent": USER_AGENT}
    params = {
        "artist": artist,
        "release_title": album,
        "type": "release",
        "token": token
    }
    
    try:
        response = requests.get(DISCOGS_API_URL, headers=headers, params=params, timeout=10)
        
        if response.status_code == 429:
            print("  [!] Rate limit atteint. Pause de 10 secondes...")
            time.sleep(10)
            return None
            
        response.raise_for_status()
        results = response.json().get("results", [])
        
        # Recherche par mots clés si la recherche stricte échoue
        if not results:
            params_broad = {
                "q": f"{artist} {album}",
                "type": "release",
                "token": token
            }
            res_broad = requests.get(DISCOGS_API_URL, headers=headers, params=params_broad, timeout=10)
            res_broad.raise_for_status()
            results = res_broad.json().get("results", [])

        if results:
            for res in results:
                cover_url = res.get("cover_image")
                # Exclure les images vides par défaut de Discogs
                if cover_url and "spacer.gif" not in cover_url:
                    return cover_url
                
    except requests.exceptions.RequestException as e:
        print(f"  [!] Erreur API : {e}")
        
    return None


def download_image(url: str, dest_path: Path, token: str) -> bool:
    headers = {
        "User-Agent": USER_AGENT,
        "Authorization": f"Discogs token={token}"
    }
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=15)
        response.raise_for_status()
        
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        print(f"  [!] Erreur de téléchargement de l'image : {e}")
        return False


def process_directories(base_dir: str, token: str, dry_run: bool = False) -> None:
    music_path = Path(base_dir)
    if not music_path.exists():
        print(f"[-] Le dossier {base_dir} n'existe pas.")
        sys.exit(1)

    # Récupérer tous les dossiers contenant au moins un .mp3
    target_dirs = set(mp3.parent for mp3 in music_path.rglob("*.mp3"))
    total_dirs = len(target_dirs)
    print(f"[+] {total_dirs} dossiers contenant des MP3 détectés dans {base_dir}\n")

    downloaded = 0
    skipped = 0

    for idx, d in enumerate(target_dirs, start=1):
        print(f"[{idx}/{total_dirs}] Analyse du dossier : {d}")
        cover_path = d / "Cover.jpg"
        
        if cover_path.exists():
            print("  [x] Cover.jpg existe déjà. Dossier ignoré.")
            skipped += 1
            continue

        # Récupération du premier MP3 pour lire les tags
        first_mp3 = next(d.glob("*.mp3"))
        
        try:
            audio = EasyID3(first_mp3)
        except ID3NoHeaderError:
            print("  [-] Tag ID3v2 absent sur le fichier d'échantillon.")
            skipped += 1
            continue
        except Exception as e:
            print(f"  [-] Erreur de lecture sur {first_mp3.name} : {e}")
            skipped += 1
            continue

        album = audio.get("album", [""])[0]
        # albumartist est plus pertinent pour les compilations, sinon artist
        artist = audio.get("albumartist", [""])[0] or audio.get("artist", [""])[0]

        if not album or not artist:
            print("  [-] Tags Artiste/Album manquants pour la recherche.")
            skipped += 1
            continue

        print(f"  -> Recherche Discogs pour : {artist} - {album}")
        cover_url = search_discogs_cover(artist, album, token)

        if cover_url:
            print(f"  [+] URL trouvée : {cover_url}")
            if not dry_run:
                if download_image(cover_url, cover_path, token):
                    print("  [+] Cover.jpg enregistré avec succès.")
                    downloaded += 1
                else:
                    skipped += 1
            else:
                print("  [*] Mode dry-run : Téléchargement simulé.")
        else:
            print("  [-] Aucune pochette correspondante trouvée.")
            skipped += 1

        # Pause pour respecter les limites de l'API Discogs (60 requêtes par minute)
        time.sleep(1.2)

    print("\n--- Bilan du traitement ---")
    print(f"Pochettes téléchargées : {downloaded}")
    print(f"Dossiers ignorés       : {skipped}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Téléchargement des pochettes (Cover.jpg) via Discogs")
    parser.add_argument("--dir", default=DEFAULT_MUSIC_DIR, help="Répertoire racine (par défaut: /home/pi/sc_tools/Music/mp3)")
    parser.add_argument("--dry-run", action="store_true", help="Simule la recherche sans télécharger les images")
    
    args = parser.parse_args()
    token = get_token_from_env()
    
    process_directories(args.dir, token, args.dry_run)


if __name__ == "__main__":
    main()
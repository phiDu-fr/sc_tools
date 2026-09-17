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


def get_token_from_env() -> str:
    """Extrait la valeur de discogs_TOKEN depuis le fichier .env."""
    if not ENV_FILE_PATH.exists():
        print(f"[-] Erreur : Le fichier {ENV_FILE_PATH} est introuvable.")
        sys.exit(1)
        
    try:
        with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Gère la présence de guillemets ou d'espaces autour de la valeur
                if line.startswith("discogs_TOKEN="):
                    token = line.split("=", 1)[1].strip(" '\"")
                    if token:
                        print(f"[+] Jeton Discogs chargé avec succès depuis {ENV_FILE_PATH}")
                        return token
                    else:
                        print("[-] Erreur : La variable discogs_TOKEN est vide dans le fichier .env.")
                        sys.exit(1)
                        
    except Exception as e:
        print(f"[-] Erreur lors de la lecture du fichier .env : {e}")
        sys.exit(1)

    print("[-] Erreur : La variable 'discogs_TOKEN=' n'a pas été trouvée dans le fichier .env.")
    sys.exit(1)


def get_discogs_broad_genre(artist: str, title: str, token: str) -> str | None:
    headers = {"User-Agent": "sc_tools_tagger/1.0"}
    params = {
        "artist": artist,
        "track": title,
        "type": "release",
        "token": token
    }
    
    try:
        response = requests.get(DISCOGS_API_URL, headers=headers, params=params, timeout=10)
        
        if response.status_code == 429:
            print("  [!] Rate limit atteint. Pause forcée de 10 secondes...")
            time.sleep(10)
            return None
            
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        
        if not results:
            params_broad = {
                "q": f"{artist} {title}",
                "type": "release",
                "token": token
            }
            res_broad = requests.get(DISCOGS_API_URL, headers=headers, params=params_broad, timeout=10)
            res_broad.raise_for_status()
            results = res_broad.json().get("results", [])

        if results:
            genres = results[0].get("genre", [])
            if genres:
                return genres[0]
                
    except requests.exceptions.RequestException as e:
        print(f"  [!] Erreur lors de la requête API : {e}")
        
    return None


def update_mp3_genres(directory: str, token: str, dry_run: bool = False) -> None:
    music_path = Path(directory)
    if not music_path.exists():
        print(f"[-] Le dossier {directory} n'existe pas.")
        sys.exit(1)

    mp3_files = list(music_path.rglob("*.mp3"))
    total_files = len(mp3_files)
    print(f"[+] {total_files} fichiers MP3 détectés dans {directory}\n")

    updated_count = 0
    skipped_count = 0

    for idx, file_path in enumerate(mp3_files, start=1):
        print(f"[{idx}/{total_files}] Analyse : {file_path.name}")
        
        try:
            audio = EasyID3(file_path)
        except ID3NoHeaderError:
            print("  [-] Tag ID3v2 absent ou corrompu. Fichier ignoré.")
            skipped_count += 1
            continue
        except Exception as e:
            print(f"  [-] Erreur de lecture : {e}")
            skipped_count += 1
            continue

        artist = audio.get("artist", [""])[0]
        title = audio.get("title", [""])[0]

        if not artist or not title:
            print("  [-] Tags Artiste ou Titre manquants. Recherche impossible.")
            skipped_count += 1
            continue

        current_genre = audio.get("genre", [""])[0]
        print(f"  -> Artiste : {artist} | Titre : {title}")
        print(f"  -> Genre actuel : {current_genre if current_genre else 'Aucun'}")

        broad_genre = get_discogs_broad_genre(artist, title, token)

        if broad_genre:
            print(f"  [+] Genre large Discogs : {broad_genre}")
            if not dry_run:
                audio["genre"] = broad_genre
                audio.save()
                print("  [+] Fichier mis à jour avec succès.")
                updated_count += 1
            else:
                print("  [*] Mode dry-run : Modification non appliquée.")
        else:
            print("  [-] Aucun résultat trouvé sur Discogs.")
            skipped_count += 1

        # Pause d'1,1s pour respecter le quota max de l'API Discogs (60 req/min)
        time.sleep(1.1)

    print("\n--- Bilan du traitement ---")
    print(f"Fichiers mis à jour : {updated_count}")
    print(f"Fichiers ignorés    : {skipped_count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mise à jour des genres ID3v2 via l'API Discogs")
    parser.add_argument("--dir", default=DEFAULT_MUSIC_DIR, help="Répertoire cible (par défaut: /home/pi/sc_tools/Music/mp3)")
    parser.add_argument("--dry-run", action="store_true", help="Exécute une simulation sans modifier les fichiers")
    
    args = parser.parse_args()
    
    # Chargement du jeton depuis le fichier .env
    token = get_token_from_env()
    
    # Lancement de la mise à jour
    update_mp3_genres(args.dir, token, args.dry_run)


if __name__ == "__main__":
    main()
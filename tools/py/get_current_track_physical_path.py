import sqlite3
import re
import requests
import xml.etree.ElementTree as ET

def get_current_track_physical_path(speaker_ip, minidlna_db_path):
    """
    Récupère le chemin physique du fichier actuellement joué sur une enceinte Bose SoundTouch
    en combinant l'API SoundTouch (port 8090) et la base SQLite de MiniDLNA.
    """
    # 1. Interrogation de l'API Bose SoundTouch
    try:
        response = requests.get(f"http://{speaker_ip}:8090/now_playing", timeout=3)
        if response.status_code != 200:
            return None, "Erreur de communication avec l'enceinte SoundTouch."
        
        # Parse du XML retourné par l'enceinte
        root = ET.fromstring(response.content)
        content_item = root.find(".//contentItem")
        
        if content_item is None:
            return None, "Aucun média en cours de lecture ou source non DLNA."
        
        media_url = content_item.get("location")
        if not media_url:
            return None, "L'élément en cours ne possède pas d'URL de localisation."
            
    except requests.RequestException as e:
        return None, f"Impossible de joindre l'enceinte : {e}"
    except ET.ParseError:
        return None, "Erreur de décodage XML de la réponse SoundTouch."

    # 2. Extraction de l'ID depuis l'URL MiniDLNA (ex: .../MediaItems/4522.mp3 -> 4522)
    match = re.search(r'/MediaItems/(\d+)', media_url)
    if not match:
        return None, f"L'URL ne correspond pas au format MiniDLNA attendu : {media_url}"
    
    media_id = match.group(1)
    
    # 3. Interrogation de la base SQLite de MiniDLNA
    try:
        conn = sqlite3.connect(minidlna_db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT PATH, TITLE, ARTIST, ALBUM FROM DETAILS WHERE ID = ?", (media_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None, f"ID MiniDLNA {media_id} introuvable dans la base de données."
            
        file_path, title, artist, album = row
        return {
            "path": file_path,
            "title": title,
            "artist": artist,
            "album": album,
            "url": media_url
        }, "Succès"
            
    except sqlite3.Error as e:
        return None, f"Erreur d'accès à la base SQLite MiniDLNA : {e}"

# Exemple d'utilisation dans ton daemon sc_tools
if __name__ == "__main__":
    SPEAKER_IP = "192.168.1.65"  # IP de ton enceinte SoundTouch
    MINIDLNA_DB = "/home/pi/sc_tools/dlna_cache/cache/files.db"
    
    if result:
        print(f"Fichier physique : {result['path']}")
        print(f"Titre : {result['artist']} - {result['title']} {result['album']}")
    else:
        print(f"Échec : {status}")
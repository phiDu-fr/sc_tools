"""Chemin réel du morceau diffusé + historique de « playlist_du_jour ».

Le WebSocket Bose ne donne pas le fichier, seulement titre / artiste / album et
l'URL de pochette (…/AlbumArt/<ALBUM_ART>-<DETAILS.ID>.jpg). On retrouve donc le
fichier dans la base MiniDLNA (files.db), ouverte en lecture seule.

- get_real_path(...)          -> chemin réel sur le Pi, pour speakers[ip]['file_path']
                                  (donc visible dans /api/data)
- record_playlist_listen(...) -> ajoute le chemin relatif à .played_history.txt
                                  (une ligne de m3u, même format que .all_tracks.txt)
"""
import os
import re
import sqlite3
import threading
from contextlib import closing
from urllib.parse import quote

PLAYLIST_NAME = "playlist_du_jour"

# Chemins vus depuis le conteneur sc_app (voir les volumes de docker-compose.yml)
MINIDLNA_DB = os.environ.get("MINIDLNA_DB", "/dlna_cache/cache/files.db")
HISTORY_FILE = os.environ.get("PLAYED_HISTORY_FILE", "/music_rw/.played_history.txt")

# Dans la base, MiniDLNA voit le dossier mp3 sous /media (MINIDLNA_MEDIA_DIR=A,/media)
MINIDLNA_MEDIA_PREFIX = "/media/"
# Même dossier, tel qu'il existe sur le Pi : sert à construire le « chemin réel »
HOST_MEDIA_DIR = os.environ.get("HOST_MEDIA_DIR", "/home/pi/sc_tools/Music/mp3")

_ART_RE = re.compile(r"/AlbumArt/(\d+)-(\d+)\.", re.IGNORECASE)
_lock = threading.Lock()
_last = {}   # ip -> (artiste, titre, album) du dernier morceau écrit dans l'historique
_cache = {}  # (artiste, titre, album, pochette) -> chemin relatif (succès uniquement)
_CACHE_MAX = 512


def _relative_path(db_path):
    """/media/Artiste/Album/01 - Titre.mp3  ->  Artiste/Album/01 - Titre.mp3"""
    if db_path and db_path.startswith(MINIDLNA_MEDIA_PREFIX):
        return db_path[len(MINIDLNA_MEDIA_PREFIX):]
    return None


def _query_db(artist, track, album, art_url, timeout):
    # Base ouverte à chaque appel (jamais gardée) : MiniDLNA la recrée après un rebuild.
    uri = f"file:{quote(MINIDLNA_DB)}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=timeout)) as db:
        # 1) ID exact via l'URL de pochette, contrôlé par le titre pour ne pas se fier
        #    aveuglément au format de l'URL.
        m = _ART_RE.search(art_url or "")
        if m:
            row = db.execute("SELECT PATH, TITLE FROM DETAILS WHERE ID = ?",
                             (int(m.group(2)),)).fetchone()
            if row and row[0] and (row[1] or "").strip().lower() == track.lower():
                return _relative_path(row[0])

        # 2) Repli : titre + album. En cas de doublon, on préfère le morceau présent dans
        #    la playlist, puis celui dont l'artiste correspond.
        row = db.execute(
            """SELECT d.PATH
               FROM DETAILS d
               WHERE d.PATH LIKE ? AND d.TITLE = ? AND COALESCE(d.ALBUM, '') = ?
               ORDER BY (d.ID IN (SELECT o.DETAIL_ID FROM OBJECTS o
                                  WHERE o.PARENT_ID IN (SELECT OBJECT_ID FROM OBJECTS
                                                        WHERE NAME = ? AND CLASS LIKE 'container%'))) DESC,
                        (d.ARTIST = ?) DESC
               LIMIT 1""",
            (MINIDLNA_MEDIA_PREFIX + "%", track, album, PLAYLIST_NAME, artist)).fetchone()
        return _relative_path(row[0]) if row else None


def _find_rel_path(artist, track, album, art_url, timeout=5):
    """Chemin relatif au dossier mp3, ou None. Lève sqlite3.Error si la base est illisible."""
    key = (artist.lower(), track.lower(), album.lower(), art_url or "")
    rel = _cache.get(key)
    if rel:
        return rel
    rel = _query_db(artist, track, album, art_url, timeout)
    if rel:
        if len(_cache) >= _CACHE_MAX:
            _cache.clear()
        _cache[key] = rel
    return rel


def get_real_path(artist, track, album, art_url=""):
    """Chemin réel du fichier sur le Pi (ex. /home/pi/sc_tools/Music/mp3/Artiste/Album/01.mp3).

    Renvoie '' si le morceau est introuvable ou si la base est indisponible. Ne lève jamais :
    appelé depuis le gestionnaire WebSocket, une exception y ferait perdre l'émission
    bose_update. Timeout court (1 s) pour ne pas bloquer ce gestionnaire.
    """
    track = (track or "").strip()
    if not track or track == "Prêt":
        return ""
    try:
        rel = _find_rel_path((artist or "").strip(), track, (album or "").strip(), art_url, timeout=1)
    except sqlite3.Error as e:
        print(f"[PlaylistHistory] Lecture MiniDLNA impossible : {e}")
        return ""
    return os.path.join(HOST_MEDIA_DIR, rel) if rel else ""


def _ends_with_newline(path):
    try:
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            return f.read(1) == b"\n"
    except OSError:  # fichier absent ou vide
        return True


def _append_line(rel_path):
    # Mode « a » : sans risque si sc_createM3u.sh vide le fichier (> $HISTORY_FILE) entre-temps.
    prefix = "" if _ends_with_newline(HISTORY_FILE) else "\n"
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{prefix}{rel_path}\n")


def record_playlist_listen(ip, artist, track, album, art_url=""):
    """Ajoute le morceau en cours à l'historique (sans doublon consécutif par enceinte)."""
    track = (track or "").strip()
    if not track or track == "Prêt":
        return
    artist, album = (artist or "").strip(), (album or "").strip()
    key = (artist.lower(), track.lower(), album.lower())

    with _lock:
        if _last.get(ip) == key:  # même morceau renvoyé par le WebSocket (buffering, pause, volume…)
            return
        _last[ip] = key
        try:
            rel = _find_rel_path(artist, track, album, art_url)
            if not rel:
                print(f"[PlaylistHistory] Fichier introuvable dans MiniDLNA : {artist} - {track} ({album})")
                return
            _append_line(rel)
            print(f"[PlaylistHistory] + {rel}")
        except (sqlite3.Error, OSError) as e:
            _last.pop(ip, None)  # on retentera au prochain message du WebSocket
            print(f"[PlaylistHistory] Erreur : {e}")

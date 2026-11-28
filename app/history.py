"""Historique d'écoute des enceintes Bose + chemin réel des morceaux locaux.

Le WebSocket Bose ne donne pas le fichier, seulement titre / artiste / album et
l'URL de pochette (…/AlbumArt/<ALBUM_ART>-<DETAILS.ID>.jpg). Le fichier est donc
retrouvé dans la base MiniDLNA (files.db), ouverte en lecture seule.

- record_listen(...)  -> à chaque nouveau morceau en lecture :
                           · écoute enregistrée dans SQLite (./data/history.db sur l'hôte
                             = /app/tools_data/ dans le conteneur), consultable via /api/history ;
                           · si la playlist « playlist_du_jour » est lue, chemin relatif du fichier
                             ajouté à .played_history.txt (une ligne de m3u, comme .all_tracks.txt)
- forget_speaker(ip)  -> à l'arrêt de l'enceinte : un même morceau relancé = nouvelle écoute
- get_real_path(...)  -> chemin réel sur le Pi, pour speakers[ip]['file_path'] (visible dans /api/data)
"""
import os
import re
import sqlite3
import threading
import time
from contextlib import closing
from urllib.parse import quote

from flask import Blueprint, jsonify, request

from shared import DATA_PATH, speakers

PLAYLIST_NAME = "playlist_du_jour"
ZONE_WINDOW = 120  # s : même morceau sur plusieurs enceintes (zone) = une seule écoute

DB_PATH = os.path.join(DATA_PATH, "history.db")

# Chemins vus depuis le conteneur sc_app (voir les volumes de docker-compose.yml)
MINIDLNA_DB = os.environ.get("MINIDLNA_DB", "/dlna_cache/cache/files.db")
PLAYED_FILE = os.environ.get("PLAYED_HISTORY_FILE", "/music_rw/.played_history.txt")

# Dans la base, MiniDLNA voit le dossier mp3 sous /media (MINIDLNA_MEDIA_DIR=A,/media)
MINIDLNA_MEDIA_PREFIX = "/media/"
# Même dossier, tel qu'il existe sur le Pi : sert à construire le « chemin réel »
HOST_MEDIA_DIR = os.environ.get("HOST_MEDIA_DIR", "/home/pi/sc_tools/Music/mp3")

_ART_RE = re.compile(r"/AlbumArt/(\d+)-(\d+)\.", re.IGNORECASE)
_CACHE_MAX = 512

history_bp = Blueprint("history", __name__)
_lock = threading.Lock()
_last = {}   # ip -> (artiste, titre, album) du dernier morceau enregistré
_cache = {}  # (artiste, titre, album, pochette) -> chemin relatif (succès uniquement)


# ---------------------------------------------------------------- base SQLite des écoutes

def _conn():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def _init():
    os.makedirs(DATA_PATH, exist_ok=True)
    with closing(_conn()) as db, db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS listens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listened_at INTEGER NOT NULL,          -- epoch UTC (secondes)
            artist TEXT NOT NULL DEFAULT '',
            album TEXT NOT NULL DEFAULT '',
            track TEXT NOT NULL,
            speakers TEXT NOT NULL DEFAULT '',     -- noms séparés par ', '
            source TEXT NOT NULL DEFAULT '',
            cover TEXT NOT NULL DEFAULT '')""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_listens_at ON listens(listened_at DESC)")


_init()


def _insert_listen(ip, artist, track, album, cover):
    spk = speakers.get(ip, {})
    name = spk.get("name") or ip
    now = int(time.time())
    with closing(_conn()) as db, db:
        row = db.execute(
            """SELECT id, speakers FROM listens
               WHERE artist=? COLLATE NOCASE AND album=? COLLATE NOCASE AND track=? COLLATE NOCASE
                 AND listened_at>=? ORDER BY listened_at DESC LIMIT 1""",
            (artist, album, track, now - ZONE_WINDOW)).fetchone()
        names = [n for n in row["speakers"].split(", ") if n] if row else []
        if row and name not in names:  # autre enceinte de la même zone
            db.execute("UPDATE listens SET speakers=? WHERE id=?",
                       (", ".join(names + [name]), row["id"]))
        else:
            db.execute(
                "INSERT INTO listens (listened_at, artist, album, track, speakers, source, cover) "
                "VALUES (?,?,?,?,?,?,?)",
                (now, artist, album, track, name, spk.get("source") or "", cover or ""))


# ---------------------------------------------------------------- fichier réel (MiniDLNA)

def _relative_path(db_path):
    """/media/Artiste/Album/01 - Titre.mp3  ->  Artiste/Album/01 - Titre.mp3"""
    if db_path and db_path.startswith(MINIDLNA_MEDIA_PREFIX):
        return db_path[len(MINIDLNA_MEDIA_PREFIX):]
    return None


def _find_rel_path(artist, track, album, art_url, timeout=5):
    """Chemin relatif au dossier mp3, ou None. Lève sqlite3.Error si la base est illisible."""
    key = (artist.lower(), track.lower(), album.lower(), art_url or "")
    rel = _cache.get(key)
    if rel:
        return rel

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
                rel = _relative_path(row[0])

        # 2) Repli : titre + album. En cas de doublon, on préfère le morceau présent dans
        #    la playlist, puis celui dont l'artiste correspond.
        if not rel:
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
            rel = _relative_path(row[0]) if row else None

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
        print(f"[Historique] Lecture MiniDLNA impossible : {e}")
        return ""
    return os.path.join(HOST_MEDIA_DIR, rel) if rel else ""


def _append_played(artist, track, album, cover):
    """Ajoute le chemin relatif du morceau à .played_history.txt."""
    rel = _find_rel_path(artist, track, album, cover)
    if not rel:
        print(f"[Historique] Fichier introuvable dans MiniDLNA : {artist} - {track} ({album})")
        return
    # Mode « a » : sans risque si sc_createM3u.sh vide le fichier (> $PLAYED_FILE) entre-temps.
    with open(PLAYED_FILE, "a+b") as f:
        prefix = b""
        if f.seek(0, os.SEEK_END):  # fichier non vide : finit-il bien par un saut de ligne ?
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                prefix = b"\n"
        f.write(prefix + rel.encode("utf-8") + b"\n")
    print(f"[Historique] + {rel}")


# ---------------------------------------------------------------- API appelée par le WebSocket

def forget_speaker(ip):
    """À appeler quand l'enceinte s'arrête : un même morceau relancé comptera comme une nouvelle écoute."""
    _last.pop(ip, None)


def record_listen(ip, artist, track, album, cover="", stored_music=False):
    """Enregistre le morceau en cours de lecture sur l'enceinte `ip` (sans doublon consécutif).

    `stored_music` : la source brute de l'enceinte est STORED_MUSIC (fichier servi par MiniDLNA).
    """
    track = (track or "").strip()
    if not track or track == "Prêt":
        return
    artist, album = (artist or "").strip(), (album or "").strip()
    key = (artist.lower(), track.lower(), album.lower())

    with _lock:
        if _last.get(ip) == key:  # mêmes infos renvoyées par la WebSocket (pause/reprise, volume…)
            return
        _last[ip] = key
        try:
            # Fichier d'abord : si MiniDLNA est illisible, rien n'est encore écrit et on retente.
            if stored_music and speakers.get(ip, {}).get("playlist") == PLAYLIST_NAME:
                _append_played(artist, track, album, cover)
            _insert_listen(ip, artist, track, album, cover)
        except (sqlite3.Error, OSError) as e:
            _last.pop(ip, None)  # on retentera au prochain message du WebSocket
            print(f"[Historique] Erreur : {e}")


# ---------------------------------------------------------------- consultation

@history_bp.route("/api/history")
def api_history():
    """?limit=50&offset=0&q=texte → écoutes, les plus récentes d'abord."""
    limit = min(max(request.args.get("limit", 50, type=int), 1), 200)
    offset = max(request.args.get("offset", 0, type=int), 0)
    q = (request.args.get("q") or "").strip()
    where, args = "", []
    if q:
        where = "WHERE artist LIKE ? OR album LIKE ? OR track LIKE ?"
        args = [f"%{q}%"] * 3
    with closing(_conn()) as db:
        total = db.execute(f"SELECT COUNT(*) FROM listens {where}", args).fetchone()[0]
        rows = db.execute(
            f"SELECT * FROM listens {where} ORDER BY listened_at DESC, id DESC LIMIT ? OFFSET ?",
            args + [limit, offset]).fetchall()
    return jsonify({"total": total, "items": [dict(r) for r in rows]})

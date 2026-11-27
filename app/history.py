"""Historique d'écoute façon ListenBrainz : tout ce que lisent les enceintes Bose
est enregistré dans SQLite (./data/history.db sur l'hôte = /app/tools_data/ dans le conteneur)."""
import os
import sqlite3
import threading
import time
from contextlib import closing

from flask import Blueprint, jsonify, request

from shared import DATA_PATH, speakers

DB_PATH = os.path.join(DATA_PATH, "history.db")
ZONE_WINDOW = 120  # s : même morceau sur plusieurs enceintes (zone) = une seule écoute

history_bp = Blueprint("history", __name__)
_lock = threading.Lock()
_last = {}  # ip -> (artiste, titre, album) du dernier morceau enregistré


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


def forget_speaker(ip):
    """À appeler quand l'enceinte s'arrête : un même morceau relancé comptera comme une nouvelle écoute."""
    _last.pop(ip, None)


def record_listen(ip, artist, track, album):
    """Enregistre le morceau en cours de lecture sur l'enceinte `ip` (sans doublon)."""
    track = (track or "").strip()
    if not track or track == "Prêt":
        return
    artist, album = (artist or "").strip(), (album or "").strip()
    spk = speakers.get(ip, {})
    name = spk.get("name") or ip
    key = (artist.lower(), track.lower(), album.lower())
    now = int(time.time())

    with _lock:
        if _last.get(ip) == key:  # mêmes infos renvoyées par la WebSocket (pause/reprise, volume…)
            return
        _last[ip] = key
        try:
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
                    return
                db.execute(
                    "INSERT INTO listens (listened_at, artist, album, track, speakers, source, cover) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (now, artist, album, track, name, spk.get("source") or "", spk.get("cover") or ""))
        except sqlite3.Error as e:
            _last.pop(ip, None)
            print(f"[Historique] Erreur SQLite : {e}")


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

"""Web API and GUI for radiofrance-downloader."""
# /home/pi/sc_tools/rf/app.py
import base64
import traceback
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

from radiofrance_downloader.api import RadioFranceAPI
from radiofrance_downloader.config import Config
from radiofrance_downloader.downloader import EpisodeDownloader
from radiofrance_downloader.models import StationId
from radiofrance_downloader.exceptions import RadioFranceError

app = FastAPI(title="Radio France Downloader", version="0.3.0")

# --- SERVIR LE FAVICON ---
@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(Path(__file__).parent / "favicon.ico")

# Chargement de la configuration globale
config = Config.load()
api = None
if config.api_key:
    api = RadioFranceAPI(config.api_key)

downloader = EpisodeDownloader(output_dir=config.output_dir)

@app.get("/api/config-check")
def check_config():
    """Vérifie l'état de la configuration."""
    return {"api_key_set": api is not None, "output_dir": config.output_dir}


@app.get("/api/shows")
def search_shows(query: str, station: str | None = None):
    """Recherche des émissions via l'API officielle."""
    if not api:
        raise HTTPException(status_code=500, detail="Clé API manquante dans votre config.json")
    
    station_id = StationId(station.upper()) if station else None
    try:
        shows = api.search_shows(query, station=station_id)
        return [{
            "id": show.id,
            "title": show.title,
            "description": show.description,
            "url": show.url,
            "station": show.station.name if show.station else "Inconnue"
        } for show in shows]
    except RadioFranceError as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- FONCTION WRAPPER POUR CAPTURER LES ERREURS ---
def safe_download(ep):
    """Encapsule le téléchargement pour afficher les erreurs dans les logs Docker."""
    try:
        print(f"[START] Début du téléchargement : {ep.title}")
        downloader.download_episode(ep)
        print(f"[SUCCESS] Téléchargement terminé : {ep.title}")
    except Exception as e:
        print(f"[ERROR] Échec du téléchargement pour '{ep.title}' : {e}")
        print(traceback.format_exc())  # Affiche la trace complète de l'erreur dans les logs

@app.post("/api/download")
def download_episode(show_url: str, background_tasks: BackgroundTasks, latest_n: int = 1):
    """Déclenche le téléchargement du/des derniers épisodes en tâche de fond."""
    if not api:
        raise HTTPException(status_code=500, detail="Clé API manquante")
    try:
        # On récupère les épisodes de l'émission
        eps, _ = api.get_show_episodes(show_url, fetch_all=False)
        eps_to_download = eps[:latest_n]
        if not eps_to_download:
            raise HTTPException(status_code=404, detail="Aucun épisode trouvé.")

        for ep in eps_to_download:
            print(f"[INFO] Planification du téléchargement : {ep.title}")
            # On utilise le wrapper safe_download au lieu de downloader.download_episode
            background_tasks.add_task(safe_download, ep)
            
        return {"message": f"Téléchargement de {len(eps_to_download)} épisode(s) lancé en arrière-plan ! Consultez les logs Docker."}
    except RadioFranceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/downloads")
def list_downloads():
    """Scanne le dossier racine pour lister les podcasts déjà téléchargés."""
    path = Path(config.output_dir)
    if not path.exists():
        return {}
    
    downloads = {}
    try:
        for show_dir in path.iterdir():
            if show_dir.is_dir():
                mp3_files = [f.name for f in show_dir.glob("*.mp3")]
                if mp3_files:
                    downloads[show_dir.name] = sorted(mp3_files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du scan du dossier : {e}")
    return downloads

# --- NOUVELLE ROUTE : SUPPRESSION D'UN FICHIER ---
@app.delete("/api/downloads")
def delete_download(show: str, filename: str):
    """Supprime physiquement un fichier mp3 du disque."""
    # Sécurité basique pour éviter la remontée d'arborescence
    if ".." in show or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Chemin invalide.")
    
    target_dir = Path(config.output_dir) / show
    target_file = target_dir / filename
    
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
        
    try:
        target_file.unlink() # Suppression du fichier
        # Si le dossier de l'émission est désormais vide, on le supprime aussi
        if not any(target_dir.iterdir()):
            target_dir.rmdir()
        return {"message": "Fichier supprimé avec succès."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression : {e}")


@app.get("/", response_class=HTMLResponse)
def index():
    """Sert l'interface graphique HTML/JS."""
    html_content = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Radio France Downloader</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #f4f6f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            .card { border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.04); border-radius: 12px; }
            .station-badge { font-size: 0.75rem; padding: 0.4em 0.8em; border-radius: 20px; background-color: #e9ecef; color: #495057; font-weight: 600; }
            .accordion-button:not(.collapsed) { background-color: #e7f1ff; color: #0c63e4; }
            .list-group-item { border-left: none; border-right: none; }
            .card-hover { transition: transform 0.2s; }
            .card-hover:hover { transform: translateY(-2px); }
            /* Effet sur le bouton de suppression */
            .btn-delete:hover { background-color: #dc3545; color: white !important; }
        </style>
    </head>
    <body>
        <div class="container py-4">
            <header class="pb-3 mb-4 border-bottom d-flex justify-content-between align-items-center">
                <span class="fs-4 fw-bold text-dark">📻 Radio France <span class="text-primary">Downloader</span></span>
                <span id="config-status" class="badge bg-secondary">Vérification...</span>
            </header>

            <div class="row g-4">
                <div class="col-lg-6">
                    <div class="card p-4 mb-4">
                        <h5 class="fw-bold mb-3">Rechercher un Podcast</h5>
                        <div class="input-group mb-3">
                            <input type="text" id="search-input" class="form-control" placeholder="Ex: Affaires sensibles...">
                            <select id="station-select" class="form-select" style="max-width: 150px;">
                                <option value="">Toutes radios</option>
                                <option value="FRANCEINTER">France Inter</option>
                                <option value="FRANCECULTURE">France Culture</option>
                                <option value="FRANCEINFO">franceinfo</option>
                                <option value="FRANCEBLEU">France Bleu</option>
                                <option value="FRANCEMUSIQUE">France Musique</option>
                                <option value="FIP">FIP</option>
                                <option value="MOUV">Mouv'</option>
                            </select>
                            <button class="btn btn-primary" type="button" id="search-btn">Chercher</button>
                        </div>
                        <div id="search-results" class="mt-2"></div>
                    </div>
                </div>

                <div class="col-lg-6">
                    <div class="card p-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold mb-0">Bibliothèque Locale</h5>
                            <button class="btn btn-sm btn-outline-primary" id="refresh-downloads-btn">🔄 Actualiser</button>
                        </div>
                        <div id="downloads-list" class="accordion">
                            <p class="text-muted text-center my-4">Chargement de votre bibliothèque...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Statut de la clé au chargement
            fetch('/api/config-check')
                .then(r => r.json())
                .then(data => {
                    const status = document.getElementById('config-status');
                    if(data.api_key_set) {
                        status.textContent = "Configuration OK";
                        status.className = "badge bg-success";
                    } else {
                        status.textContent = "Clé API absente";
                        status.className = "badge bg-danger";
                    }
                });

            // Gestion de la recherche
            document.getElementById('search-btn').addEventListener('click', performSearch);
            document.getElementById('search-input').addEventListener('keypress', (e) => {
                if(e.key === 'Enter') performSearch();
            });

            function performSearch() {
                const query = document.getElementById('search-input').value.trim();
                const station = document.getElementById('station-select').value;
                if(!query) return;
                
                const container = document.getElementById('search-results');
                container.innerHTML = '<div class="text-center p-4"><div class="spinner-border text-primary" role="status"></div></div>';
                
                let url = `/api/shows?query=${encodeURIComponent(query)}`;
                if (station) {
                    url += `&station=${encodeURIComponent(station)}`;
                }
                
                fetch(url)
                    .then(r => r.json())
                    .then(shows => {
                        container.innerHTML = '';
                        if(!shows || shows.length === 0 || shows.detail) {
                            container.innerHTML = '<div class="alert alert-light text-center border">Aucune émission trouvée. Essayez une autre recherche.</div>';
                            return;
                        }
                        shows.forEach((show, index) => {
                            const div = document.createElement('div');
                            div.className = 'p-3 mb-3 border rounded bg-white card-hover';
                            const b64Url = btoa(unescape(encodeURIComponent(show.url)));
                            
                            div.innerHTML = `
                                <div class="d-flex justify-content-between align-items-start mb-2">
                                    <h6 class="mb-0 fw-bold text-dark">${show.title}</h6>
                                    <span class="station-badge">${show.station}</span>
                                </div>
                                <p class="text-muted small mb-3">${show.description || 'Aucune description disponible.'}</p>
                                
                                <div class="d-flex gap-2">
                                    <select id="count-${index}" class="form-select form-select-sm" style="max-width: 130px;">
                                        <option value="1">1 seul (dernier)</option>
                                        <option value="3">3 derniers</option>
                                        <option value="5">5 derniers</option>
                                        <option value="10">10 derniers</option>
                                        <option value="15">15 derniers</option>
                                    </select>
                                    <button class="btn btn-sm btn-success flex-grow-1" onclick="downloadLatest('${b64Url}', 'count-${index}')">⚡ Télécharger</button>
                                </div>
                            `;
                            container.appendChild(div);
                        });
                    }).catch(() => {
                        container.innerHTML = '<div class="alert alert-danger">Erreur serveur lors de la recherche.</div>';
                    });
            }

            function downloadLatest(b64Url, selectId) {
                const url = decodeURIComponent(escape(atob(b64Url)));
                const count = document.getElementById(selectId).value;
                
                fetch(`/api/download?show_url=${encodeURIComponent(url)}&latest_n=${count}`, { method: 'POST' })
                    .then(r => r.json())
                    .then(data => {
                        alert(data.message || data.detail);
                        setTimeout(loadLocalDownloads, 4000);
                    });
            }

            // Charger et afficher la liste des fichiers locaux
            function loadLocalDownloads() {
                const container = document.getElementById('downloads-list');
                fetch('/api/downloads')
                    .then(r => r.json())
                    .then(data => {
                        container.innerHTML = '';
                        const showNames = Object.keys(data);
                        if(showNames.length === 0) {
                            container.innerHTML = '<p class="text-muted text-center my-4">Aucun podcast trouvé dans le dossier.</p>';
                            return;
                        }
                        
                        showNames.forEach((name, idx) => {
                            const files = data[name];
                            const item = document.createElement('div');
                            item.className = 'accordion-item mb-2 border rounded-3 overflow-hidden';
                            
                            const fileListHTML = files.map(f => {
                                const encName = encodeURIComponent(name);
                                const encFile = encodeURIComponent(f);
                                return `
                                <li class="list-group-item d-flex align-items-center justify-content-between bg-transparent py-2">
                                    <div class="d-flex align-items-center text-truncate me-2">
                                        <span class="me-2">🎵</span>
                                        <span class="text-dark small text-truncate" title="${f}">${f}</span>
                                    </div>
                                    <button class="btn btn-sm btn-outline-secondary border-0 btn-delete flex-shrink-0" onclick="deleteFile('${encName}', '${encFile}')" title="Supprimer le fichier">🗑️</button>
                                </li>
                                `;
                            }).join('');

                            item.innerHTML = `
                                <h2 class="accordion-header" id="heading-${idx}">
                                    <button class="accordion-button collapsed fw-bold py-3" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-${idx}">
                                        📁 &nbsp; ${name} <span class="badge bg-secondary ms-2 rounded-pill">${files.length}</span>
                                    </button>
                                </h2>
                                <div id="collapse-${idx}" class="accordion-collapse collapse" data-bs-parent="#downloads-list">
                                    <div class="accordion-body p-0 bg-white">
                                        <ul class="list-group list-group-flush mb-0">
                                            ${fileListHTML}
                                        </ul>
                                    </div>
                                </div>
                            `;
                            container.appendChild(item);
                        });
                    }).catch(() => {
                        container.innerHTML = '<p class="text-danger text-center my-4">Impossible de charger la bibliothèque locale.</p>';
                    });
            }
            
            // Fonction de suppression
            function deleteFile(encShow, encFilename) {
                if(!confirm("Êtes-vous sûr de vouloir supprimer ce podcast du Raspberry Pi ?")) return;
                
                const show = decodeURIComponent(encShow);
                const filename = decodeURIComponent(encFilename);
                
                fetch(`/api/downloads?show=${encodeURIComponent(show)}&filename=${encodeURIComponent(filename)}`, {
                    method: 'DELETE'
                })
                .then(r => r.json())
                .then(data => {
                    if (data.detail) {
                        alert("Erreur : " + data.detail);
                    } else {
                        // Recharger la liste si la suppression a réussi
                        loadLocalDownloads();
                    }
                })
                .catch(err => alert("Erreur réseau lors de la suppression."));
            }

            document.getElementById('refresh-downloads-btn').addEventListener('click', loadLocalDownloads);
            loadLocalDownloads();
        </script>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return html_content
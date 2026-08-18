from flask import Flask, send_from_directory
import threading
import json
import os

# --- Importation des composants isolés ---
from shared import scheduler, JSON_FILE, DATA_PATH, socketio, speakers 
from soundtouch_api import soundtouch_bp, parse_device_info, check_stereo_groups
from dlna import dlna_bp
from radios import radio_bp, load_radios
from podcasts import podcast_bp
from alarms import alarm_bp, sync_alarms_to_scheduler
from tools import tools_bp
from rf_dwl import rf_dwl_bp
from bose_websocket import bose_ws_manager 

# Initialisation de l'application
app = Flask(__name__, static_folder='/app/www')
socketio.init_app(app) 

# "Branchement" des Blueprints
app.register_blueprint(soundtouch_bp)
app.register_blueprint(dlna_bp)
app.register_blueprint(radio_bp)
app.register_blueprint(podcast_bp)
app.register_blueprint(alarm_bp)
app.register_blueprint(tools_bp)
app.register_blueprint(rf_dwl_bp)

# Fichiers statiques et page d'accueil
@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('www', filename)

@app.route('/')
def index():
    return send_from_directory('www', 'index.html')

def init_db():
    """Crée les dossiers au démarrage si besoin"""
    if not os.path.exists(DATA_PATH): 
        os.makedirs(DATA_PATH, exist_ok=True)
    if not os.path.exists(JSON_FILE):
        with open(JSON_FILE, "w") as f: json.dump([], f)

if __name__ == '__main__':
    # Initialisations
    init_db()
    parse_device_info()
    load_radios()
    
    # Détection des groupes stéréo (Bose SoundTouch 10)
    check_stereo_groups()
    
    # Lancement des tâches planifiées (Alarmes)
    scheduler.start()
    with open(JSON_FILE, 'r') as f:
        sync_alarms_to_scheduler(json.load(f))
        
    # Lancement de l'écoute WebSocket absolue pour chaque enceinte détectée
    for ip, info in speakers.items():
        if not info.get('is_stereo_slave'):
            print(f"Démarrage de l'écoute WS pour l'enceinte {ip}")
            bose_ws_manager.start_listening(ip)
        else:
            print(f"Ignoré (Esclave stéréo ST-10) : {ip}")
    
    # Lancement du serveur Web via SocketIO
    print("Démarrage du serveur temps réel sur le port 80...")
    socketio.run(app, host='0.0.0.0', port=80, allow_unsafe_werkzeug=True)
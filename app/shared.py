import os
from apscheduler.schedulers.background import BackgroundScheduler
from flask_socketio import SocketIO

# Variables d'environnement et ports
SOUNDCORK_PORT = os.environ.get('SOUNDCORK_PORT', '8000')

# Chemins de données
DATA_PATH = "/app/tools_data"
DATA_SOUNDCORK = "/data"
RADIOS_FILE = os.path.join(DATA_PATH, "radios.json")
JSON_FILE = os.path.join(DATA_PATH, "alarms.json")
TOOLS_CONFIG_PATH = os.path.join(DATA_PATH, 'config_tools.ini')
RF_PODCASTS_PATH = "/app/rf_podcasts"

# États partagés en mémoire
speakers = {}
speaker_last_states = {}
server_queues = {}
radios_list = []
dlna_servers_cache = {}

# Moteur de tâches de fond
scheduler = BackgroundScheduler()

# NOUVEAU : Instance serveur WebSockets pour communiquer avec app.js en temps réel
socketio = SocketIO(cors_allowed_origins="*")
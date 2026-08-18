# Documentation des codes sources
Généré le \2026-\08-\18 \15:\15:\26

## Arborescence du projet

```text
.
├── app
│   ├── alarms.py
│   ├── app.py
│   ├── bose_websocket.py
│   ├── dlna.py
│   ├── podcasts.py
│   ├── radiofrance_downloader
│   │   ├── api.py
│   │   ├── app.py
│   │   ├── cli.py
│   │   ├── config.py
│   │   ├── downloader.py
│   │   ├── exceptions.py
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── models.py
│   │   ├── rss.py
│   │   └── scraper.py
│   ├── radios.py
│   ├── rf_dwl.py
│   ├── shared.py
│   ├── soundtouch_api.py
│   ├── tools.py
│   ├── update_radio_logo.py
│   ├── utils.py
│   └── virtual_soundtouch.py
├── docker-compose.yml
├── Dockerfile
└── www
    ├── alarm.html
    ├── components
    │   ├── footer.html
    │   └── sidebar.html
    ├── config.html
    ├── css
    │   └── global.css
    ├── dlna_browser.html
    ├── dlna.html
    ├── index.html
    ├── js
    │   ├── app.js
    │   └── player.js
    ├── now.html
    ├── player.html
    ├── podcasts.html
    ├── radios.html
    ├── remote.html
    ├── tools.html
    └── upload.html

7 directories, 43 files
```
<br>

---

## Fichiers sources

### `app/alarms.py`

```python
from flask import Blueprint, jsonify, request
import json
import time
import requests
from apscheduler.triggers.cron import CronTrigger

import shared

alarm_bp = Blueprint('alarm_bp', __name__)

def trigger_bose_alarm(ip, preset):
    print(f"⏰ [ALARM] Déclenchement sur {ip} avec le {preset} !")
    try:
        requests.post(f"http://{ip}:8090/volume", data='<volume>25</volume>', headers={"Content-Type": "application/xml"}, timeout=2)
        time.sleep(1)
        requests.post(f"http://{ip}:8090/key", data=f'<key state="release" sender="Gabbo">{preset}</key>'.encode('utf-8'), headers={"Content-Type": "application/xml"}, timeout=2)
    except Exception as e: print(f"❌ Erreur alarme: {e}")

def sync_alarms_to_scheduler(alarms):
    for job in shared.scheduler.get_jobs(): shared.scheduler.remove_job(job.id)
    day_map = {"0": "sun", "1": "mon", "2": "tue", "3": "wed", "4": "thu", "5": "fri", "6": "sat"}
    for idx, a in enumerate(alarms):
        ap_days = ",".join([day_map[d.strip()] for d in a['days'].split(',') if d.strip() in day_map])
        trigger = CronTrigger(minute=a['minute'], hour=a['hour'], day_of_week=ap_days, timezone="Europe/Paris")
        shared.scheduler.add_job(func=trigger_bose_alarm, trigger=trigger, args=[a['ip'], a['preset']], id=f"alarm_{idx}")

@alarm_bp.route('/api/alarms', methods=['GET', 'POST', 'DELETE'])
def manage_alarms():
    if request.method == 'GET':
        try:
            with open(shared.JSON_FILE, 'r') as f: return jsonify(json.load(f))
        except: return jsonify([])
        
    if request.method == 'POST':
        try:
            with open(shared.JSON_FILE, 'r') as f: alarms = json.load(f)
        except: alarms = []
        alarms.append(request.json)
        with open(shared.JSON_FILE, 'w') as f: json.dump(alarms, f, indent=4)
        sync_alarms_to_scheduler(alarms)
        return jsonify({"status": "success"})
        
    if request.method == 'DELETE':
        idx = int(request.args.get('index', -1))
        try:
            with open(shared.JSON_FILE, 'r') as f: alarms = json.load(f)
            if 0 <= idx < len(alarms):
                alarms.pop(idx)
                with open(shared.JSON_FILE, 'w') as f: json.dump(alarms, f, indent=4)
                sync_alarms_to_scheduler(alarms)
                return jsonify({"status": "success"})
        except: pass
        return jsonify({"status": "error"}), 400
```
<br>

### `app/app.py`

```python
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
```
<br>

### `app/bose_websocket.py`

```python
import websocket
import threading
import xml.etree.ElementTree as ET
from shared import speakers, socketio
import requests
import time
import radios

class BoseWebsocketManager:
    def __init__(self):
        self.active_connections = {}

    def fetch_initial_state(self, ip):
        try:
            # On utilise une Session pour réutiliser la connexion TCP (Keep-Alive)
            # Cela évite de saturer le serveur web de la Bose (bug du port 8090)
            with requests.Session() as session:
                resp_np = session.get(f"http://{ip}:8090/nowPlaying", timeout=5.0)
                if resp_np.status_code == 200:
                    self.parse_and_emit(ip, resp_np.text)
                
                time.sleep(0.1)
                resp_vol = session.get(f"http://{ip}:8090/volume", timeout=5.0)
                if resp_vol.status_code == 200:
                    self.parse_and_emit(ip, resp_vol.text)
                    
                time.sleep(0.1)
                resp_zone = session.get(f"http://{ip}:8090/getZone", timeout=5.0)
                if resp_zone.status_code == 200:
                    zone_root = ET.fromstring(resp_zone.text)
                    master_id = zone_root.attrib.get('master')
                    
                    device_id = speakers.get(ip, {}).get('deviceID')
                    if not device_id:
                        time.sleep(0.1)
                        resp_info = session.get(f"http://{ip}:8090/info", timeout=5.0)
                        if resp_info.status_code == 200:
                            device_id = ET.fromstring(resp_info.text).attrib.get('deviceID')
                            if device_id: device_id = device_id.upper()
                            if ip not in speakers: speakers[ip] = {}
                            speakers[ip]['deviceID'] = device_id
                    
                    if ip not in speakers: speakers[ip] = {}
                    speakers[ip]['is_zone_master'] = bool(master_id and device_id and master_id == device_id)

                time.sleep(0.1)
                resp_power = session.get(f"http://{ip}:8090/powerManagement", timeout=5.0)
                if resp_power.status_code == 200:
                    self.parse_and_emit(ip, resp_power.text)
                
            from shared import socketio
            socketio.emit('bose_update', {'speakers': speakers})
        except Exception:
            pass

    def start_listening(self, ip):
        if ip in self.active_connections:
            return

        self.active_connections[ip] = "starting"

        def ws_worker():
            self.fetch_initial_state(ip)

            def on_message(ws, message):
                self.parse_and_emit(ip, message)

            def on_error(ws, error):
                pass

            def on_close(ws, close_status_code, close_msg):
                pass

            def on_open(ws):
                self.fetch_initial_state(ip)

            ws_url = f"ws://{ip}:8080/"
            custom_headers = ["Sec-WebSocket-Protocol: gabbo"]
            
            ws = websocket.WebSocketApp(
                ws_url,
                header=custom_headers,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )

            self.active_connections[ip] = ws
            ws.run_forever()
            
            self.active_connections.pop(ip, None)
            
            time.sleep(15)
            self.start_listening(ip)

        threading.Thread(target=ws_worker, daemon=True).start()

    def stop_listening(self, ip):
        ws = self.active_connections.pop(ip, None)
        if ws and hasattr(ws, 'close'):
            ws.close()

    def parse_and_emit(self, ip, xml_message):
        try:
            root = ET.fromstring(xml_message)
            if ip not in speakers:
                speakers[ip] = {}
                
            updated = False

            power_node = root if root.tag in ['powerManagementResponse', 'powerManagementUpdated'] else root.find('.//powerManagementUpdated') or root.find('.//powerManagementResponse')
            if power_node is not None:
                battery_node = power_node.find('.//battery')
                if battery_node is not None:
                    capable = (battery_node.findtext('capable') == 'true')
                    speakers[ip]['battery_capable'] = capable
                    if capable:
                        pct_str = battery_node.findtext('percentCharge')
                        speakers[ip]['battery_percent'] = int(pct_str) if pct_str else 0
                        run_batt_str = battery_node.findtext('runningOnBattery')
                        speakers[ip]['running_on_battery'] = (run_batt_str == 'true')
                    updated = True

            if root.find('.//nowSelectionUpdated') is not None:
                import shared
                if hasattr(shared, 'server_queues') and ip in shared.server_queues:
                    shared.server_queues[ip] = {} 
                    
            zone_updated = root.find('.//zoneUpdated')
            if zone_updated is not None:
                zone_node = zone_updated.find('zone')
                if zone_node is not None:
                    master_id = zone_node.attrib.get('master')
                    device_id = root.attrib.get('deviceID')
                    if device_id: device_id = device_id.upper()
                    if not device_id:
                        device_id = speakers[ip].get('deviceID')
                    speakers[ip]['is_zone_master'] = bool(master_id and device_id and master_id == device_id)
                    updated = True

            prev_source = speakers[ip].get('source', '') or ''
            prev_status = speakers[ip].get('playStatus', '')

            actual_volume = root.find('.//actualvolume')
            if actual_volume is not None:
                speakers[ip]['volume'] = int(actual_volume.text)
                updated = True

            now_playing = root.find('.//nowPlaying') if root.tag != 'nowPlaying' else root
            
            if now_playing is not None and now_playing.tag == 'nowPlaying':
                source = now_playing.get('source', '') or ''
                source_account = now_playing.get('sourceAccount', '') or ''

                import shared
                if not hasattr(shared, 'speaker_sources_cache'):
                    setattr(shared, 'speaker_sources_cache', {})
                
                if ip not in shared.speaker_sources_cache:
                    try:
                        r_src = requests.get(f"http://{ip}:8090/sources", timeout=2.0)
                        if r_src.status_code == 200:
                            src_tree = ET.fromstring(r_src.content)
                            shared.speaker_sources_cache[ip] = {}
                            
                            if not hasattr(shared, 'speaker_supported_sources'):
                                shared.speaker_supported_sources = {}
                            shared.speaker_supported_sources[ip] = []

                            for item in src_tree.findall('sourceItem'):
                                acc = item.get('sourceAccount')
                                src = item.get('source')
                                if acc:
                                    shared.speaker_sources_cache[ip][acc] = item.text or ''
                                
                                val = acc if (acc and acc != 'VIRTUAL') else src
                                if val and val not in shared.speaker_supported_sources[ip]:
                                    shared.speaker_supported_sources[ip].append(val)
                    except Exception:
                        pass
                
                display_source = source
                if source == 'STORED_MUSIC' and source_account:
                    server_name = shared.speaker_sources_cache.get(ip, {}).get(source_account)
                    if server_name:
                        display_source = f"STORED_MUSIC ({server_name})"

                play_status_node = now_playing.find('playStatus')
                current_status = play_status_node.text if play_status_node is not None else None

                queue = getattr(shared, 'server_queues', {}).get(ip)
                is_end_of_track = False
                
                if source == 'INVALID_SOURCE' and (prev_source.startswith('LOCAL_INTERNET_RADIO') or prev_source.startswith('STORED_MUSIC')):
                    if queue and queue.get('tracks'):
                        is_end_of_track = True
                        
                elif prev_status in ['PLAY_STATE', 'BUFFERING_STATE'] and current_status in ['STOP_STATE', 'STANDBY']:
                    is_end_of_track = True

                if is_end_of_track:
                    if queue and queue.get('tracks'):
                        from dlna import play_next_in_queue
                        def delayed_next():
                            time.sleep(1.0) 
                            import shared
                            q = getattr(shared, 'server_queues', {}).get(ip)
                            if not q or not q.get('tracks'):
                                return
                            play_next_in_queue(ip)
                        threading.Thread(target=delayed_next, daemon=True).start()
                
                speakers[ip]['source'] = display_source
                
                supported_srcs = getattr(shared, 'speaker_supported_sources', {}).get(ip, [])
                speakers[ip]['supported_sources'] = supported_srcs
                
                if source == 'STANDBY':
                    speakers[ip]['state'] = 'STANDBY'
                    speakers[ip]['track'] = ''
                    speakers[ip]['artist'] = ''
                    speakers[ip]['album'] = ''
                    speakers[ip]['cover'] = ''
                    speakers[ip]['playlist'] = ''
                    speakers[ip]['playStatus'] = 'STOP_STATE'
                    speakers[ip]['show_title'] = None 
                    speakers[ip]['show_desc'] = None
                    speakers[ip]['show_image'] = None
                else:
                    speakers[ip]['state'] = 'ON'
                    
                    track = now_playing.find('track')
                    speakers[ip]['track'] = track.text if track is not None else "Prêt"
                    
                    artist = now_playing.find('artist')
                    speakers[ip]['artist'] = artist.text if artist is not None else ""
                    
                    album = now_playing.find('album')
                    speakers[ip]['album'] = album.text if album is not None else ""
                    
                    art = now_playing.find('art')
                    speakers[ip]['cover'] = art.text if art is not None else ""
                    
                    content_item = now_playing.find('ContentItem')
                    if content_item is not None:
                        item_name = content_item.find('itemName')
                        speakers[ip]['playlist'] = item_name.text if item_name is not None else ""
                    else:
                        speakers[ip]['playlist'] = ""

                    shuffle_setting = now_playing.find('shuffleSetting')
                    if shuffle_setting is not None:
                        speakers[ip]['shuffleSetting'] = shuffle_setting.text
                        
                    repeat_setting = now_playing.find('repeatSetting')
                    if repeat_setting is not None:
                        speakers[ip]['repeatSetting'] = repeat_setting.text

                    play_status = now_playing.find('playStatus')
                    if play_status is not None:
                        speakers[ip]['playStatus'] = play_status.text

                    time_node = now_playing.find('time')
                    if time_node is not None:
                        speakers[ip]['time_total'] = time_node.get('total', '0')
                        speakers[ip]['time_position'] = time_node.text

                    if queue and queue.get('tracks') and source in ["LOCAL_INTERNET_RADIO", "INVALID_SOURCE"]:
                        q_idx = queue.get('index', 0)
                        if q_idx < len(queue['tracks']):
                            current_track = queue['tracks'][q_idx]
                            
                            display_source = "LOCAL_INTERNET_RADIO (Fichiers locaux)"
                            speakers[ip]['source'] = display_source 
                            
                            speakers[ip]['track'] = current_track.get('title', speakers[ip]['track'])
                            speakers[ip]['artist'] = current_track.get('artist', 'Inconnu')
                            speakers[ip]['album'] = current_track.get('album', '')
                            
                            total_secs = current_track.get('duration_secs', 0)
                            if total_secs > 0:
                                speakers[ip]['time_total'] = str(total_secs)
                                
                            cover_url = current_track.get('cover')
                            if cover_url and cover_url != "SHOW_DEFAULT_IMAGE":
                                speakers[ip]['cover'] = cover_url

                    speakers[ip]['show_title'] = None
                    speakers[ip]['show_desc'] = None
                    speakers[ip]['show_image'] = None

                    if speakers[ip]['source'] in ['LOCAL_INTERNET_RADIO', 'TUNEIN', 'RADIO_BROWSER']:
                        station_name = str(speakers[ip]['track']).upper() + " " + str(speakers[ip]['artist']).upper()
                        
                        if "FRANCE INTER" in station_name or "FRANCEINTER" in station_name:
                            import radios
                            rf_data = radios.get_radiofrance_live("FRANCEINTER")
                            
                            if rf_data:
                                speakers[ip]['show_title'] = rf_data.get('show_title')
                                speakers[ip]['show_desc'] = rf_data.get('show_desc')
                                speakers[ip]['show_image'] = rf_data.get('show_image')

                updated = True

            if updated:
                from shared import socketio
                socketio.emit('bose_update', {'speakers': speakers})

        except ET.ParseError:
            pass
        except Exception:
            pass

bose_ws_manager = BoseWebsocketManager()
```
<br>

### `app/dlna.py`

```python
from flask import Blueprint, jsonify, request, Response
import socket
import upnpclient
import xml.etree.ElementTree as ET
import base64
import json
import requests
import urllib.parse
import time
import random
import os
import shared
from xml.sax.saxutils import escape
from utils import get_local_ip

dlna_bp = Blueprint('dlna_bp', __name__)

def parse_duration_to_seconds(d_str):
    if not d_str: 
        return 0
    try:
        time_part = d_str.split('.')[0] 
        parts = list(map(int, time_part.split(':')))
        
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        
        return parts[0]
    except Exception:
        return 0
        
# --- RECHERCHE DLNA ---
def ssdp_discover_media_servers():
    msg = ('M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 1\r\nST: urn:schemas-upnp-org:device:MediaServer:1\r\n\r\n')
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(1.5)
    sock.sendto(msg.encode('utf-8'), ('239.255.255.250', 1900))
    locations = set()
    try:
        while True:
            data, _ = sock.recvfrom(2048)
            for line in data.decode('utf-8', errors='ignore').split('\r\n'):
                if line.lower().startswith('location:'):
                    locations.add(line.split(':', 1)[1].strip())
    except socket.timeout: pass
    return locations

@dlna_bp.route('/api/dlna/servers', methods=['GET'])
def list_dlna_servers():
    locations = ssdp_discover_media_servers()
    servers = []
    for loc in locations:
        try:
            device = upnpclient.Device(loc)
            shared.dlna_servers_cache[device.udn] = loc
            servers.append({"name": device.friendly_name, "udn": device.udn})
        except: pass
    return jsonify(servers)

@dlna_bp.route('/api/dlna/browse', methods=['GET'])
def browse_dlna():
    udn = request.args.get('udn')
    object_id = request.args.get('id', '0')
    if udn not in shared.dlna_servers_cache: 
        return jsonify({"error": "Serveur non trouvé"}), 404
    
    try:
        device = upnpclient.Device(shared.dlna_servers_cache[udn])
        result = device.ContentDirectory.Browse(
            ObjectID=object_id, BrowseFlag='BrowseDirectChildren', 
            Filter='*', StartingIndex=0, RequestedCount=500, SortCriteria=''
        )
        root = ET.fromstring(result['Result'])
        ns = {'didl': 'urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/', 'dc': 'http://purl.org/dc/elements/1.1/', 'upnp': 'urn:schemas-upnp-org:metadata-1-0/upnp/'}
        
        items = []
        for container in root.findall('didl:container', ns):
            title_node = container.find('dc:title', ns)
            title = title_node.text if title_node is not None and title_node.text else "Dossier Inconnu"
            
            if title.lower() in ['video', 'videos', 'pictures', 'images', 'photos']:
                continue
            items.append({"id": container.get('id'), "title": title, "type": "folder"})
            
        for item in root.findall('didl:item', ns):
            res = item.find('didl:res', ns)
            if res is not None:
                protocol_info = res.get('protocolInfo', '').lower()
                if 'audio' in protocol_info or 'mpegurl' in protocol_info or 'playlist' in protocol_info:
                    
                    title_node = item.find('dc:title', ns)
                    title = title_node.text if title_node is not None and title_node.text else "Piste Inconnue"
                    
                    cover = item.find('upnp:albumArtURI', ns)
                    artist = item.find('upnp:artist', ns)
                    album = item.find('upnp:album', ns)
                    
                    duration_str = res.get('duration', '')
                    duration_secs = parse_duration_to_seconds(duration_str)
                    
                    cover_url = cover.text.strip() if cover is not None and cover.text else ""
                    if cover_url and cover_url.startswith('/'):
                        from urllib.parse import urlparse
                        parsed_uri = urlparse(shared.dlna_servers_cache[udn])
                        cover_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}{cover_url}"
                        
                    items.append({
                        "id": item.get('id'),
                        "title": title,
                        "artist": artist.text if artist is not None else "Inconnu",
                        "album": album.text if album is not None else "",
                        "url": res.text,
                        "cover": cover_url,
                        "duration_secs": duration_secs,
                        "type": "audio"
                    })
        return jsonify(items)
    except Exception as e: 
        print(f"Erreur DLNA Browse sur le dossier {object_id} : {e}")
        return jsonify({"error": str(e)}), 500

@dlna_bp.route('/api/dlna/search', methods=['POST'])
def search_dlna():
    data = request.json
    udn = data.get('udn')
    query = data.get('query', '').replace('"', '\\"')
    search_type = data.get('type', 'all')
    
    if udn not in shared.dlna_servers_cache: 
        return jsonify({"error": "Serveur DLNA non trouvé ou expiré"}), 404
    
    try:
        device = upnpclient.Device(shared.dlna_servers_cache[udn])
        
        criteria = ""
        if search_type == 'title':
            criteria = f'dc:title contains "{query}"'
        elif search_type == 'artist':
            criteria = f'upnp:artist contains "{query}"'
        elif search_type == 'album':
            criteria = f'upnp:album contains "{query}"'
        else:
            criteria = f'dc:title contains "{query}" or upnp:artist contains "{query}" or upnp:album contains "{query}"'

        criteria = f'(upnp:class derivedfrom "object.item.audioItem") and ({criteria})'

        result = device.ContentDirectory.Search(
            ContainerID='0',
            SearchCriteria=criteria,
            Filter='*', 
            StartingIndex=0, 
            RequestedCount=200, 
            SortCriteria=''
        )
        
        root = ET.fromstring(result['Result'])
        ns = {'didl': 'urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/', 'dc': 'http://purl.org/dc/elements/1.1/', 'upnp': 'urn:schemas-upnp-org:metadata-1-0/upnp/'}
        
        items = []
        for item in root.findall('didl:item', ns):
            res = item.find('didl:res', ns)
            if res is not None:
                protocol_info = res.get('protocolInfo', '').lower()
                if 'audio' in protocol_info or 'mpegurl' in protocol_info or 'playlist' in protocol_info:
                    title_node = item.find('dc:title', ns)
                    title = title_node.text if title_node is not None and title_node.text else "Piste Inconnue"
                    
                    cover = item.find('upnp:albumArtURI', ns)
                    artist = item.find('upnp:artist', ns)
                    album = item.find('upnp:album', ns)
                    
                    duration_str = res.get('duration', '')
                    duration_secs = parse_duration_to_seconds(duration_str)
                    
                    cover_url = cover.text.strip() if cover is not None and cover.text else ""
                    if cover_url and cover_url.startswith('/'):
                        from urllib.parse import urlparse
                        parsed_uri = urlparse(shared.dlna_servers_cache[udn])
                        cover_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}{cover_url}"
                        
                    items.append({
                        "id": item.get('id'),
                        "title": title,
                        "artist": artist.text if artist is not None else "Inconnu",
                        "album": album.text if album is not None else "",
                        "url": res.text,
                        "cover": cover_url,
                        "duration_secs": duration_secs,
                        "type": "audio"
                    })
        return jsonify(items)
    except Exception as e:
        print(f"Erreur DLNA Search local sur {udn} : {e}")
        return jsonify({"error": "Le serveur ne supporte pas la recherche native ou requête mal formée."}), 500

# --- LE PROXY AUDIO ---
@dlna_bp.route('/api/dlna/stream')
def stream_dlna():
    url = request.args.get('url')
    if not url: return "URL manquante", 400
    headers = {}
    if 'Range' in request.headers:
        headers['Range'] = request.headers['Range']
    try:
        r = requests.get(url, headers=headers, stream=True, timeout=5)
        def generate():
            for chunk in r.iter_content(chunk_size=8192):
                if chunk: yield chunk
        resp = Response(generate(), status=r.status_code)
        for key, value in r.headers.items():
            if key.lower() in ['content-type', 'content-length', 'accept-ranges', 'content-range']:
                resp.headers[key] = value
        return resp
    except Exception as e: return str(e), 500

# --- LECTURE ET FILE D'ATTENTE ---
def play_track_from_queue(ip):
    queue = shared.server_queues.get(ip)
    if not queue or not queue['tracks']: return
    
    track = queue['tracks'][queue['index']]
    local_ip = get_local_ip()
    
    item_name = f"{track.get('artist', 'Inconnu')} / {track.get('album', '')} / {track.get('title', 'Piste')}"
    encoded_dlna_url = urllib.parse.quote(track.get('url', ''))
    proxy_url = f"http://{local_ip}/api/dlna/stream?url={encoded_dlna_url}"
    
    queue['elapsed_accumulator'] = 0
    queue['last_updated'] = time.time()
    
    cover_url = track.get('cover', '')
    if cover_url == "SHOW_DEFAULT_IMAGE":
        cover_url = ""
    
    orion_data = {"name": item_name, "imageUrl": cover_url, "streamUrl": proxy_url}
    b64 = base64.b64encode(json.dumps(orion_data, separators=(',', ':')).encode()).decode()
    orion_url = f"http://{local_ip}:{shared.SOUNDCORK_PORT}/core02/svc-bmx-adapter-orion/prod/orion/station?data={b64}"

    xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
<ContentItem source="LOCAL_INTERNET_RADIO" type="stationurl" location="{orion_url}">
    <itemName>{escape(item_name)}</itemName>
</ContentItem>"""

    try:
        requests.post(f"http://{ip}:8090/select", data=xml_data.encode('utf-8'), headers={"Content-Type": "text/xml; charset=utf-8"}, timeout=3.0)
    except Exception as e: print(f"Erreur d'envoi à {ip}: {e}")

def play_next_in_queue(ip):
    queue = shared.server_queues.get(ip)
    if not queue or not queue.get('tracks'): 
        return
    
    if queue.get('repeat_setting') == 'REPEAT_ONE':
        play_track_from_queue(ip)
        return

    if queue['index'] < len(queue['tracks']) - 1:
        queue['index'] += 1
        play_track_from_queue(ip)
    
    elif queue.get('repeat_setting') == 'REPEAT_ALL':
        queue['index'] = 0
        play_track_from_queue(ip)
        
def play_prev_in_queue(ip):
    queue = shared.server_queues.get(ip)
    if not queue or not queue.get('tracks'): return
    
    if queue['index'] > 0:
        queue['index'] -= 1
    elif queue.get('repeat_setting') == 'REPEAT_ALL':
        queue['index'] = len(queue['tracks']) - 1
    else:
        queue['index'] = 0 
        
    play_track_from_queue(ip)

def set_queue_shuffle(ip, shuffle_state):
    queue = shared.server_queues.get(ip)
    if not queue or not queue.get('tracks'): return
    
    queue['shuffle_setting'] = shuffle_state
    
    if shuffle_state == "SHUFFLE_ON":
        if 'original_tracks' not in queue:
            queue['original_tracks'] = list(queue['tracks'])
            
        current_track = queue['tracks'][queue['index']]
        random.shuffle(queue['tracks'])
        queue['index'] = queue['tracks'].index(current_track)
    else:
        if 'original_tracks' in queue:
            current_track = queue['tracks'][queue['index']]
            queue['tracks'] = list(queue['original_tracks'])
            try:
                queue['index'] = queue['tracks'].index(current_track)
            except ValueError:
                queue['index'] = 0

def set_queue_repeat(ip, repeat_state):
    queue = shared.server_queues.get(ip)
    if not queue: return
    
    queue['repeat_setting'] = repeat_state
    queue['repeat'] = (repeat_state in ["REPEAT_ALL", "REPEAT_ONE"])
    
@dlna_bp.route('/api/queue/play', methods=['POST'])
def api_queue_play():
    data = request.json
    ips = data.get('ips', [])
    for ip in ips:
        shared.server_queues[ip] = {
            "tracks": data.get('tracks', []),
            "index": data.get('index', 0),
            "repeat": data.get('repeat', False)
        }
        play_track_from_queue(ip)
    return jsonify({"status": "ok"})

@dlna_bp.route('/api/queue/control', methods=['POST'])
def api_queue_control():
    data = request.json
    ip = data.get('ip')
    action = data.get('action')
    queue = shared.server_queues.get(ip)
    if not queue: return jsonify({"status": "error"})
    
    if action == 'next': play_next_in_queue(ip)
    elif action == 'prev':
        if queue['index'] > 0:
            queue['index'] -= 1
            play_track_from_queue(ip)
        elif queue['repeat']:
            queue['index'] = len(queue['tracks']) - 1
            play_track_from_queue(ip)
    elif action == 'toggle_repeat':
        queue['repeat'] = not queue['repeat']
    return jsonify({"status": "ok", "repeat": queue['repeat']})

@dlna_bp.route('/api/queue/status', methods=['GET'])
def api_queue_status():
    ip = request.args.get('ip')
    queue = shared.server_queues.get(ip)
    if queue and queue['tracks']:
        return jsonify({
            "active": True,
            "track": queue['tracks'][queue['index']],
            "index": queue['index'],
            "total": len(queue['tracks']),
            "repeat": queue['repeat']
        })
    return jsonify({"active": False})
    

# =========================================================
# --- NAVIGATEUR DLNA (Bypass Bose -> UPNP Direct) ---
# =========================================================

@dlna_bp.route('/api/upnp/servers', methods=['GET'])
def get_upnp_servers():
    ip = request.args.get('ip')
    if not ip:
        return jsonify({'error': 'IP de l\'enceinte requise'}), 400

    servers = []
    try:
        ready_accounts = set()
        try:
            resp_sources = requests.get(f'http://{ip}:8090/sources', timeout=3)
            if resp_sources.status_code == 200:
                sources_tree = ET.fromstring(resp_sources.text)
                for source in sources_tree.findall('.//sourceItem'):
                    if source.get('source') == 'STORED_MUSIC' and source.get('status') == 'READY':
                        account = source.get('sourceAccount')
                        if account:
                            ready_accounts.add(account)
        except Exception as e:
            print(f"Avertissement: Impossible de lire /sources sur {ip} : {e}", flush=True)

        response = requests.get(f'http://{ip}:8090/listMediaServers', timeout=5)
        tree = ET.fromstring(response.text)
        
        for server in tree.findall('.//media_server'):
            friendly_name = server.get('friendly_name') or 'Serveur DLNA'
            account_id = server.get('id')
            location_url = server.get('location')
            nas_ip = server.get('ip')
            
            if account_id and not account_id.endswith('/0'):
                account_id = f"{account_id}/0"
            
            if account_id not in ready_accounts:
                continue
            
            if not location_url and nas_ip:
                location_url = f"http://{nas_ip}:50001/desc/device.xml"
            
            servers.append({
                'name': friendly_name,
                'account': account_id,
                'location': location_url
            })
            
    except Exception as e:
        print("Erreur listMediaServers :", str(e), flush=True)
        return jsonify({'error': str(e)}), 500

    return jsonify(servers)
    
@dlna_bp.route('/api/upnp/navigate', methods=['POST'])
def navigate_upnp():
    data = request.json
    location = data.get('location')
    node_id = data.get('node_id', '0')
    
    if not location or location == 'undefined':
        return jsonify({'error': 'URL du NAS introuvable. Veuillez rafraîchir la page.'}), 400

    try:
        device = upnpclient.Device(location)
        
        content_directory = None
        for service in device.services:
            if 'ContentDirectory' in service.service_type:
                content_directory = service
                break
                
        if not content_directory:
            return jsonify({'error': 'Service de contenu introuvable.'}), 400

        browse_result = content_directory.Browse(
            ObjectID=node_id,
            BrowseFlag='BrowseDirectChildren',
            Filter='*',
            StartingIndex=0,
            RequestedCount=200,
            SortCriteria=''
        )
        
        didl_xml = browse_result.get('Result')
        items = []
        
        if didl_xml:
            didl_tree = ET.fromstring(didl_xml.encode('utf-8'))
            
            for child in didl_tree:
                tag_name = child.tag.split('}')[-1]
                is_dir = (tag_name == 'container')
                
                name, artist, album, url, cover = '', '', '', '', ''
                
                for sub in child:
                    sub_tag = sub.tag.split('}')[-1]
                    if sub_tag == 'title': name = sub.text
                    elif sub_tag == 'artist': artist = sub.text
                    elif sub_tag == 'album': album = sub.text
                    elif sub_tag == 'res': url = sub.text
                    elif sub_tag == 'albumArtURI': cover = sub.text
                        
                if cover and cover.startswith('/'):
                    from urllib.parse import urlparse
                    parsed_uri = urlparse(location)
                    cover = f"{parsed_uri.scheme}://{parsed_uri.netloc}{cover}"
                        
                items.append({
                    'name': name or ('Dossier' if is_dir else 'Piste audio'),
                    'node_id': child.get('id'),
                    'is_dir': is_dir,
                    'artist': artist,
                    'album': album,
                    'url': url,
                    'cover': cover
                })
                
        return jsonify({'items': items})
        
    except Exception as e:
        print(f"ERREUR UPNP DIRECT (Location: {location}) :", str(e), flush=True)
        return jsonify({'error': str(e)}), 500
        
@dlna_bp.route('/api/upnp/play', methods=['POST'])
def play_upnp():
    data = request.json
    ip = data.get('ip')
    folder_id = data.get('folder_id')
    offset = data.get('offset', 0)
    
    account = data.get('account') 
    folder_title = data.get('folder_title', 'Dossier inconnu')
    
    if not ip or not folder_id or not account:
        return jsonify({'error': 'Données manquantes'}), 400

    if ip in getattr(shared, 'server_queues', {}):
        shared.server_queues[ip] = {}
        
    xml_payload = f"""<?xml version="1.0" encoding="UTF-8" ?>
    <ContentItem source="STORED_MUSIC" location="{folder_id}" sourceAccount="{account}" isPresetable="true">
        <itemName>{folder_title}</itemName>
    </ContentItem>"""

    headers = {"Content-Type": "text/xml; charset=utf-8"}
    
    try:
        response = requests.post(f'http://{ip}:8090/select', data=xml_payload.encode('utf-8'), headers=headers, timeout=5)
        
        if response.status_code == 200:
            
            if offset > 0:
                import time
                import threading
                import xml.etree.ElementTree as ET
                
                def smart_skip_tracks():
                    ready = False
                    for _ in range(20):
                        try:
                            r = requests.get(f'http://{ip}:8090/nowPlaying', timeout=1)
                            if r.status_code == 200:
                                status = ET.fromstring(r.content).findtext('playStatus')
                                if status in ['PLAY_STATE', 'BUFFERING_STATE']:
                                    ready = True
                                    break
                        except:
                            pass
                        time.sleep(0.5)
                    
                    if ready:
                        time.sleep(0.5) 
                        for _ in range(offset):
                            requests.post(f'http://{ip}:8090/key', data='<key state="press" sender="Gabbo">NEXT_TRACK</key>'.encode('utf-8'), headers=headers)
                            requests.post(f'http://{ip}:8090/key', data='<key state="release" sender="Gabbo">NEXT_TRACK</key>'.encode('utf-8'), headers=headers)
                            time.sleep(0.6) 
                            
                threading.Thread(target=smart_skip_tracks, daemon=True).start()
                
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'error': f'Erreur enceinte: {response.status_code}'}), 500
            
    except Exception as e:
        return jsonify({'error': 'Enceinte injoignable'}), 500

@dlna_bp.route('/api/upnp/search', methods=['POST'])
def search_upnp():
    data = request.json
    location = data.get('location')
    query = data.get('query', '').replace('"', '\\"') 
    search_type = data.get('type', 'all')
    
    if not location or location == 'undefined':
        return jsonify({'error': 'URL du NAS introuvable.'}), 400

    try:
        device = upnpclient.Device(location)
        
        content_directory = None
        for service in device.services:
            if 'ContentDirectory' in service.service_type:
                content_directory = service
                break
                
        if not content_directory:
            return jsonify({'error': 'Service de contenu introuvable sur le NAS.'}), 400

        criteria = ""
        if search_type == 'title':
            criteria = f'dc:title contains "{query}"'
        elif search_type == 'artist':
            criteria = f'upnp:artist contains "{query}"'
        elif search_type == 'album':
            criteria = f'upnp:album contains "{query}"'
        else: 
            criteria = f'dc:title contains "{query}" or upnp:artist contains "{query}" or upnp:album contains "{query}"'

        criteria = f'(upnp:class derivedfrom "object.item.audioItem") and ({criteria})'

        search_result = content_directory.Search(
            ContainerID='0',
            SearchCriteria=criteria,
            Filter='*',
            StartingIndex=0,
            RequestedCount=100,
            SortCriteria=''
        )
        
        didl_xml = search_result.get('Result')
        items = []
        
        if didl_xml:
            import xml.etree.ElementTree as ET
            didl_tree = ET.fromstring(didl_xml.encode('utf-8'))
            
            for child in didl_tree:
                tag_name = child.tag.split('}')[-1]
                
                if tag_name == 'item': 
                    name, artist, album, url, cover = '', '', '', '', ''
                    
                    for sub in child:
                        sub_tag = sub.tag.split('}')[-1]
                        if sub_tag == 'title': name = sub.text
                        elif sub_tag == 'artist': artist = sub.text
                        elif sub_tag == 'album': album = sub.text
                        elif sub_tag == 'res': url = sub.text
                        elif sub_tag == 'albumArtURI': cover = sub.text
                            
                    if cover and cover.startswith('/'):
                        from urllib.parse import urlparse
                        parsed_uri = urlparse(location)
                        cover = f"{parsed_uri.scheme}://{parsed_uri.netloc}{cover}"
                            
                    items.append({
                        'name': name or 'Piste audio',
                        'node_id': child.get('id'),
                        'parent_id': child.get('parentID', '0'), 
                        'artist': artist,
                        'album': album,
                        'url': url,
                        'cover': cover
                    })
                    
        return jsonify({'items': items})
        
    except Exception as e:
        print(f"ERREUR UPNP SEARCH (Location: {location}) :", str(e), flush=True)
        return jsonify({'error': 'Ce serveur DLNA ne supporte probablement pas la fonction de recherche.'}), 500

```
<br>

### `app/podcasts.py`

```python
from flask import Blueprint, jsonify, request, send_from_directory
import os
import requests
import urllib.parse
import urllib.request
import json
import base64
import threading
import shared
from xml.sax.saxutils import escape
from werkzeug.utils import secure_filename

podcast_bp = Blueprint('podcast_bp', __name__)

# =========================================================================
# 1. MODULE RADIO FRANCE DOWNLOADER (Natif Flask)
# =========================================================================
# Transféré dans  rf_dwl.py
# =========================================================================
# 2. APPLE PODCASTS (EXISTANT)
# =========================================================================
@podcast_bp.route('/api/podcasts/search', methods=['GET'])
def search_podcast():
    query = request.args.get('q', '')
    if len(query) < 2: return jsonify([])
    try:
        params = {"term": query, "country": request.args.get('country', 'fr'), "entity": "podcastEpisode", "limit": 30}
        url = f"https://itunes.apple.com/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Soundtouch-Pi/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as response:
            data = json.loads(response.read().decode('utf-8'))
            return jsonify([{"title": item.get("trackName"), "emission": item.get("collectionName"), "url": item.get("episodeUrl") or item.get("previewUrl")} for item in data.get("results", []) if item.get("episodeUrl") or item.get("previewUrl")])
    except Exception as e: return jsonify({"error": str(e)}), 500

@podcast_bp.route('/local_podcast/<filename>')
def serve_local_podcast(filename):
    return send_from_directory(shared.DATA_PATH, filename)

@podcast_bp.route('/api/play_podcast', methods=['POST'])
def play_podcast():
    data = request.json
    local_filename = "podcast.mp3"
    try:
        r = requests.get(data.get('url'), headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=15)
        r.raise_for_status()
        with open(os.path.join(shared.DATA_PATH, local_filename), 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

    media_server_host = request.host.split(':')[0] 
    orion_data = {"name": data.get('name', 'Podcast'), "imageUrl": "", "streamUrl": f"http://{media_server_host}/local_podcast/{local_filename}"}
    b64 = base64.b64encode(json.dumps(orion_data, separators=(',', ':')).encode()).decode()
    xml_data = f'<?xml version="1.0" encoding="UTF-8"?><ContentItem source="LOCAL_INTERNET_RADIO" type="stationurl" location="http://{media_server_host}:{shared.SOUNDCORK_PORT}/core02/svc-bmx-adapter-orion/prod/orion/station?data={b64}"><itemName>{escape(data.get("name", "Podcast"))}</itemName></ContentItem>'

    for ip in data.get('ips', []):
        # --- FIX : Libération de la file DLNA ---
        if ip in shared.server_queues:
            shared.server_queues[ip] = {}
            
        try: requests.post(f"http://{ip}:8090/select", data=xml_data.encode('utf-8'), headers={"Content-Type": "text/xml; charset=utf-8"}, timeout=3.0)
        except: pass
    return jsonify({"status": "ok"})

# =========================================================================
# 3. LECTURE DES FICHIERS LOCAUX RF (EXISTANT)
# =========================================================================
@podcast_bp.route('/rf_podcast/<path:filename>')
def serve_rf_podcast(filename):
    return send_from_directory(shared.RF_PODCASTS_PATH, filename)

@podcast_bp.route('/api/local_rf_downloads', methods=['GET'])
def list_local_rf_downloads():
    if not os.path.exists(shared.RF_PODCASTS_PATH): return jsonify({})
    downloads = {}
    try:
        for show_dir in os.listdir(shared.RF_PODCASTS_PATH):
            dir_path = os.path.join(shared.RF_PODCASTS_PATH, show_dir)
            if os.path.isdir(dir_path):
                mp3s = [f for f in os.listdir(dir_path) if f.endswith('.mp3')]
                if mp3s: downloads[show_dir] = sorted(mp3s)
    except: pass
    return jsonify(downloads)

@podcast_bp.route('/api/play_local_rf', methods=['POST'])
def play_local_rf():
    data = request.json
    media_server_host = request.host.split(':')[0] 
    mp3_url = f"http://{media_server_host}/rf_podcast/{urllib.parse.quote(data.get('path'))}"
    
    orion_data = {"name": data.get('name', 'Podcast RF'), "imageUrl": "", "streamUrl": mp3_url}
    b64 = base64.b64encode(json.dumps(orion_data, separators=(',', ':')).encode()).decode()
    xml_data = f'<?xml version="1.0" encoding="UTF-8"?><ContentItem source="LOCAL_INTERNET_RADIO" type="stationurl" location="http://{media_server_host}:{shared.SOUNDCORK_PORT}/core02/svc-bmx-adapter-orion/prod/orion/station?data={b64}"><itemName>{escape(data.get("name", "Podcast RF"))}</itemName></ContentItem>'

    for ip in data.get('ips', []):
        # --- FIX : Libération de la file DLNA ---
        if ip in shared.server_queues:
            shared.server_queues[ip] = {}
            
        try: requests.post(f"http://{ip}:8090/select", data=xml_data.encode('utf-8'), headers={"Content-Type": "text/xml; charset=utf-8"}, timeout=3.0)
        except: pass
    return jsonify({"status": "ok"})
    
@podcast_bp.route('/api/delete_local_rf', methods=['POST'])
def delete_local_rf():
    data = request.json
    file_path = data.get('path')
    
    # Sécurité : empêcher de remonter dans les dossiers parents
    if not file_path or '..' in file_path:
        return jsonify({"status": "error", "message": "Chemin de fichier invalide"}), 400
        
    full_path = os.path.join(shared.RF_PODCASTS_PATH, file_path)
    
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
            
            # Nettoyage automatique : supprimer le dossier de l'émission s'il est maintenant vide
            folder_path = os.path.dirname(full_path)
            if not os.listdir(folder_path):
                os.rmdir(folder_path)
                
            return jsonify({"status": "ok"})
        else:
            return jsonify({"status": "error", "message": "Fichier introuvable"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@podcast_bp.route('/api/upload_play', methods=['POST'])
def upload_play():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "Aucun fichier reçu"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "Fichier invalide"}), 400

    ips_str = request.form.get('ips', '[]')
    try:
        ips = json.loads(ips_str)
    except:
        ips = []

    if not ips:
        return jsonify({"status": "error", "message": "Aucune enceinte ciblée"}), 400

    # Nettoie le nom de fichier (retire les accents et caractères spéciaux)
    filename = secure_filename(file.filename)
    
    # Écrase le précédent "upload" pour ne pas saturer la mémoire du Raspberry
    # On ajoute un préfixe pour le dissocier des podcasts iTunes
    temp_filename = f"upload_{filename}"
    filepath = os.path.join(shared.DATA_PATH, temp_filename)
    
    try:
        file.save(filepath)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur d'écriture disque: {str(e)}"}), 500

    media_server_host = request.host.split(':')[0] 
    
    # On exploite la route existante serve_local_podcast pour exposer le fichier à l'enceinte
    file_url = f"http://{media_server_host}/local_podcast/{urllib.parse.quote(temp_filename)}"

    # Utilisation du Hack Orion (idem que pour les webradios et podcasts)
    orion_data = {"name": file.filename, "imageUrl": "", "streamUrl": file_url}
    b64 = base64.b64encode(json.dumps(orion_data, separators=(',', ':')).encode()).decode()
    xml_data = f'<?xml version="1.0" encoding="UTF-8"?><ContentItem source="LOCAL_INTERNET_RADIO" type="stationurl" location="http://{media_server_host}:{shared.SOUNDCORK_PORT}/core02/svc-bmx-adapter-orion/prod/orion/station?data={b64}"><itemName>{escape(file.filename)}</itemName></ContentItem>'

    for ip in ips:
        # Libération de la file DLNA locale si elle était en cours de lecture
        if ip in shared.server_queues:
            shared.server_queues[ip] = {}
            
        try: 
            requests.post(f"http://{ip}:8090/select", data=xml_data.encode('utf-8'), headers={"Content-Type": "text/xml; charset=utf-8"}, timeout=3.0)
        except Exception as e: 
            print(f"Erreur d'envoi à {ip}: {e}")
            
    return jsonify({"status": "ok"})

```
<br>

### `app/radiofrance_downloader/api.py`

```python
"""Radio France GraphQL API client."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import requests

from radiofrance_downloader.exceptions import (
    APIError,
    AuthenticationError,
    ShowNotFoundError,
)
from radiofrance_downloader.models import Episode, Show, Station, StationId

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://openapi.radiofrance.fr/v1/graphql"

STATIONS: dict[StationId, Station] = {
    StationId.FRANCE_INTER: Station(
        id=StationId.FRANCE_INTER,
        name="France Inter",
        url="https://www.radiofrance.fr/franceinter",
    ),
    StationId.FRANCE_INFO: Station(
        id=StationId.FRANCE_INFO,
        name="franceinfo",
        url="https://www.radiofrance.fr/franceinfo",
    ),
    StationId.FRANCE_BLEU: Station(
        id=StationId.FRANCE_BLEU,
        name="France Bleu",
        url="https://www.radiofrance.fr/francebleu",
    ),
    StationId.FRANCE_CULTURE: Station(
        id=StationId.FRANCE_CULTURE,
        name="France Culture",
        url="https://www.radiofrance.fr/franceculture",
    ),
    StationId.FRANCE_MUSIQUE: Station(
        id=StationId.FRANCE_MUSIQUE,
        name="France Musique",
        url="https://www.radiofrance.fr/francemusique",
    ),
    StationId.MOUV: Station(
        id=StationId.MOUV,
        name="Mouv'",
        url="https://www.radiofrance.fr/mouv",
    ),
    StationId.FIP: Station(
        id=StationId.FIP,
        name="FIP",
        url="https://www.radiofrance.fr/fip",
    ),
}

# Map from URL slug to StationId for reverse lookup
_SLUG_TO_STATION: dict[str, StationId] = {
    "franceinter": StationId.FRANCE_INTER,
    "franceinfo": StationId.FRANCE_INFO,
    "francebleu": StationId.FRANCE_BLEU,
    "franceculture": StationId.FRANCE_CULTURE,
    "francemusique": StationId.FRANCE_MUSIQUE,
    "mouv": StationId.MOUV,
    "fip": StationId.FIP,
}


class RadioFranceAPI:
    """Client for the Radio France GraphQL API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {
                "x-token": api_key,
                "Content-Type": "application/json",
            }
        )

    def _query(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query."""
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables

        logger.debug("GraphQL POST %s", GRAPHQL_URL)
        logger.debug("Query: %s", query.strip()[:200])
        logger.debug("Variables: %s", variables)

        try:
            resp = self.session.post(GRAPHQL_URL, json=payload, timeout=30)
        except requests.RequestException as e:
            raise APIError(f"Request failed: {e}") from e

        logger.debug("Response %s: %s", resp.status_code, resp.text[:500])

        if resp.status_code == 401:
            raise AuthenticationError(
                f"Authentication failed (HTTP {resp.status_code}): "
                f"{resp.text[:200]}"
            )
        if resp.status_code >= 400:
            raise APIError(
                f"API error {resp.status_code}: {resp.text}",
                resp.status_code,
            )

        data = resp.json()

        # GraphQL can return errors even with 200 status
        if "errors" in data:
            errors = data["errors"]
            msg = (
                errors[0].get("message", str(errors))
                if errors else str(errors)
            )
            if "not found" in msg.lower():
                raise ShowNotFoundError(msg)
            raise APIError(f"GraphQL error: {msg}")

        return data.get("data", {})

    def search_shows(
        self, query: str, station: StationId | None = None,
    ) -> list[Show]:
        """Search for shows, optionally filtered by station.

        The GraphQL API has no text search — we list shows per station
        and filter client-side.
        """
        q = query.lower()
        stations = [station] if station else list(STATIONS)

        all_shows: list[Show] = []
        for station_id in stations:
            try:
                shows = self.get_all_station_shows(station_id)
                for show in shows:
                    title = show.title.lower()
                    desc = (show.description or "").lower()
                    if q in title or q in desc:
                        all_shows.append(show)
            except APIError:
                continue
        return all_shows

    def get_all_station_shows(
        self,
        station: StationId,
    ) -> list[Show]:
        """Get all shows for a station, paginating automatically."""
        all_shows: list[Show] = []
        after: str | None = None
        while True:
            shows, last_cursor = self._fetch_station_shows_page(
                station, first=100, after=after,
            )
            all_shows.extend(shows)
            if not last_cursor or len(shows) < 100:
                break
            after = last_cursor
        return all_shows

    def get_station_shows(
        self,
        station: StationId,
        first: int = 100,
        after: str | None = None,
    ) -> list[Show]:
        """Get one page of shows for a station."""
        shows, _ = self._fetch_station_shows_page(
            station, first=first, after=after,
        )
        return shows

    def _fetch_station_shows_page(
        self,
        station: StationId,
        first: int = 100,
        after: str | None = None,
    ) -> tuple[list[Show], str | None]:
        """Fetch a single page of shows. Returns (shows, last_cursor)."""
        gql = """
        query GetShows($station: StationsEnum!, $first: Int!, $after: String) {
            shows(station: $station, first: $first, after: $after) {
                edges {
                    cursor
                    node {
                        id
                        title
                        url
                        standFirst
                    }
                }
            }
        }
        """
        variables: dict = {"station": station.value, "first": first}
        if after:
            variables["after"] = after

        data = self._query(gql, variables)
        shows_data = data.get("shows", {})
        edges = shows_data.get("edges", [])

        shows = []
        last_cursor = None
        for edge in edges:
            node = edge.get("node", {})
            last_cursor = edge.get("cursor")
            station_obj = STATIONS.get(station)

            shows.append(
                Show(
                    id=node.get("id", ""),
                    title=node.get("title", ""),
                    description=node.get("standFirst", ""),
                    url=node.get("url", ""),
                    station=station_obj,
                )
            )
        return shows, last_cursor

    def get_show_episodes(
        self,
        show_url: str,
        first: int = 20,
        after: str | None = None,
        fetch_all: bool = False,
    ) -> tuple[list[Episode], str | None]:
        """Get episodes for a show by its URL.

        Returns (episodes, next_cursor).
        """
        gql = """
        query GetDiffusions($url: String!, $first: Int!, $after: String) {
            diffusionsOfShowByUrl(url: $url, first: $first, after: $after) {
                edges {
                    cursor
                    node {
                        id
                        title
                        standFirst
                        published_date
                        url
                        podcastEpisode {
                            url
                            duration
                        }
                        show {
                            id
                            title
                        }
                    }
                }
            }
        }
        """
        all_episodes: list[Episode] = []
        current_after = after

        while True:
            variables: dict = {"url": show_url, "first": first}
            if current_after:
                variables["after"] = current_after

            data = self._query(gql, variables)
            diffusions = data.get("diffusionsOfShowByUrl", {})
            edges = diffusions.get("edges", [])

            if not edges:
                return all_episodes, None

            next_cursor = None
            for edge in edges:
                node = edge.get("node", {})
                next_cursor = edge.get("cursor")

                show_data = node.get("show") or {}
                podcast = node.get("podcastEpisode") or {}

                # published_date is a String timestamp from the API
                published_at = None
                ts = node.get("published_date")
                if ts:
                    published_at = datetime.fromtimestamp(
                        int(ts), tz=UTC,
                    )

                all_episodes.append(
                    Episode(
                        id=node.get("id", ""),
                        title=node.get("title", ""),
                        description=node.get("standFirst", ""),
                        show_id=show_data.get("id", ""),
                        show_title=show_data.get("title", ""),
                        published_at=published_at,
                        duration=podcast.get("duration", 0) or 0,
                        audio_url=podcast.get("url", ""),
                        page_url=node.get("url", ""),
                    )
                )

            if not fetch_all or not next_cursor:
                return all_episodes, next_cursor

            current_after = next_cursor

    def get_show_details(self, show_url: str) -> Show:
        """Get details for a show by its URL."""
        gql = """
        query GetShow($url: String!) {
            showByUrl(url: $url) {
                id
                title
                standFirst
                url
                podcast {
                    rss
                    itunes
                }
            }
        }
        """
        data = self._query(gql, {"url": show_url})
        show_data = data.get("showByUrl")

        if not show_data:
            raise ShowNotFoundError(f"Show not found: {show_url}")

        show_full_url = show_data.get("url", "")
        station = self._station_from_url(show_full_url)

        return Show(
            id=show_data.get("id", ""),
            title=show_data.get("title", ""),
            description=show_data.get("standFirst", ""),
            url=show_full_url,
            station=station,
        )

    @staticmethod
    def _station_from_url(url: str) -> Station | None:
        """Try to determine the station from a show URL."""
        for slug, station_id in _SLUG_TO_STATION.items():
            if f"/{slug}/" in url or url.endswith(f"/{slug}"):
                return STATIONS.get(station_id)
        return None

```
<br>

### `app/radiofrance_downloader/app.py`

```python
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
```
<br>

### `app/radiofrance_downloader/cli.py`

```python
"""CLI interface for radiofrance-downloader."""

from __future__ import annotations

import logging
from pathlib import Path

import click
from rich.console import Console
from rich.progress import BarColumn, DownloadColumn, Progress, TransferSpeedColumn
from rich.table import Table

from radiofrance_downloader import __version__
from radiofrance_downloader.api import STATIONS, RadioFranceAPI
from radiofrance_downloader.config import Config
from radiofrance_downloader.downloader import EpisodeDownloader
from radiofrance_downloader.exceptions import RadioFranceError
from radiofrance_downloader.models import StationId

console = Console()
err_console = Console(stderr=True)


def _get_api(config: Config) -> RadioFranceAPI:
    """Get an API client, raising a helpful error if no key is set."""
    if not config.api_key:
        raise click.ClickException(
            "No API key configured. Run: radiofrance-dl config set-api-key <key>"
        )
    return RadioFranceAPI(config.api_key)


@click.group()
@click.version_option(version=__version__, prog_name="radiofrance-dl")
@click.option("--debug", is_flag=True, help="Enable debug logging.")
@click.pass_context
def main(ctx: click.Context, debug: bool) -> None:
    """Download Radio France podcasts."""
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(name)s %(levelname)s: %(message)s",
        )
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.load()


@main.command()
@click.argument("query")
@click.option(
    "--station",
    type=click.Choice([s.value for s in StationId], case_sensitive=False),
    default=None,
    help="Filter by station.",
)
@click.pass_context
def search(ctx: click.Context, query: str, station: str | None) -> None:
    """Search for shows by name."""
    config = ctx.obj["config"]
    api = _get_api(config)

    station_id = StationId(station) if station else None

    try:
        shows = api.search_shows(query, station=station_id)
    except RadioFranceError as e:
        raise click.ClickException(str(e)) from e

    if not shows:
        console.print("[yellow]No shows found.[/yellow]")
        return

    table = Table(title=f"Search results for '{query}'")
    table.add_column("URL", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Station", style="green")
    table.add_column("Description", max_width=50)

    for show in shows:
        station_name = show.station.name if show.station else "—"
        desc = show.description or ""
        if len(desc) > 50:
            desc = desc[:47] + "..."
        table.add_row(show.url, show.title, station_name, desc)

    console.print(table)


@main.command("list")
@click.argument("station", required=False)
@click.pass_context
def list_cmd(ctx: click.Context, station: str | None) -> None:
    """List stations, or shows for a station."""
    if station is None:
        table = Table(title="Radio France Stations")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="bold")
        table.add_column("URL")

        for sid, st in STATIONS.items():
            table.add_row(str(sid), st.name, st.url)

        console.print(table)
        return

    # If station is provided, list shows for that station
    config = ctx.obj["config"]
    api = _get_api(config)

    try:
        station_id = StationId(station.upper())
    except ValueError:
        raise click.ClickException(
            f"Unknown station '{station}'. Run 'radiofrance-dl list' to see available stations."
        ) from None

    try:
        shows = api.get_station_shows(station_id)
    except RadioFranceError as e:
        raise click.ClickException(str(e)) from e

    if not shows:
        console.print(f"[yellow]No shows found for '{station}'.[/yellow]")
        return

    table = Table(title=f"Shows for {STATIONS[station_id].name}")
    table.add_column("URL", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Description", max_width=60)

    for show in shows:
        desc = show.description or ""
        if len(desc) > 60:
            desc = desc[:57] + "..."
        table.add_row(show.url, show.title, desc)

    console.print(table)


@main.command()
@click.argument("show_url")
@click.option("--page", "after", default=None, help="Cursor for pagination.")
@click.pass_context
def episodes(ctx: click.Context, show_url: str, after: str | None) -> None:
    """List episodes for a show (by URL path)."""
    config = ctx.obj["config"]
    api = _get_api(config)

    try:
        eps, next_cursor = api.get_show_episodes(show_url, after=after)
    except RadioFranceError as e:
        raise click.ClickException(str(e)) from e

    if not eps:
        console.print("[yellow]No episodes found.[/yellow]")
        return

    table = Table(title=f"Episodes for {show_url}")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Date", style="green")
    table.add_column("Duration", justify="right")

    for ep in eps:
        date_str = ep.published_at.strftime("%Y-%m-%d") if ep.published_at else "—"
        dur = f"{ep.duration // 60}:{ep.duration % 60:02d}" if ep.duration else "—"
        table.add_row(ep.id, ep.title, date_str, dur)

    console.print(table)

    if next_cursor is not None:
        console.print(f"\n[dim]Next page: --page {next_cursor}[/dim]")


@main.command()
@click.argument("show_url")
@click.option("--latest", "latest_n", type=int, default=None, help="Download latest N episodes.")
@click.option("--all", "fetch_all", is_flag=True, help="Download all available episodes.")
@click.option("-o", "--output", "output_dir", type=click.Path(), default=None, help="Output dir.")
@click.pass_context
def download(
    ctx: click.Context,
    show_url: str,
    latest_n: int | None,
    fetch_all: bool,
    output_dir: str | None,
) -> None:
    """Download episodes for a show (by URL path)."""
    config = ctx.obj["config"]
    api = _get_api(config)

    out = Path(output_dir) if output_dir else Path(config.output_dir)

    try:
        eps, _ = api.get_show_episodes(show_url, fetch_all=fetch_all)
    except RadioFranceError as e:
        raise click.ClickException(str(e)) from e

    if latest_n is not None:
        eps = eps[:latest_n]

    if not eps:
        console.print("[yellow]No episodes to download.[/yellow]")
        return

    console.print(f"Downloading {len(eps)} episode(s) to [bold]{out}[/bold]\n")

    downloader = EpisodeDownloader(output_dir=out)

    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        console=console,
        disable=not console.is_terminal,
    ) as progress:
        for ep in eps:
            task = progress.add_task(
                f"[cyan]{ep.title[:50]}",
                total=None,
            )

            def on_progress(downloaded: int, total: int, _task=task) -> None:
                if total:
                    progress.update(_task, total=total, completed=downloaded)
                else:
                    progress.update(_task, completed=downloaded)

            try:
                result = downloader.download_episode(ep, progress_callback=on_progress)
            except RadioFranceError as e:
                progress.update(task, description=f"[red]FAILED: {ep.title[:40]}")
                err_console.print(f"[red]Error downloading {ep.title}: {e}[/red]")
                continue

            if result.already_existed:
                progress.update(
                    task,
                    description=f"[dim]SKIPPED: {ep.title[:40]}[/dim]",
                    completed=result.file_size,
                    total=result.file_size,
                )
            elif result.success:
                progress.update(
                    task,
                    description=f"[green]OK: {ep.title[:40]}[/green]",
                    completed=result.file_size,
                    total=result.file_size,
                )
            else: # <--- AJOUTER CE BLOC
                progress.update(
                    task,
                    description=f"[red]FAILED: {ep.title[:40]} ({result.error})[/red]",
                )

@main.group()
def config() -> None:
    """Manage configuration."""


@config.command("set-api-key")
@click.argument("key")
def set_api_key(key: str) -> None:
    """Store your Radio France API key."""
    cfg = Config.load()
    cfg.api_key = key
    cfg.save()
    console.print("[green]API key saved.[/green]")


@config.command("set-output-dir")
@click.argument("path", type=click.Path())
def set_output_dir(path: str) -> None:
    """Set the default output directory for downloads."""
    cfg = Config.load()
    cfg.output_dir = str(Path(path).expanduser().resolve())
    cfg.save()
    console.print(f"[green]Output directory set to {cfg.output_dir}[/green]")


@config.command("show")
def show_config() -> None:
    """Display current configuration."""
    cfg = Config.load()
    table = Table(title="Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    api_key_display = cfg.api_key[:8] + "..." if len(cfg.api_key) > 8 else cfg.api_key or "—"
    table.add_row("api_key", api_key_display)
    table.add_row("output_dir", cfg.output_dir)
    table.add_row("default_station", cfg.default_station or "—")

    console.print(table)

```
<br>

### `app/radiofrance_downloader/config.py`

```python
"""Configuration management for radiofrance-downloader."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from radiofrance_downloader.exceptions import ConfigError

CONFIG_DIR = Path.home() / ".config" / "radiofrance-downloader"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    """Application configuration."""

    api_key: str = ""
    output_dir: str = str(Path.home() / "Podcasts" / "RadioFrance")
    default_station: str = ""

    @classmethod
    def load(cls) -> Config:
        """Load configuration from disk, returning defaults if not found."""
        if not CONFIG_FILE.exists():
            return cls()
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return cls(
                api_key=data.get("api_key", ""),
                output_dir=data.get("output_dir", str(Path.home() / "Podcasts" / "RadioFrance")),
                default_station=data.get("default_station", ""),
            )
        except (json.JSONDecodeError, OSError) as e:
            raise ConfigError(f"Failed to read config: {e}") from e

    def save(self) -> None:
        """Save configuration to disk."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(
                json.dumps(asdict(self), indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            raise ConfigError(f"Failed to write config: {e}") from e

```
<br>

### `app/radiofrance_downloader/downloader.py`

```python
"""MP3 download engine with progress callbacks."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

import requests

from radiofrance_downloader.exceptions import DownloadError
from radiofrance_downloader.models import DownloadResult, Episode

DEFAULT_CHUNK_SIZE = 8192


def sanitize_filename(name: str) -> str:
    """Convert a string into a safe filename."""
    # Normalize unicode characters
    name = unicodedata.normalize("NFKD", name)
    # Replace common separators with hyphens
    name = re.sub(r"[\s/\\:]+", "-", name)
    # Remove characters not allowed in filenames
    name = re.sub(r"[^\w\-.]", "", name)
    # Collapse multiple hyphens
    name = re.sub(r"-{2,}", "-", name)
    # Strip leading/trailing hyphens and dots
    name = name.strip("-.")
    return name[:200] if name else "episode"


class EpisodeDownloader:
    """Downloads podcast episodes to disk."""

    def __init__(
        self,
        output_dir: str | Path,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        self.output_dir = Path(output_dir)
        self.chunk_size = chunk_size

    def _build_filepath(self, episode: Episode) -> Path:
        """Build the destination file path for an episode."""
        show_dir_name = sanitize_filename(episode.show_title) if episode.show_title else "unknown"
        show_dir = self.output_dir / show_dir_name
        show_dir.mkdir(parents=True, exist_ok=True)

        date_prefix = ""
        if episode.published_at:
            date_prefix = episode.published_at.strftime("%Y-%m-%d") + "_"

        title_part = sanitize_filename(episode.title)
        filename = f"{date_prefix}{title_part}.mp3"

        return show_dir / filename

    def download_episode(
        self,
        episode: Episode,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> DownloadResult:
        """Download a single episode. Skips if file already exists."""
        if not episode.audio_url:
            return DownloadResult(
                episode=episode,
                error="No audio URL available",
            )

        file_path = self._build_filepath(episode)

        # Skip if already downloaded
        if file_path.exists():
            return DownloadResult(
                episode=episode,
                file_path=file_path,
                file_size=file_path.stat().st_size,
                already_existed=True,
                success=True,
            )

        try:
            resp = requests.get(episode.audio_url, stream=True, timeout=60)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise DownloadError(f"Failed to download {episode.audio_url}: {e}") from e

        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0

        try:
            with open(file_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=self.chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)
        except OSError as e:
            # Clean up partial file
            file_path.unlink(missing_ok=True)
            raise DownloadError(f"Failed to write {file_path}: {e}") from e

        return DownloadResult(
            episode=episode,
            file_path=file_path,
            file_size=downloaded,
            success=True,
        )

```
<br>

### `app/radiofrance_downloader/exceptions.py`

```python
"""Custom exception hierarchy for radiofrance-downloader."""


class RadioFranceError(Exception):
    """Base exception for all radiofrance-downloader errors."""


class APIError(RadioFranceError):
    """Error communicating with the Radio France API."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(APIError):
    """Invalid or missing API key."""

    def __init__(self, message: str = "Invalid or missing API key"):
        super().__init__(message, status_code=401)


class ShowNotFoundError(RadioFranceError):
    """Requested show was not found."""


class EpisodeNotFoundError(RadioFranceError):
    """Requested episode was not found."""


class DownloadError(RadioFranceError):
    """Error downloading an episode file."""


class ScrapingError(RadioFranceError):
    """Error scraping a web page."""


class ConfigError(RadioFranceError):
    """Error reading or writing configuration."""

```
<br>

### `app/radiofrance_downloader/__init__.py`

```python

```
<br>

### `app/radiofrance_downloader/__main__.py`

```python
"""Allow running with `python -m radiofrance_downloader`."""

from radiofrance_downloader.cli import main

main()

```
<br>

### `app/radiofrance_downloader/models.py`

```python
"""Data models for radiofrance-downloader."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class StationId(StrEnum):
    """Radio France station/brand identifiers (GraphQL API)."""

    FRANCE_INTER = "FRANCEINTER"
    FRANCE_INFO = "FRANCEINFO"
    FRANCE_CULTURE = "FRANCECULTURE"
    FRANCE_MUSIQUE = "FRANCEMUSIQUE"
    FIP = "FIP"
    MOUV = "MOUV"
    FRANCE_BLEU = "FRANCEBLEU"


@dataclass(frozen=True)
class Station:
    """A Radio France station."""

    id: StationId
    name: str
    url: str


@dataclass(frozen=True)
class Show:
    """A podcast show."""

    id: str
    title: str
    description: str = ""
    url: str = ""
    station: Station | None = None
    image_url: str = ""


@dataclass(frozen=True)
class Episode:
    """A single podcast episode."""

    id: str
    title: str
    description: str = ""
    show_id: str = ""
    show_title: str = ""
    published_at: datetime | None = None
    duration: int = 0
    audio_url: str = ""
    page_url: str = ""
    image_url: str = ""


@dataclass
class DownloadResult:
    """Outcome of a download attempt."""

    episode: Episode
    file_path: Path | None = None
    file_size: int = 0
    already_existed: bool = False
    success: bool = False
    error: str = ""

```
<br>

### `app/radiofrance_downloader/rss.py`

```python
"""RSS feed parser for Radio France podcasts."""

from __future__ import annotations

from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import requests

from radiofrance_downloader.exceptions import RadioFranceError
from radiofrance_downloader.models import Episode

AERION_URL = "https://radiofrance-podcast.net/podcast09/rss_{show_id}.xml"

# Common namespace for iTunes podcast feeds
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


class RSSParser:
    """Parse RSS feeds for Radio France podcasts."""

    def fetch_episodes(self, rss_url: str) -> list[Episode]:
        """Fetch and parse episodes from an RSS feed URL."""
        try:
            resp = requests.get(rss_url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RadioFranceError(f"Failed to fetch RSS feed: {e}") from e

        return self.parse_feed(resp.text)

    def parse_feed(self, xml_text: str) -> list[Episode]:
        """Parse episodes from RSS XML text."""
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            raise RadioFranceError(f"Invalid RSS XML: {e}") from e

        channel = root.find("channel")
        if channel is None:
            return []

        show_title = ""
        title_el = channel.find("title")
        if title_el is not None and title_el.text:
            show_title = title_el.text

        episodes = []
        for item in channel.findall("item"):
            ep = self._parse_item(item, show_title)
            if ep:
                episodes.append(ep)

        return episodes

    def _parse_item(self, item: ElementTree.Element, show_title: str) -> Episode | None:
        """Parse a single RSS <item> into an Episode."""
        title_el = item.find("title")
        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        if not title:
            return None

        desc_el = item.find("description")
        description = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

        guid_el = item.find("guid")
        ep_id = guid_el.text.strip() if guid_el is not None and guid_el.text else title

        link_el = item.find("link")
        page_url = link_el.text.strip() if link_el is not None and link_el.text else ""

        # Audio URL from enclosure
        audio_url = ""
        enclosure = item.find("enclosure")
        if enclosure is not None:
            audio_url = enclosure.get("url", "")

        # Published date
        published_at = None
        pub_date_el = item.find("pubDate")
        if pub_date_el is not None and pub_date_el.text:
            try:
                published_at = parsedate_to_datetime(pub_date_el.text.strip())
            except (ValueError, TypeError):
                pass

        # Duration from itunes:duration
        duration = 0
        dur_el = item.find(f"{{{ITUNES_NS}}}duration")
        if dur_el is not None and dur_el.text:
            duration = self._parse_duration(dur_el.text.strip())

        # Image
        image_url = ""
        img_el = item.find(f"{{{ITUNES_NS}}}image")
        if img_el is not None:
            image_url = img_el.get("href", "")

        return Episode(
            id=ep_id,
            title=title,
            description=description,
            show_title=show_title,
            published_at=published_at,
            duration=duration,
            audio_url=audio_url,
            page_url=page_url,
            image_url=image_url,
        )

    @staticmethod
    def _parse_duration(text: str) -> int:
        """Parse duration text to seconds. Handles HH:MM:SS, MM:SS, or raw seconds."""
        if ":" in text:
            parts = text.split(":")
            if len(parts) == 3:
                h, m, s = (int(p) for p in parts)
                return h * 3600 + m * 60 + s
            elif len(parts) == 2:
                m, s = (int(p) for p in parts)
                return m * 60 + s
        try:
            return int(text)
        except ValueError:
            return 0

    @staticmethod
    def build_aerion_url(show_id: str) -> str:
        """Build RSS feed URL via the Aerion proxy."""
        return AERION_URL.format(show_id=show_id)

```
<br>

### `app/radiofrance_downloader/scraper.py`

```python
"""Web scraping fallback for Radio France shows."""

from __future__ import annotations

import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from radiofrance_downloader.exceptions import ScrapingError
from radiofrance_downloader.models import Episode

RADIOFRANCE_BASE = "https://www.radiofrance.fr"


class RadioFranceScraper:
    """Scrapes Radio France website for episode data."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) "
                    "Gecko/20100101 Firefox/128.0"
                ),
            }
        )

    def get_episodes(self, station: str, show_slug: str) -> list[Episode]:
        """Get episodes from a show page."""
        url = f"{RADIOFRANCE_BASE}/{station}/podcasts/{show_slug}"
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ScrapingError(f"Failed to fetch {url}: {e}") from e

        return self._parse_show_page(resp.text, show_slug)

    def get_episode_audio_url(self, episode_url: str) -> str:
        """Extract audio URL from an episode page."""
        if not episode_url.startswith("http"):
            episode_url = f"{RADIOFRANCE_BASE}{episode_url}"

        try:
            resp = self.session.get(episode_url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ScrapingError(f"Failed to fetch {episode_url}: {e}") from e

        return self._extract_audio_url(resp.text)

    def _parse_show_page(self, html: str, show_slug: str) -> list[Episode]:
        """Parse episode cards from a show page."""
        soup = BeautifulSoup(html, "html.parser")
        episodes = []

        # Try JSON-LD first
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    for item in data:
                        ep = self._parse_jsonld_episode(item)
                        if ep:
                            episodes.append(ep)
                elif isinstance(data, dict):
                    ep = self._parse_jsonld_episode(data)
                    if ep:
                        episodes.append(ep)
            except (json.JSONDecodeError, KeyError):
                continue

        if episodes:
            return episodes

        # Fallback: parse card elements
        cards = soup.select("a.CardEpisode, [class*='CardEpisode'], article.card")
        for card in cards:
            title_el = card.select_one("h2, h3, .title, [class*='title']")
            title = title_el.get_text(strip=True) if title_el else ""
            link = card.get("href", "")
            if link and not link.startswith("http"):
                link = f"{RADIOFRANCE_BASE}{link}"

            if title:
                episodes.append(
                    Episode(
                        id=link.split("/")[-1] if link else title[:50],
                        title=title,
                        page_url=link,
                        show_title=show_slug,
                    )
                )

        return episodes

    def _parse_jsonld_episode(self, data: dict) -> Episode | None:
        """Parse a single episode from JSON-LD data."""
        if data.get("@type") not in ("PodcastEpisode", "RadioEpisode", "AudioObject"):
            return None

        audio_url = ""
        if "contentUrl" in data:
            audio_url = data["contentUrl"]
        elif "associatedMedia" in data:
            media = data["associatedMedia"]
            if isinstance(media, dict):
                audio_url = media.get("contentUrl", "")

        published_at = None
        date_str = data.get("datePublished", "")
        if date_str:
            try:
                published_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        duration = 0
        dur_str = data.get("duration", "")
        if dur_str:
            # Parse ISO 8601 duration (e.g. PT3M30S)
            match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur_str)
            if match:
                h, m, s = (int(x or 0) for x in match.groups())
                duration = h * 3600 + m * 60 + s

        return Episode(
            id=data.get("identifier", data.get("@id", "")),
            title=data.get("name", ""),
            description=data.get("description", ""),
            published_at=published_at,
            duration=duration,
            audio_url=audio_url,
            page_url=data.get("url", ""),
        )

    def _extract_audio_url(self, html: str) -> str:
        """Extract MP3 URL from an episode page."""
        soup = BeautifulSoup(html, "html.parser")

        # Try JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict):
                    url = data.get("contentUrl", "")
                    if url and url.endswith(".mp3"):
                        return url
                    media = data.get("associatedMedia", {})
                    if isinstance(media, dict):
                        url = media.get("contentUrl", "")
                        if url:
                            return url
            except (json.JSONDecodeError, KeyError):
                continue

        # Regex fallback for mp3 URLs
        match = re.search(
            r'https?://media\.radiofrance-podcast\.net/[^\s"\'<>]+\.mp3',
            html,
        )
        if match:
            return match.group(0)

        raise ScrapingError("Could not find audio URL on page")

```
<br>

### `app/radios.py`

```python
from flask import Blueprint, jsonify, request
import os
import json
import requests
import urllib.parse
import urllib.request
import time

import shared

radio_bp = Blueprint('radio_bp', __name__)

# --- CACHE EN MÉMOIRE (Évite de spammer l'API Radio France) ---
rf_cache = {"time": 0, "data": None}

def load_radios():
    if os.path.exists(shared.RADIOS_FILE):
        try:
            with open(shared.RADIOS_FILE, 'r') as f: shared.radios_list = json.load(f)
        except: shared.radios_list = []
    else:
        shared.radios_list = [
            {"name": "RTL2", "uuid": "034d52a3-30dc-4017-8495-004cd65383b1"}, 
            {"name": "101 SMOOTH JAZZ", "uuid": "d28420a4-eccf-47a2-ace1-088c7e7cb7e0"}
        ]
        save_radios()

def save_radios():
    try:
        with open(shared.RADIOS_FILE, 'w') as f: json.dump(shared.radios_list, f)
    except: pass

# =========================================================
# INTÉGRATION API RADIO FRANCE (GraphQL)
# =========================================================
rf_cache = {"time": 0, "data": None}

def get_radiofrance_live(station="FRANCEINTER"):
    """
    Interroge l'API GraphQL de Radio France.
    Utilise un cache de 60s pour protéger les quotas de l'API.
    """
    global rf_cache
    import time
    
    # Vérification du cache (60 secondes)
    if time.time() - rf_cache["time"] < 60 and rf_cache["data"]:
        return rf_cache["data"]

    token = os.environ.get('RF_TOKEN')
    if not token:
        return None
        
    url = "https://openapi.radiofrance.fr/v1/graphql"
    
    # La requête parfaite avec les "Fragments"
    query = """
    query {
      live(station: FRANCEINTER) {
        show {
          ... on BlankStep { title }
          ... on DiffusionStep {
            diffusion {
              title
              standFirst
              show { title }
            }
          }
        }
      }
    }
    """
    
    try:
        response = requests.post(
            url, headers={"x-token": token, "Content-Type": "application/json"}, json={'query': query}, timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            step = data.get('data', {}).get('live', {}).get('show', {})
            
            titre_final = "Direct"
            desc_finale = ""
            
            if step:
                if 'diffusion' in step and step['diffusion']:
                    diffusion = step['diffusion']
                    show_obj = diffusion.get('show', {})
                    if show_obj and show_obj.get('title'):
                        titre_final = show_obj.get('title')
                        desc_finale = diffusion.get('title', diffusion.get('standFirst', ''))
                    else:
                        titre_final = diffusion.get('title', 'Direct')
                        desc_finale = diffusion.get('standFirst', '')
                elif 'title' in step:
                    titre_final = step.get('title')
            
            # Mise en cache et formatage des clés attendues par le Frontend
            rf_cache["data"] = {
                "show_title": titre_final,
                "show_desc": desc_finale,
                "show_image": "https://www.radiofrance.fr/build/images/logos/franceinter-1.svg"
            }
            rf_cache["time"] = time.time()
            return rf_cache["data"]
            
    except Exception as e:
        print(f"Erreur API Radio France: {e}")
        
    return None
    
@radio_bp.route('/api/radios/rf_test', methods=['GET'])
def test_rf_api():
    token = os.environ.get('RF_TOKEN')
    url = "https://openapi.radiofrance.fr/v1/graphql"
    
    # La requête parfaite basée sur ton introspection
    query = """
    query {
      live(station: FRANCEINTER) {
        show {
          ... on BlankStep {
            title
          }
          ... on DiffusionStep {
            diffusion {
              title
              standFirst
              show {
                title
              }
            }
          }
        }
      }
    }
    """
    
    try:
        response = requests.post(
            url, 
            headers={"x-token": token, "Content-Type": "application/json"}, 
            json={'query': query}, 
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # --- LOGIQUE D'EXTRACTION FINALE ---
            step = data.get('data', {}).get('live', {}).get('show', {})
            
            titre_final = "Direct"
            desc_finale = ""
            
            if step:
                # 1. Si c'est une grosse émission (DiffusionStep)
                if 'diffusion' in step and step['diffusion']:
                    diffusion = step['diffusion']
                    show_obj = diffusion.get('show', {})
                    
                    if show_obj and show_obj.get('title'):
                        # Ex: Titre = "La Terre au carré", Desc = "L'actualité de la planète..."
                        titre_final = show_obj.get('title')
                        desc_finale = diffusion.get('title', diffusion.get('standFirst', ''))
                    else:
                        titre_final = diffusion.get('title', 'Direct')
                        desc_finale = diffusion.get('standFirst', '')
                
                # 2. Si c'est un créneau simple (BlankStep, ex: "Le Journal de 13h")
                elif 'title' in step:
                    titre_final = step.get('title')
                    
            return jsonify({
                "status": "VICTOIRE", 
                "emission_en_cours": titre_final,
                "description": desc_finale,
                "json_brut": data
            })
        else:
            return jsonify({"status": "ERREUR", "details": response.text})
            
    except Exception as e:
        return jsonify({"status": "CRASH", "erreur": str(e)})

@radio_bp.route('/api/play_radio', methods=['POST'])
def play_radio():
    data = request.json
    xml = f'<ContentItem source="RADIO_BROWSER" type="stationurl" location="/stations/byuuid/{data.get("uuid")}"><itemName>{data.get("name", "Radio")}</itemName></ContentItem>'
    for ip in data.get('ips', []):
        # --- FIX : On vide la file d'attente DLNA pour libérer l'enceinte ---
        if ip in shared.server_queues:
            shared.server_queues[ip] = {}
        # --------------------------------------------------------------------
        try: requests.post(f"http://{ip}:8090/select", data=xml, headers={"Content-Type": "application/xml"}, timeout=5)
        except: pass
    return jsonify({"status": "ok"})

@radio_bp.route('/api/radios/search', methods=['GET'])
def search_radio():
    query = request.args.get('q', '')
    country_filter = request.args.get('country', 'FR')
    if not query or len(query) < 2: return jsonify([])
    try:
        params = {"name": query, "countrycode": country_filter, "order": "clickcount", "reverse": "true", "limit": 30}
        url = f"https://de1.api.radio-browser.info/json/stations/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "SoundCorkApp/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # On extrait le favicon, sinon on renvoie notre code de secours
            return jsonify([{
                "name": s.get("name"), 
                "uuid": s.get("stationuuid"), 
                "country": s.get("countrycode", "").upper(),
                "logo": s.get("favicon") if s.get("favicon") else "FA_ICON"
            } for s in data])
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

@radio_bp.route('/api/radios/save', methods=['POST'])
def api_save_radios():
    data = request.json
    shared.radios_list = data['radios'] if isinstance(data, dict) and 'radios' in data else data
    save_radios()
    return jsonify({"status": "ok"})
```
<br>

### `app/rf_dwl.py`

```python
# /app/rf_dwl.py
import os
import re
import traceback
import threading
import dataclasses
import requests
from flask import Blueprint, jsonify, request
from radiofrance_downloader.api import RadioFranceAPI
from radiofrance_downloader.config import Config
from radiofrance_downloader.downloader import EpisodeDownloader
from radiofrance_downloader.models import StationId
from radiofrance_downloader.rss import RSSParser
import shared

# Initialisation du Blueprint isolé
rf_dwl_bp = Blueprint('rf_dwl_bp', __name__)

config = Config.load()
config.output_dir = shared.RF_PODCASTS_PATH 

api_key = os.environ.get('RF_TOKEN') or config.api_key
api = RadioFranceAPI(api_key) if api_key else None

downloader = EpisodeDownloader(output_dir=shared.RF_PODCASTS_PATH)

@rf_dwl_bp.route('/api/rf/config-check', methods=['GET'])
def check_config():
    return jsonify({"api_key_set": api is not None, "output_dir": shared.RF_PODCASTS_PATH})

@rf_dwl_bp.route('/api/rf/shows', methods=['GET'])
def search_shows():
    print(f"\n--- 📡 NOUVELLE RECHERCHE RADIO FRANCE ---")
    
    if not api:
        print("❌ CRASH : API non initialisée")
        return jsonify({"error": "API non initialisée"}), 500
        
    query = request.args.get('query', '')
    station = request.args.get('station', '')
    print(f"🔍 Paramètres reçus : query='{query}', station='{station}'")

    try:
        station_id = StationId(station.upper()) if station else None
        shows = api.search_shows(query, station=station_id)
        print(f"✅ Succès API : {len(shows)} émissions trouvées !")
        
        return jsonify([{
            "id": show.id,
            "title": show.title,
            "description": show.description,
            "url": show.url,
            "station": show.station.name if show.station else "Inconnue"
        } for show in shows])
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def safe_download_v9(ep, show_url):
    """Téléchargement V9 - Interception ciblée balises <audio> et format .m4a."""
    try:
        print(f"[V9-START] Début du traitement : {ep.title}")
        
        if not ep.audio_url:
            print(f"[V9-INFO] API muette. Analyse ciblée du code source de la page...")
            audio_url = None
            
            if ep.page_url:
                page_url = ep.page_url
                for d in ['franceinter.fr', 'franceculture.fr', 'franceinfo.fr', 'francemusique.fr', 'francebleu.fr', 'mouv.fr', 'fip.fr']:
                    page_url = page_url.replace(f"www.{d}", "www.radiofrance.fr")
                
                try:
                    r = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    
                    # 1. On cible spécifiquement la nouvelle balise <audio> de Radio France
                    m_audio = re.search(r'<audio[^>]*src=["\']([^"\']+)["\']', r.text)
                    if m_audio:
                        audio_url = m_audio.group(1).replace('\\/', '/')
                    else:
                        # 2. Secours : on cherche les .mp3 OU les nouveaux .m4a
                        m_ext = re.search(r'(https?://[^"\']+\.(?:mp3|m4a))', r.text)
                        if m_ext: 
                            audio_url = m_ext.group(1).replace('\\/', '/')
                except Exception as e:
                    print(f"[V9-WARNING] Analyse de la page a échoué : {e}")
            
            if audio_url:
                ep = dataclasses.replace(ep, audio_url=audio_url)
                print(f"[V9-SUCCESS-SCRAPER] URL Audio trouvée : {audio_url}")
            else:
                print(f"[V9-ERROR] Impossible de trouver l'audio (.mp3 ou .m4a) sur la page.")

        result = downloader.download_episode(ep)
        
        if result.success:
            if result.already_existed:
                print(f"[V9-INFO] Fichier déjà présent sur le SSD : {ep.title}")
            else:
                print(f"[V9-SUCCESS] Téléchargement terminé : {ep.title} ({result.file_size} octets)")
        else:
            print(f"[V9-ERROR] Échec final : {result.error}")
            
    except Exception as e:
        print(f"[V9-CRITICAL] Exception fatale : {e}")
        traceback.print_exc()

@rf_dwl_bp.route('/api/rf/download', methods=['POST'])
def download_episode():
    if not api:
        return jsonify({"error": "Clé API manquante"}), 500
    
    data = request.json or {}
    show_url = data.get('show_url')
    latest_n = int(data.get('latest_n', 1))
    
    if not show_url:
        return jsonify({"error": "URL manquante."}), 400
        
    try:
        print(f"[V9-INFO] Demande reçue pour : {show_url}")
        
        web_url = show_url
        for d in ['franceinter.fr', 'franceculture.fr', 'franceinfo.fr', 'francemusique.fr', 'francebleu.fr', 'mouv.fr', 'fip.fr']:
            web_url = web_url.replace(f"www.{d}", "www.radiofrance.fr")
            
        eps_to_download = []
        rss_url = None
        
        print(f"[V9-INFO] Interception du lien RSS officiel dans le HTML...")
        try:
            r = requests.get(web_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code == 200:
                # On cible leur nouveau format exact d'URL (podcast_UUID.xml)
                m_rss = re.search(r'href=["\'](https?://radiofrance-podcast\.net/[^"\']+\.xml)["\']', r.text)
                if m_rss:
                    rss_url = m_rss.group(1)
        except Exception as e:
            print(f"[V9-WARNING] Échec de la lecture HTML : {e}")

        if rss_url:
            print(f"[V9-SUCCESS] Flux RSS intercepté : {rss_url}")
            parser = RSSParser()
            try:
                all_eps = parser.fetch_episodes(rss_url)
                eps_to_download = all_eps[:latest_n]
                print(f"[V9-INFO] Épisodes extraits du flux RSS avec succès.")
            except Exception as e:
                print(f"[V9-WARNING] Lecture du flux RSS échouée ({e}).")
        
        if not eps_to_download:
            print(f"[V9-INFO] Bascule sur l'API GraphQL pour avoir au moins les titres...")
            base_eps, _ = api.get_show_episodes(show_url, fetch_all=False)
            if not base_eps:
                return jsonify({"error": "Aucun épisode trouvé."}), 404
            eps_to_download = base_eps[:latest_n]

        for ep in eps_to_download:
            print(f"[V9-INFO] Planification : {ep.title}")
            threading.Thread(target=safe_download_v9, args=(ep, web_url), daemon=True).start()
            
        return jsonify({"message": f"Téléchargement lancé !"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400
```
<br>

### `app/shared.py`

```python
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
```
<br>

### `app/soundtouch_api.py`

```python
from flask import Blueprint, jsonify, request
import os
import xml.etree.ElementTree as ET
import requests
from requests.exceptions import RequestException
import threading
import time
import urllib.parse
import re
import json
import socket
import subprocess
from datetime import datetime
from zeroconf import Zeroconf, ServiceBrowser

import shared
from dlna import play_next_in_queue

soundtouch_bp = Blueprint('soundtouch_bp', __name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOGOS_DIR = '/app/www/img/radios'
WEB_LOGO_DIR = '/www/img/radios'
GENERIC_LOGO = 'FA_ICON'
LOGOS_CACHE_FILE = '/app/tools_data/radio_logos_cache.json'
CUSTOM_LOGOS_FILE = '/app/tools_data/custom_logos.json'

os.makedirs(LOGOS_DIR, exist_ok=True)

# --- OUTIL DE DEBUG ---
def st_log(msg):
    print(f"[ST-DEBUG] {datetime.now().strftime('%H:%M:%S.%f')[:-3]} | {msg}", flush=True)

radio_logos_cache = {}
if os.path.exists(LOGOS_CACHE_FILE):
    try:
        with open(LOGOS_CACHE_FILE, 'r') as f:
            radio_logos_cache = json.load(f)
    except Exception:
        pass

def save_logos_cache():
    try:
        with open(LOGOS_CACHE_FILE, 'w') as f:
            json.dump(radio_logos_cache, f)
    except:
        pass

def sanitize_filename(name):
    return re.sub(r'(?u)[^-\w.]', '', str(name).strip().replace(' ', '_'))

def load_custom_logos():
    default_logos = {
        "101 smooth jazz": "https://cdn-radiotime-logos.tunein.com/s24368q.png"
    }
    if not os.path.exists(CUSTOM_LOGOS_FILE):
        try:
            with open(CUSTOM_LOGOS_FILE, 'w') as f:
                json.dump(default_logos, f, indent=4)
        except:
            pass
        return default_logos

    try:
        with open(CUSTOM_LOGOS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return default_logos

def get_radio_logo(source, identifier, name):
    if not name or name == "Inconnue":
        return GENERIC_LOGO

    clean_name = name.split("-")[0].strip()
    cache_key = clean_name
    search_name = clean_name.lower()
    
    if cache_key in radio_logos_cache:
        if radio_logos_cache[cache_key] != GENERIC_LOGO:
            return radio_logos_cache[cache_key]

    logo_url_to_download = None

    try:
        custom_logos_dict = load_custom_logos()
        if search_name in custom_logos_dict:
            logo_url_to_download = custom_logos_dict[search_name]

        if not logo_url_to_download:
            r = requests.get(f"https://itunes.apple.com/search?term={urllib.parse.quote(clean_name + ' radio')}&limit=5&country=fr", timeout=5.0)
            if r.status_code == 200:
                results = r.json().get('results', [])
                for item in results:
                    if clean_name.lower() in item.get('collectionName', '').lower() or clean_name.lower() in item.get('trackName', '').lower():
                        img = item.get('artworkUrl600') or item.get('artworkUrl100')
                        if img:
                            logo_url_to_download = img.replace("100x100", "600x600")
                            break
                if not logo_url_to_download and results:
                    img = results[0].get('artworkUrl600') or results[0].get('artworkUrl100')
                    if img: logo_url_to_download = img.replace("100x100", "600x600")

        if not logo_url_to_download:
            r = requests.get(f"https://api.deezer.com/search/radio?q={urllib.parse.quote(clean_name)}", timeout=5.0)
            if r.status_code == 200:
                data = r.json()
                if data.get('data') and len(data['data']) > 0:
                    logo_url_to_download = data['data'][0].get('picture_xl') or data['data'][0].get('picture_medium')

        if not logo_url_to_download and source == "RADIO_BROWSER" and identifier:
            clean_uuid = identifier.split("/")[-1] 
            if clean_uuid and len(clean_uuid) > 10:
                r = requests.get(f"https://de1.api.radio-browser.info/json/stations/byuuid/{clean_uuid}", headers={"User-Agent": "SoundCorkApp/1.0"}, timeout=5.0)
                if r.status_code == 200:
                    data = r.json()
                    if data and data[0].get('favicon') and not "default" in data[0]['favicon']:
                        logo_url_to_download = data[0]['favicon']

        if logo_url_to_download:
            headers = {'User-Agent': 'SoundCorkApp/1.0 (HomeNetwork)'}
            img_r = requests.get(logo_url_to_download, headers=headers, timeout=10.0, allow_redirects=True)
            
            if img_r.status_code == 200:
                ext = ".jpg" if "jpeg" in img_r.headers.get("Content-Type", "") or "jpg" in logo_url_to_download.lower() else ".png"
                if ".svg" in logo_url_to_download.lower(): ext = ".svg"
                filename = f"{sanitize_filename(clean_name)}{ext}"
                filepath = os.path.join(LOGOS_DIR, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(img_r.content)
                    
                public_path = f"{WEB_LOGO_DIR}/{filename}"
                radio_logos_cache[cache_key] = public_path
                save_logos_cache()
                return public_path

    except Exception:
        pass

    return GENERIC_LOGO

def is_host_online(ip):
    """ 
    Vérifie si l'enceinte est en ligne.
    Physique : Ping ICMP (2 paquets).
    Virtuelle : HTTP GET sur /info (Le ping de l'OS fausserait le test).
    """
    is_virtual = False
    if hasattr(shared, 'speakers') and ip in shared.speakers:
        is_virtual = shared.speakers[ip].get('is_virtual', False)

    if is_virtual:
        try:
            r = requests.get(f"http://{ip}:8090/info", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False
    else:
        try:
            res = subprocess.run(['ping', '-c', '2', '-W', '2', ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return res.returncode == 0
        except Exception as e:
            st_log(f"[Ping ICMP] Erreur d'exécution : {e}")
            return False

def check_stereo_groups():
    if not hasattr(shared, 'speakers'): return
    
    slaves_to_hide = []
    for ip in list(shared.speakers.keys()):
        # Optimisation : On ignore les enceintes qui ne sont pas des ST10
        is_st10 = shared.speakers[ip].get('is_st10')
        if is_st10 is False:
            continue

        try:
            r = requests.get(f"http://{ip}:8090/getGroup", timeout=10.0)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                status = root.findtext('status')
                if status == 'GROUP_OK':
                    group_name = root.findtext('name')
                    master_id = root.findtext('masterDeviceId')
                    if master_id: master_id = master_id.upper()
                    
                    roles = root.find('roles')
                    if roles is not None:
                        for role_node in roles.findall('groupRole'):
                            dev_id = role_node.findtext('deviceId')
                            if dev_id: dev_id = dev_id.upper()
                            dev_ip = role_node.findtext('ipAddress')
                            
                            if dev_id == master_id:
                                if dev_ip in shared.speakers:
                                    shared.speakers[dev_ip]['name'] = group_name
                                    shared.speakers[dev_ip]['is_stereo_master'] = True
                            else:
                                if dev_ip:
                                    slaves_to_hide.append(dev_ip)
        except Exception:
            pass 
            
    for slave_ip in slaves_to_hide:
        if slave_ip in shared.speakers:
            shared.speakers[slave_ip]['is_stereo_slave'] = True
            shared.speakers[slave_ip]['state'] = 'OFF'

class SoundTouchListener:
    def add_service(self, zeroconf, type, name):
        self._process_service(zeroconf, type, name)

    def update_service(self, zeroconf, type, name):
        self._process_service(zeroconf, type, name)

    def remove_service(self, zeroconf, type, name): 
        pass

    def _process_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if not info: return
            
        ip = None
        if hasattr(info, 'parsed_addresses'):
            for addr in info.parsed_addresses():
                if '.' in addr:
                    ip = addr
                    break
                    
        if not ip and info.addresses:
            for addr in info.addresses:
                if len(addr) == 4:
                    try:
                        ip = socket.inet_ntoa(addr)
                        break
                    except:
                        pass
                
        if not ip: return

        device_id = None
        if info.properties:
            for k, v in info.properties.items():
                k_str = k.decode('utf-8').upper() if isinstance(k, bytes) else str(k).upper()
                if k_str == 'MAC' and v:
                    device_id = v.decode('utf-8').upper() if isinstance(v, bytes) else str(v).upper()
                    break

        if not device_id: return

        st_log(f"[mDNS] Détection de {name} sur IP {ip} (MAC: {device_id})")

        if not hasattr(shared, 'speakers'): shared.speakers = {}
        
        old_ip_to_delete = None
        for existing_ip, spk_data in shared.speakers.items():
            if spk_data.get('deviceID') == device_id and existing_ip != ip:
                old_ip_to_delete = existing_ip
                break

        if old_ip_to_delete:
            st_log(f"[mDNS] Migration d'IP DHCP pour {device_id}: {old_ip_to_delete} -> {ip}")
            shared.speakers[ip] = shared.speakers.pop(old_ip_to_delete)
            try:
                from bose_websocket import bose_ws_manager
                bose_ws_manager.stop_listening(old_ip_to_delete)
                bose_ws_manager.start_listening(ip)
            except Exception as e:
                st_log(f"[mDNS] Erreur WebSocket migration: {e}")

def parse_device_info():
    st_log("[SoundCork] Synchronisation de l'administration...")
    if not hasattr(shared, 'speakers'): shared.speakers = {}
    found_devices = {}
    account_id = None
    
    try:
        port = getattr(shared, 'SOUNDCORK_PORT', 8000)
        url = f"http://127.0.0.1:{port}/admin/"
        resp = requests.get(url, timeout=15.0)
        
        if resp.status_code == 200:
            html = resp.text
            
            # --- Extraction du compte intégrée ici ---
            account_match = re.search(r'<h2>\s*Account\s+(\d+)\s*</h2>', html, re.IGNORECASE)
            if account_match:
                account_id = account_match.group(1)
                st_log(f"[SoundCork] Account ID extrait : {account_id}")
            else:
                st_log("[SoundCork] AVERTISSEMENT : Account ID introuvable dans la page.")

            pattern = re.compile(r'/admin/edit_device/([A-Fa-f0-9]+)[^>]*>.*?</td>\s*<td>\s*([0-9\.]+)\s*</td>\s*<td>\s*([^<]+?)\s*</td>', re.IGNORECASE)
            matches = pattern.findall(html)
            
            for device_id, ip, name in matches:
                found_devices[device_id.upper()] = {"ip": ip.strip(), "name": name.strip()}
    except Exception as e:
        st_log(f"[SoundCork] Erreur connexion admin : {e}")

    if not found_devices:
        return

    for dev_id, info in found_devices.items():
        ip = info['ip']
        name = info['name']

        if ip in shared.speakers:
            is_master = shared.speakers[ip].get('is_stereo_master', False)
            current_name = shared.speakers[ip].get('name')
            
            if shared.speakers[ip].get('deviceID') != dev_id:
                st_log(f"[SoundCork] Mise à jour du DeviceID pour {ip}: {dev_id}")
                shared.speakers[ip]['deviceID'] = dev_id
                
            if not is_master and current_name != name:
                st_log(f"[SoundCork] Mise à jour du nom pour {ip}: {name}")
                shared.speakers[ip]['name'] = name
        else:
            st_log(f"[SoundCork] Ajout NOUVELLE enceinte depuis l'admin: {ip} - {name} ({dev_id})")
            shared.speakers[ip] = {
                "name": name, 
                "state": "OFF", 
                "discovered": False,
                "deviceID": dev_id
            }
            try:
                from bose_websocket import bose_ws_manager
                bose_ws_manager.start_listening(ip)
            except Exception as e:
                st_log(f"[SoundCork] Erreur WebSocket pour {ip} : {e}")

    # --- Identification des modèles via le endpoint /full ---
    try:
        if not account_id:
            st_log("[SoundCork] Impossible de requêter /full (Account ID manquant).")
        else:
            port = getattr(shared, 'SOUNDCORK_PORT', 8000)
            url_full = f"http://127.0.0.1:{port}/marge/streaming/account/{account_id}/full"
            resp_full = requests.get(url_full, timeout=10.0)
            
            if resp_full.status_code == 200:
                root_full = ET.fromstring(resp_full.content)
                for device in root_full.findall('.//device'):
                    ip = device.findtext('ipaddress')
                    product_node = device.find('attachedProduct')
                    
                    if ip and ip in shared.speakers and product_node is not None:
                        product_code = product_node.attrib.get('product_code', '')
                        shared.speakers[ip]['is_st10'] = ('SoundTouch 10' in product_code)
                        shared.speakers[ip]['is_virtual'] = ('SoundTouch Virtual' in product_code)
                    
    except Exception as e:
        st_log(f"[SoundCork] Erreur récupération du type d'enceintes via /full : {e}")

def get_device_id(ip):
    try:
        resp = requests.get(f"http://{ip}:8090/nowPlaying", timeout=10.0)
        dev_id = ET.fromstring(resp.content).attrib.get('deviceID')
        return dev_id.upper() if dev_id else None
    except: return None

def get_presets():
    if not hasattr(shared, 'speakers'): shared.speakers = {}
    for ip, data in list(shared.speakers.items()):
        if data.get('is_stereo_slave') or data.get('state') == 'OFF':
            continue
            
        try:
            r = requests.get(f"http://{ip}:8090/presets", timeout=10.0)
            if r.status_code == 200:
                presets = {}
                for p in ET.fromstring(r.content).findall('preset'):
                    item = p.find('ContentItem')
                    if item is not None and item.find('itemName') is not None:
                        presets[p.get('id')] = item.find('itemName').text
                return presets
        except:
            continue
    return {}

def update_speaker_state(ip):
    st_log(f"[Scan HTTP] Scan complet initié pour {ip}...")
    if not hasattr(shared, 'speaker_last_states'): shared.speaker_last_states = {}
    if not hasattr(shared, 'speaker_last_sources'): shared.speaker_last_sources = {}
    if not hasattr(shared, 'server_queues'): shared.server_queues = {}
    if not hasattr(shared, 'speakers'): shared.speakers = {}
    
    if ip not in shared.speakers: return
        
    spk = shared.speakers[ip]
    prev_state = spk.get("state", "OFF")
    
    try:
        r_np = requests.get(f"http://{ip}:8090/nowPlaying", timeout=20.0)
        r_np.raise_for_status()
        
        root = ET.fromstring(r_np.content)
        
        dev_id = root.attrib.get('deviceID')
        if dev_id:
            spk['deviceID'] = dev_id.upper()
            
        source = root.attrib.get('source', '') or ''
        source_account = root.attrib.get('sourceAccount', '') or ''
        
        if source == "STANDBY":
            spk['state'] = "STANDBY"
        elif source:
            spk['state'] = "ON"
        else:
            spk['state'] = "STANDBY" 
            
        st_log(f"[Scan HTTP] {ip} est {spk['state']} (Source: {source})")

        spk['source'] = source
        spk['playStatus'] = root.findtext('playStatus') or ""
        spk['track'] = root.findtext("track") or ""
        spk['artist'] = root.findtext("artist") or ""
        spk['album'] = root.findtext("album") or ""
        
        art = root.find("art")
        spk['cover'] = art.text.strip() if art is not None and art.text else ""
        
        content_item = root.find("ContentItem")
        spk['playlist'] = content_item.findtext("itemName") if content_item is not None else ""
        location = content_item.attrib.get("location", "") if content_item is not None else ""
        
        spk['shuffleSetting'] = root.findtext('shuffleSetting') or ""
        spk['repeatSetting'] = root.findtext('repeatSetting') or ""
        spk['offset'] = root.findtext('.//offset') or ""

        time_node = root.find("time")
        if time_node is not None:
            spk['elapsed'] = int(time_node.text) if time_node.text else 0
            spk['total'] = int(time_node.get('total', '0'))
            spk['time_total'] = time_node.get('total', '0')
            spk['time_position'] = time_node.text
        else:
            spk['elapsed'] = 0
            spk['total'] = 0
            spk['time_total'] = "0"
            spk['time_position'] = "0"

        spk['discovered'] = True 

    except Exception as e:
        st_log(f"[Scan HTTP] ECHEC/Timeout nowPlaying pour {ip} : {e}")
        spk['state'] = "OFF"
        spk['discovered'] = False

    if spk['state'] != "OFF":
        try:
            r_vol = requests.get(f"http://{ip}:8090/volume", timeout=10.0)
            if r_vol.status_code == 200:
                vol_root = ET.fromstring(r_vol.content)
                actual_vol = vol_root.findtext('actualvolume')
                if actual_vol:
                    spk['volume'] = int(actual_vol)
        except Exception as e:
            st_log(f"[Scan HTTP] Impossible de lire le volume sur {ip} : {e}")

        try:
            r_zone = requests.get(f"http://{ip}:8090/getZone", timeout=10.0)
            if r_zone.status_code == 200:
                zone_root = ET.fromstring(r_zone.content)
                master_id = zone_root.attrib.get('master')
                spk['is_zone_master'] = bool(master_id and spk.get('deviceID') and master_id.upper() == spk['deviceID'])
        except: pass
        
        if not hasattr(shared, 'speaker_sources_cache'):
            setattr(shared, 'speaker_sources_cache', {})
        
        if ip not in shared.speaker_sources_cache:
            try:
                r_src = requests.get(f"http://{ip}:8090/sources", timeout=10.0)
                if r_src.status_code == 200:
                    src_tree = ET.fromstring(r_src.content)
                    shared.speaker_sources_cache[ip] = {}
                    if not hasattr(shared, 'speaker_supported_sources'):
                        shared.speaker_supported_sources = {}
                    shared.speaker_supported_sources[ip] = []

                    for item in src_tree.findall('sourceItem'):
                        acc = item.get('sourceAccount')
                        src = item.get('source')
                        if acc:
                            shared.speaker_sources_cache[ip][acc] = item.text or ''
                        
                        val = acc if (acc and acc != 'VIRTUAL') else src
                        if val and val not in shared.speaker_supported_sources[ip]:
                            shared.speaker_supported_sources[ip].append(val)
            except: pass

        try:
            r_power = requests.get(f"http://{ip}:8090/powerManagement", timeout=10.0)
            if r_power.status_code == 200:
                power_root = ET.fromstring(r_power.content)
                battery_node = power_root.find('.//battery')
                if battery_node is not None:
                    spk['battery_capable'] = (battery_node.findtext('capable') == 'true')
                    if spk['battery_capable']:
                        pct_str = battery_node.findtext('percentCharge')
                        spk['battery_percent'] = int(pct_str) if pct_str else 0
                        spk['running_on_battery'] = (battery_node.findtext('runningOnBattery') == 'true')
        except Exception as e:
            st_log(f"[Scan HTTP] Impossible de lire la batterie sur {ip} : {e}")

        spk['supported_sources'] = getattr(shared, 'speaker_supported_sources', {}).get(ip, [])

        display_source = spk['source']
        if spk['source'] == 'STORED_MUSIC' and source_account:
            server_name = shared.speaker_sources_cache.get(ip, {}).get(source_account)
            if server_name:
                display_source = f"STORED_MUSIC ({server_name})"
        spk['source'] = display_source

        prev_status = shared.speaker_last_states.get(ip, '')
        prev_source = shared.speaker_last_sources.get(ip, '') or ''
        
        is_end_of_track = False
        if spk['source'] == 'INVALID_SOURCE' and (prev_source.startswith('LOCAL_INTERNET_RADIO') or prev_source.startswith('STORED_MUSIC')):
            is_end_of_track = True
        elif prev_status in ['PLAY_STATE', 'BUFFERING_STATE'] and spk['playStatus'] in ['STOP_STATE', 'STANDBY']:
            is_end_of_track = True
        
        if is_end_of_track:
            queue = shared.server_queues.get(ip)
            if queue and queue.get('tracks'):
                def delayed_next():
                    time.sleep(1.0) 
                    from dlna import play_next_in_queue
                    play_next_in_queue(ip)
                threading.Thread(target=delayed_next, daemon=True).start()
        
        shared.speaker_last_states[ip] = spk['playStatus']
        shared.speaker_last_sources[ip] = spk['source']

        try:
            queue = getattr(shared, 'server_queues', {}).get(ip)
            is_proxy_dlna = bool(queue and queue.get('tracks') and spk['source'] == "LOCAL_INTERNET_RADIO")

            if spk['source'] in ["RADIO_BROWSER", "LOCAL_INTERNET_RADIO"] and not is_proxy_dlna:
                identifier = spk['playlist']
                if spk['source'] == "RADIO_BROWSER" and "byuuid/" in location:
                    identifier = location.split("byuuid/")[-1]
                
                search_name = spk['playlist'] if spk['playlist'] else spk['track']
                if hasattr(shared, 'radios_list') and identifier:
                    for r in shared.radios_list:
                        if str(r.get('uuid')) == str(identifier):
                            search_name = r.get('name', search_name)
                            break
                
                cached_logo = get_radio_logo(spk['source'], identifier, search_name)
                spk['cover'] = cached_logo if cached_logo else GENERIC_LOGO
                
                if spk['artist'] == "LOCAL_INTERNET_RADIO":
                    spk['artist'] = ""
                    
            elif queue and queue.get('tracks') and (spk['source'] in ["LOCAL_INTERNET_RADIO", "INVALID_SOURCE"]):
                q_idx = queue.get('index', 0)
                if q_idx < len(queue['tracks']):
                    current_track = queue['tracks'][q_idx]
                    spk['source'] = "LOCAL_INTERNET_RADIO (Fichiers locaux)"
                    spk['state'] = "ON"
                    spk['playStatus'] = "PLAY_STATE" if not is_end_of_track else "BUFFERING_STATE"
                    spk['track'] = current_track.get('title', spk['track'])
                    spk['artist'] = current_track.get('artist', 'Inconnu')
                    spk['album'] = current_track.get('album', '')
                    spk['total'] = current_track.get('duration_secs', 0)
                    now = time.time()
                    spk['shuffleSetting'] = queue.get('shuffle_setting', 'SHUFFLE_OFF')
                    spk['repeatSetting'] = queue.get('repeat_setting', 'REPEAT_OFF')
                    
                    if spk['playStatus'] == "PLAY_STATE" and not is_end_of_track:
                        delta = now - queue.get('last_updated', now)
                        if 0 < delta < 10: queue['elapsed_accumulator'] += delta
                        queue['last_updated'] = now
                        spk['elapsed'] = int(queue['elapsed_accumulator'])
                    else:
                        queue['last_updated'] = now
                        spk['elapsed'] = int(queue.get('elapsed_accumulator', 0))

                    art_url = current_track.get('cover', spk['cover'])
                    if not art_url or art_url.strip() == "" or "SHOW_DEFAULT_IMAGE" in str(art_url):
                        art_url = "/www/img/generic-cover.jpg"
                        current_track['cover'] = art_url
                    spk['cover'] = art_url  
                    if spk['elapsed'] > spk['total']: spk['elapsed'] = spk['total']
                    
        except Exception:
            pass
            
        if spk['source'] in ["INVALID_SOURCE", "STORED_MUSIC"] or spk['source'] == "LOCAL_INTERNET_RADIO (Fichiers locaux)": 
            spk['state'] = "ON"

    shared.speakers[ip] = spk
    
    if prev_state != spk['state']:
        st_log(f"[Scan HTTP] Changement d'état détecté pour {ip}: {prev_state} -> {spk['state']}")
        try:
            from shared import socketio
            socketio.emit('bose_update', {'speakers': shared.speakers})
        except: pass

def background_tasks():
    st_log("[Background] Démarrage des tâches de fond...")
    try:
        zeroconf = Zeroconf()
        listener = SoundTouchListener()
        browser = ServiceBrowser(zeroconf, "_soundtouch._tcp.local.", listener)
        st_log("[Background] mDNS Browser démarré.")
    except Exception as e:
        st_log(f"[Background] Erreur lancement mDNS : {e}")
    
    def prefetch_logos():
        time.sleep(5)
        if hasattr(shared, 'radios_list'):
            for r in shared.radios_list:
                clean_name = r.get('name', '').split('-')[0].strip()
                if clean_name not in radio_logos_cache or radio_logos_cache.get(clean_name) == GENERIC_LOGO:
                    get_radio_logo("RADIO_BROWSER", r.get('uuid', ''), r.get('name', ''))
    threading.Thread(target=prefetch_logos, daemon=True).start()

    # Synchronisation initiale
    parse_device_info()
    
    # Grand scan initial (1 thread par enceinte)
    if hasattr(shared, 'speakers'):
        for ip in list(shared.speakers.keys()):
            if not shared.speakers[ip].get('is_stereo_slave'):
                threading.Thread(target=update_speaker_state, args=(ip,), daemon=True).start()
    
    last_group_check = 0
    last_sync_check = time.time()
    
    while True:
        try:
            now = time.time()
            if now - last_group_check > 120:
                threading.Thread(target=check_stereo_groups, daemon=True).start()
                last_group_check = now
                
            if now - last_sync_check > 120:
                threading.Thread(target=parse_device_info, daemon=True).start()
                last_sync_check = now
                
            # --- SURVEILLANCE SILENCIEUSE ---
            if hasattr(shared, 'speakers'):
                for ip in list(shared.speakers.keys()):
                    if shared.speakers[ip].get('is_stereo_slave'):
                        continue
                    
                    est_en_ligne = is_host_online(ip)
                    etat_actuel = shared.speakers[ip].get('state', 'OFF')
                    
                    if est_en_ligne and etat_actuel == 'OFF':
                        st_log(f"[Ping] {ip} est de retour sur le réseau ! Lancement du scan HTTP.")
                        threading.Thread(target=update_speaker_state, args=(ip,), daemon=True).start()
                    
                    elif not est_en_ligne and etat_actuel != 'OFF':
                        # Anti-faux-positif : on revérifie dans 2 secondes
                        time.sleep(2)
                        if not is_host_online(ip):
                            st_log(f"[Ping] {ip} injoignable. Passage en OFF.")
                            shared.speakers[ip]['state'] = 'OFF'
                            shared.speakers[ip]['discovered'] = False
                            try:
                                from shared import socketio
                                socketio.emit('bose_update', {'speakers': shared.speakers})
                            except: pass

        except Exception as e:
            st_log(f"[Background] Exception boucle principale : {e}")
            
        time.sleep(15)

@soundtouch_bp.route('/api/data')
def get_data():
    enriched_radios = []
    if hasattr(shared, 'radios_list'):
        for r in shared.radios_list:
            r_copy = dict(r)
            clean_name = r_copy.get('name', '').split('-')[0].strip()
            
            if clean_name not in radio_logos_cache or radio_logos_cache.get(clean_name) == GENERIC_LOGO:
                threading.Thread(target=get_radio_logo, args=("RADIO_BROWSER", r.get('uuid', ''), r.get('name', '')), daemon=True).start()
                r_copy['logo'] = GENERIC_LOGO
            else:
                r_copy['logo'] = radio_logos_cache[clean_name]
            enriched_radios.append(r_copy)

    return jsonify({
        "speakers": shared.speakers if hasattr(shared, 'speakers') else {}, 
        "presets": get_presets(), 
        "radios": enriched_radios
    })
    
@soundtouch_bp.route('/api/poll', methods=['POST'])
def force_poll_all():
    st_log("[API] Requête POST /api/poll reçue (Forçage manuel)")
    if hasattr(shared, 'speakers'):
        for ip in list(shared.speakers.keys()):
            if shared.speakers[ip].get('is_stereo_slave'):
                continue
            threading.Thread(target=update_speaker_state, args=(ip,), daemon=True).start()
            try:
                from bose_websocket import bose_ws_manager
                bose_ws_manager.start_listening(ip)
            except Exception as e:
                st_log(f"[API] Erreur relance WS pour {ip}: {e}")
    return jsonify({"status": "success"})
    
@soundtouch_bp.route('/api/create_zone', methods=['POST'])
def create_zone():
    data = request.json
    ips = data.get('ips', [])
    if len(ips) < 2: return jsonify({"status": "error", "message": "Il faut au moins 2 enceintes"})
    members = [{'ip': ip, 'id': get_device_id(ip)} for ip in ips if get_device_id(ip)]
    master = members[0]
    xml_data = f'<zone master="{master["id"]}">' + ''.join([f'<member ipaddress="{m["ip"]}">{m["id"]}</member>' for m in members]) + '</zone>'
    requests.post(f"http://{master['ip']}:8090/setZone", data=xml_data, headers={'Content-Type': 'text/xml'})
    return jsonify({"status": "success"})

@soundtouch_bp.route('/api/create_stereo', methods=['POST'])
def create_stereo():
    data = request.json
    master_ip = data.get('master_ip')
    slave_ip = data.get('slave_ip')
    group_name = data.get('name', 'Paire Stéréo')
    
    if not master_ip or not slave_ip:
        return jsonify({"status": "error", "message": "IPs manquantes"})
        
    master_id = get_device_id(master_ip)
    slave_id = get_device_id(slave_ip)
    
    if not master_id or not slave_id:
        return jsonify({"status": "error", "message": "Impossible de lire l'ID des enceintes. Sont-elles allumées ?"})
    
    xml_data = f"""<?xml version="1.0" encoding="UTF-8" ?>
    <group>
        <name>{group_name}</name>
        <masterDeviceId>{master_id}</masterDeviceId>
        <roles>
            <groupRole>
                <deviceId>{master_id}</deviceId>
                <role>LEFT</role>
                <ipAddress>{master_ip}</ipAddress>
            </groupRole>
            <groupRole>
                <deviceId>{slave_id}</deviceId>
                <role>RIGHT</role>
                <ipAddress>{slave_ip}</ipAddress>
            </groupRole>
        </roles>
    </group>"""
    try:
        requests.post(f"http://{master_ip}:8090/setGroup", data=xml_data.encode('utf-8'), headers={'Content-Type': 'application/xml'}, timeout=10.0)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

    return jsonify({"status": "success"})
```
<br>

### `app/tools.py`

```python
from flask import Blueprint, request, render_template_string
import os
import subprocess
import configparser
import time

import shared

tools_bp = Blueprint('tools_bp', __name__)
TTYD_PORT = 8081  # Port dédié à ttyd (évite le conflit avec le WS Bose 8080)

@tools_bp.route('/tools')
def tools_dashboard():
    config = configparser.ConfigParser()
    config.read(shared.TOOLS_CONFIG_PATH)
    sections = {s: dict(config.items(s)) for s in config.sections()}
    
    # Chemin absolu adapté à ton montage Docker (./www monté dans /app/www)
    html_path = os.path.join(os.path.dirname(__file__), 'www', 'tools.html')
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    return render_template_string(html_content, config=sections)

@tools_bp.route('/run_tool', methods=['POST'])
def run_tool():
    section = request.form.get('section')
    config = configparser.ConfigParser()
    config.read(shared.TOOLS_CONFIG_PATH)
    
    if section not in config: 
        return "Erreur", 400
        
    script_path = config[section]['script']
    args = []
    for i in range(1, 4):
        if f'arg{i}_label' in config[section]: 
            args.append(request.form.get(f'arg{i}', ''))

    # 1. On tue violemment l'ancien processus
    os.system("pkill -9 ttyd")
    time.sleep(0.5)
    
    # 2. Construction de la commande : on lance le script, puis on reste dans un shell (exec bash)
    # On transforme la liste args en chaîne de caractères pour le bash -c
    full_args = " ".join(args)
    cmd = f"{script_path} {full_args}; exec bash"
    
    # 3. Lancement avec bash -c pour maintenir la session ouverte
    subprocess.Popen(["ttyd", "-W", "-p", str(TTYD_PORT), "-i", "0.0.0.0", "bash", "-c", cmd])
    
    # 4. On attend 1 seconde pour que ttyd ait le temps d'écouter
    time.sleep(1.0)
    
    return f"<script>window.location.href = 'http://{request.host.split(':')[0]}:{TTYD_PORT}';</script>"
```
<br>

### `app/update_radio_logo.py`

```python
import requests
import os
import urllib.parse
import json
import re

# ==========================================
# CONFIGURATION DE PRODUCTION
# ==========================================
LOGOS_CACHE_FILE = '/home/pi/sc_tools/data/radio_logos_cache.json' 
LOGOS_DIR = '/home/pi/sc_tools/www/img/radios' 

# User-Agent pour passer les sécurités des serveurs d'images
NAVIGATOR_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ==========================================
# FONCTIONS DE RECHERCHE (Par ordre de qualité)
# ==========================================

def get_itunes_clean_logo(radio_name):
    """ Priorité 1 : API iTunes (Haute résolution 600x600) """
    try:
        search_query = urllib.parse.quote(radio_name)
        url = f"https://itunes.apple.com/search?term={search_query}&limit=5&country=fr"
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            if results:
                # Cherche une correspondance exacte d'abord
                for item in results:
                    collection = item.get('collectionName', '').lower()
                    track = item.get('trackName', '').lower()
                    if radio_name.lower() in collection or radio_name.lower() in track:
                        img_url = item.get('artworkUrl100') or item.get('artworkUrl600')
                        if img_url:
                            return img_url.replace("100x100", "600x600")
                # Sinon prend le premier résultat
                return results[0].get('artworkUrl600') or results[0].get('artworkUrl100')
    except Exception:
        pass
    return None

def get_wikipedia_logo(radio_name):
    """ Priorité 2 : API Wikipédia (Logos officiels détourés) """
    try:
        # 1. Chercher la page Wikipedia de la radio
        search_query = urllib.parse.quote(radio_name + " radio")
        search_url = f"https://fr.wikipedia.org/w/api.php?action=query&list=search&srsearch={search_query}&utf8=&format=json&srlimit=1"
        r = requests.get(search_url, headers=NAVIGATOR_HEADERS, timeout=4)
        
        if r.status_code == 200 and r.json().get('query', {}).get('search'):
            title = r.json()['query']['search'][0]['title']
            
            # 2. Récupérer l'image principale de cette page (Taille 500px)
            img_url = f"https://fr.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(title)}&prop=pageimages&format=json&pithumbsize=500"
            r_img = requests.get(img_url, headers=NAVIGATOR_HEADERS, timeout=4)
            pages = r_img.json().get('query', {}).get('pages', {})
            
            for page_id, page_data in pages.items():
                if 'thumbnail' in page_data:
                    return page_data['thumbnail']['source']
    except Exception:
        pass
    return None

def get_radio_browser_logo(radio_name):
    """ Priorité 3 (Dernier recours) : Radio-Browser """
    try:
        search_query = urllib.parse.quote(radio_name)
        url = f"https://de1.api.radio-browser.info/json/stations/byname/{search_query}"
        response = requests.get(url, headers=NAVIGATOR_HEADERS, timeout=4)
        if response.status_code == 200:
            data = response.json()
            valid_stations = [s for s in data if s.get('favicon') and s['favicon'].startswith('http') and "default" not in s['favicon']]
            if valid_stations:
                valid_stations.sort(key=lambda x: x.get('clickcount', 0), reverse=True)
                return valid_stations[0]['favicon']
    except Exception:
        pass
    return None

def download_logo(radio_name, image_url):
    """ Télécharge l'image physiquement et retourne le chemin relatif pour le JSON """
    safe_name = "".join([c for c in radio_name if c.isalnum()]).lower()
    file_name = f"{safe_name}.jpg"
    local_file_path = os.path.join(LOGOS_DIR, file_name)
    json_target_address = f"/www/img/radios/{file_name}"

    try:
        img_response = requests.get(image_url, headers=NAVIGATOR_HEADERS, timeout=5)
        img_response.raise_for_status()
        
        with open(local_file_path, 'wb') as handler:
            handler.write(img_response.content)
        
        return json_target_address
    except Exception as e:
        print(f"  -> [Erreur Téléchargement] {e}")
        return None

# ==========================================
# MOTEUR PRINCIPAL (TRAITEMENT DU JSON)
# ==========================================
def process_cache_updates():
    if not os.path.exists(LOGOS_CACHE_FILE):
        print(f"[Erreur] Fichier JSON introuvable : {LOGOS_CACHE_FILE}")
        return

    os.makedirs(LOGOS_DIR, exist_ok=True)

    with open(LOGOS_CACHE_FILE, 'r', encoding='utf-8') as f:
        cache_data = json.load(f)

    print(f"📡 Analyse du cache : {len(cache_data)} stations trouvées...")
    has_changes = False

    for station_name, target_address in cache_data.items():
        if target_address == "FA_ICON" or target_address == "":
            print(f"\n🔍 Recherche requise pour : '{station_name}'")
            
            # CASCADE DE RECHERCHE : iTunes -> Wikipedia -> Radio-Browser
            img_url = get_itunes_clean_logo(station_name)
            
            if not img_url:
                print("  -> iTunes échoué, tentative Wikipédia...")
                img_url = get_wikipedia_logo(station_name)
                
            if not img_url:
                print("  -> Wikipédia échoué, tentative Radio-Browser...")
                img_url = get_radio_browser_logo(station_name)

            if img_url:
                new_target_address = download_logo(station_name, img_url)
                if new_target_address:
                    print(f"  ✅ Succès : {new_target_address}")
                    cache_data[station_name] = new_target_address
                    has_changes = True
            else:
                print(f"  ❌ Aucun logo trouvé. Conservé en l'état.")

    if has_changes:
        print("\n💾 Mise à jour du fichier JSON en cours...")
        with open(LOGOS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        print("🎉 Fichier mis à jour avec succès !")
    else:
        print("\n✨ Terminé. Le cache est déjà à jour, aucune action nécessaire.")

if __name__ == "__main__":
    process_cache_updates()
```
<br>

### `app/utils.py`

```python
import socket

def get_local_ip():
    """Permet au serveur de deviner sa propre IP locale pour envoyer des liens à la Bose"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP
```
<br>

### `app/virtual_soundtouch.py`

```python
import os
import time
import socket
import threading
import uuid
import json
import base64
import requests
import re
import hashlib
import urllib.parse
import subprocess
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils
from flask import Flask, request, Response
import vlc
from zeroconf import ServiceInfo, Zeroconf
import logging

# --- UTILITAIRE RESEAU ---
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

LOCAL_IP = get_local_ip()

# --- LECTURE CONFIGURATION .ENV ---
def load_env_config():
    """Charge les variables depuis le fichier .env[cite: 4]."""
    env_paths = ["/home/pi/sc_tools/.env", "/home/pi/sc_tools/data/.env", ".env"]
    for env_path in env_paths:
        if os.path.exists(env_path):
            try:
                env_data = {}
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if '=' in line:
                                k, v = line.split('=', 1)
                                env_data[k.strip()] = v.strip()
                print(f"✅ Configuration chargée depuis {env_path}")
                return env_data
            except Exception as e:
                print(f"⚠️ Erreur de lecture de {env_path} : {e}")
    return {}

ENV_CONFIG = load_env_config()

# --- CONFIGURATION DE L'EMULATEUR ---
DEVICE_NAME = "Pi-Bluetooth"
MAC_ADDRESS = ''.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0,8*6,8)][::-1]).upper()
HTTP_PORT = 8090
WS_PORT = 8080

# Extraction dynamique depuis le .env[cite: 4]
MARGE_PORT = int(ENV_CONFIG.get("SC_MARGE_PORT", 8000))
MARGE_ADDR = ENV_CONFIG.get("SC_MARGE_ADDR", "127.0.0.1")

# --- CONFIGURATION MATERIELLE ---
BT_MAC_ADDRESS = ENV_CONFIG.get("SC_MARGE_ADDR", "70:99:1C:AF:FB:5F")

def get_marge_account_uuid(default_uuid="5476586"):
    """
    Récupération dynamique du margeAccountUUID.
    Priorité 1 : Fichier .env (SC_MARGE_ACCOUNT)[cite: 4]
    Priorité 2 : Interrogation API réseau Marge/Soundcork
    Priorité 3 : Valeur par défaut
    """
    if "SC_MARGE_ACCOUNT" in ENV_CONFIG:
        print("✅ ACCOUNT_UUID chargé depuis le fichier .env")
        return str(ENV_CONFIG["SC_MARGE_ACCOUNT"])

    try:
        r = requests.get(f"http://{MARGE_ADDR}:{MARGE_PORT}/info", timeout=2)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            uuid_node = root.find('.//margeAccountUUID')
            if uuid_node is not None and uuid_node.text:
                print(f"✅ ACCOUNT_UUID récupéré via l'API distante sur {MARGE_ADDR}:{MARGE_PORT}")
                return uuid_node.text
    except Exception:
        pass

    print(f"⚠️ Utilisation de l'ACCOUNT_UUID par défaut : {default_uuid}")
    return default_uuid

ACCOUNT_UUID = get_marge_account_uuid()

app = Flask(__name__)
# --- DESACTIVER LES LOGS HTTP DE FLASK ---
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
# -----------------------------------------
ws_clients = []
device_presets = {}
media_servers = []

# --- MOTEUR AUDIO (VLC) & ETAT ---
class VirtualDevice:
    def __init__(self):
        # Configuration stricte pour BlueALSA
        self.vlc_instance = vlc.Instance('--no-video', '--aout=alsa', '--alsa-audio-device=bluealsa', '--quiet')
        self.player = self.vlc_instance.media_player_new()
        self.volume = 30
        self.is_muted = False
        self.player.audio_set_volume(self.volume)
        self.player.audio_set_mute(0)
        
        # État par défaut
        self.state = "STANDBY"
        self.source = "STANDBY"
        self.track = ""
        self.artist = ""
        self.album = ""
        self.art_url = ""
        
        # Paramètres étendus obligatoires pour sc_tools
        self.location = ""
        self.source_account = ""
        self.item_type = "stationurl"
        self.station_name = ""
        self.stream_type = "RADIO_STREAMING"
        
        self.shuffle = "SHUFFLE_OFF"
        self.repeat = "REPEAT_OFF"
        
        # Événements VLC
        self.events = self.player.event_manager()
        self.events.event_attach(vlc.EventType.MediaPlayerPlaying, self.on_playing)
        self.events.event_attach(vlc.EventType.MediaPlayerPaused, self.on_paused)
        self.events.event_attach(vlc.EventType.MediaPlayerEndReached, self.on_ended)
        self.events.event_attach(vlc.EventType.MediaPlayerEncounteredError, self.on_error)

    def on_playing(self, event):
        self.state = "PLAY_STATE"
        broadcast_update()

    def on_paused(self, event):
        self.state = "PAUSE_STATE"
        broadcast_update()

    def on_ended(self, event):
        self.state = "STOP_STATE"
        broadcast_update()

    def on_error(self, event):
        self.state = "STOP_STATE"
        broadcast_update()

    def play_url(self, url, source_type, title="Flux Audio", location="", source_account=""):
        # --- FORCER LA RECONNEXION BLUETOOTH AVANT DE JOUER ---
        try:
            subprocess.run(["bluetoothctl", "connect", BT_MAC_ADDRESS], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL, 
                           timeout=3)
            time.sleep(0.5) # Le temps que BlueALSA recrée la carte son
        except Exception as e:
            print(f"Info BT : {e}")
        # ------------------------------------------------------

        media = self.vlc_instance.media_new(url)
        self.player.set_media(media)
        
        # Mémorisation stricte des attributs
        self.source = source_type
        self.track = title
        self.station_name = title
        self.location = location
        self.source_account = source_account
        self.state = "BUFFERING_STATE"
        
        if source_type in ["RADIO_BROWSER", "LOCAL_INTERNET_RADIO", "TUNEIN"]:
            self.item_type = "stationurl"
            self.stream_type = "RADIO_STREAMING"
        else:
            self.item_type = "track"
            self.stream_type = "TRACK_ONDEMAND"
            
        self.player.play()
        broadcast_update()

    def toggle_pause(self):
        if self.state == "PLAY_STATE":
            self.player.pause()
        elif self.state == "PAUSE_STATE":
            self.player.play()

    def set_volume(self, vol):
        self.volume = max(0, min(100, int(vol)))
        self.player.audio_set_volume(self.volume)
        if self.is_muted and self.volume > 0:
            self.is_muted = False
            self.player.audio_set_mute(0)
        broadcast_volume()

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        self.player.audio_set_mute(1 if self.is_muted else 0)
        broadcast_volume()

device = VirtualDevice()

# --- TACHES DE FOND (Presets & DLNA) ---
def background_preset_sync():
    global device_presets
    while True:
        try:
            url = f"http://{MARGE_ADDR}:{MARGE_PORT}/marge/streaming/account/{ACCOUNT_UUID}/full"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                dev = root.find(f".//device[@deviceid='{MAC_ADDRESS}']")
                if dev is not None:
                    presets_node = dev.find('presets')
                    if presets_node is not None:
                        new_presets = {}
                        for p in presets_node.findall('preset'):
                            btn = p.get('buttonNumber')
                            loc = p.findtext('location') or ''
                            name = p.findtext('name') or f'Preset {btn}'
                            
                            source = "LOCAL_INTERNET_RADIO"
                            if "/stations/byuuid" in loc:
                                source = "RADIO_BROWSER"
                            elif "1$F$1" in loc:
                                source = "STORED_MUSIC"
                            
                            new_presets[btn] = {
                                'source': source,
                                'location': loc,
                                'itemName': name
                            }
                        device_presets = new_presets
        except Exception:
            pass
        time.sleep(60)

def background_ssdp_discover():
    global media_servers
    msg = ('M-SEARCH * HTTP/1.1\r\n'
           'HOST: 239.255.255.250:1900\r\n'
           'MAN: "ssdp:discover"\r\n'
           'MX: 2\r\n'
           'ST: urn:schemas-upnp-org:device:MediaServer:1\r\n\r\n')
           
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.settimeout(2.5)
            sock.sendto(msg.encode('utf-8'), ('239.255.255.250', 1900))
            locations = set()
            
            while True:
                try:
                    data, addr = sock.recvfrom(2048)
                    for line in data.decode('utf-8', errors='ignore').split('\r\n'):
                        if line.lower().startswith('location:'):
                            locations.add(line.split(':', 1)[1].strip())
                except socket.timeout:
                    break
            sock.close()
            
            discovered = []
            for loc in locations:
                try:
                    r = requests.get(loc, timeout=2)
                    if r.status_code == 200:
                        friendly_name = re.search(r'<friendlyName>(.*?)</friendlyName>', r.text)
                        friendly_name = friendly_name.group(1) if friendly_name else 'Unknown'
                        
                        udn = re.search(r'<UDN>uuid:(.*?)</UDN>', r.text)
                        udn = udn.group(1) if udn else str(uuid.uuid4())
                        
                        manufacturer = re.search(r'<manufacturer>(.*?)</manufacturer>', r.text)
                        manufacturer = manufacturer.group(1) if manufacturer else ''
                        
                        model_name = re.search(r'<modelName>(.*?)</modelName>', r.text)
                        model_name = model_name.group(1) if model_name else ''
                        
                        model_desc = re.search(r'<modelDescription>(.*?)</modelDescription>', r.text)
                        model_desc = model_desc.group(1) if model_desc else ''
                        
                        ip = urllib.parse.urlparse(loc).hostname
                        
                        discovered.append({
                            'id': udn,
                            'ip': ip,
                            'manufacturer': manufacturer,
                            'model_name': model_name,
                            'friendly_name': friendly_name,
                            'model_description': model_desc,
                            'location': loc
                        })
                except Exception:
                    pass
            media_servers = discovered
        except Exception:
            pass
        time.sleep(60)

def resolve_and_play(source, location, item_name, source_account=""):
    url_to_play = None
    
    if source == "LOCAL_INTERNET_RADIO":
        url_to_play = location 
        if "orion/station?data=" in url_to_play:
            try:
                b64_data = url_to_play.split("data=")[1]
                decoded = json.loads(base64.b64decode(b64_data).decode('utf-8'))
                url_to_play = decoded.get('streamUrl')
            except Exception as e:
                print(f"Erreur de décodage Orion : {e}")
                
    elif source == "STORED_MUSIC":
        if location.startswith("http"):
            url_to_play = location
        else:
            print(f"⚠️ [DLNA] Le preset pointe vers un ID UPnP ({location}).")
            device.player.stop()
            device.source = "STANDBY"
            device.state = "STANDBY"
            broadcast_update()
            return
            
    elif source == "RADIO_BROWSER" and "byuuid" in location:
        uuid_station = location.split("/")[-1]
        try:
            r = requests.get(f"https://de1.api.radio-browser.info/json/stations/byuuid/{uuid_station}", timeout=5)
            if r.status_code == 200:
                url_to_play = r.json()[0].get('url')
        except Exception as e:
            print(f"Erreur RadioBrowser : {e}")

    if url_to_play and url_to_play.startswith("http"):
        print(f"▶️ Lecture de l'URL résolue : {url_to_play}")
        device.play_url(url_to_play, source, item_name, location, source_account)
    else:
        print(f"⚠️ Impossible de résoudre une URL HTTP valide pour la source {source}")
        device.player.stop()
        device.source = "STANDBY"
        device.state = "STANDBY"
        broadcast_update()

# --- GENERATEURS XML EXACTS (Bose Spec) ---
def generate_now_playing_xml():
    if device.source == "STANDBY":
        return f'<nowPlaying deviceID="{MAC_ADDRESS}" source="STANDBY"><ContentItem source="STANDBY" isPresetable="false" /></nowPlaying>'
        
    safe_track = saxutils.escape(device.track)
    safe_artist = saxutils.escape(device.artist)
    safe_album = saxutils.escape(device.album)
    safe_station = saxutils.escape(device.station_name)
    safe_location = saxutils.escape(device.location)
    
    current_time = max(0, device.player.get_time() // 1000)
    total_time = max(0, device.player.get_length() // 1000)
    time_node = f'<time total="{total_time}">{current_time}</time>' if total_time > 0 else ''
    
    return f'''<nowPlaying deviceID="{MAC_ADDRESS}" source="{device.source}" sourceAccount="{device.source_account}">
    <ContentItem source="{device.source}" type="{device.item_type}" location="{safe_location}" sourceAccount="{device.source_account}" isPresetable="true">
        <itemName>{safe_track}</itemName>
        <containerArt/>
    </ContentItem>
    <track>{safe_track}</track>
    <artist>{safe_artist}</artist>
    <album>{safe_album}</album>
    <stationName>{safe_station}</stationName>
    <art artImageStatus="SHOW_DEFAULT_IMAGE">{device.art_url}</art>
    {time_node}
    <playStatus>{device.state}</playStatus>
    <streamType>{device.stream_type}</streamType>
    <shuffleSetting>{device.shuffle}</shuffleSetting>
    <repeatSetting>{device.repeat}</repeatSetting>
</nowPlaying>'''

def generate_volume_xml():
    mute_str = "true" if device.is_muted else "false"
    return f'<volume deviceID="{MAC_ADDRESS}"><targetvolume>{device.volume}</targetvolume><actualvolume>{device.volume}</actualvolume><muteenabled>{mute_str}</muteenabled></volume>'

def generate_404_xml():
    return f'<?xml version="1.0" encoding="UTF-8" ?><errors deviceID="{MAC_ADDRESS}"><error value="1503" name="HTTP_NOT_FOUND" severity="Unknown">1503</error></errors>'

# --- GESTIONNAIRE WEBSOCKET NATIF ---
def ws_send(conn, msg):
    try:
        msg_bytes = msg.encode('utf-8')
        length = len(msg_bytes)
        frame = bytearray([0x81]) 
        
        if length <= 125:
            frame.append(length)
        elif length <= 65535:
            frame.append(126)
            frame.extend(length.to_bytes(2, 'big'))
        else:
            frame.append(127)
            frame.extend(length.to_bytes(8, 'big'))
            
        frame.extend(msg_bytes)
        conn.sendall(frame)
    except Exception:
        if conn in ws_clients:
            ws_clients.remove(conn)
        conn.close()

def broadcast_update():
    xml = f'<updates deviceID="{MAC_ADDRESS}"><nowPlayingUpdated>{generate_now_playing_xml()}</nowPlayingUpdated></updates>'
    for conn in list(ws_clients):
        ws_send(conn, xml)

def broadcast_volume():
    xml = f'<updates deviceID="{MAC_ADDRESS}"><volumeUpdated>{generate_volume_xml()}</volumeUpdated></updates>'
    for conn in list(ws_clients):
        ws_send(conn, xml)

def periodic_status_broadcast():
    while True:
        if device.state == "PLAY_STATE":
            # --- AUTO-STOP EN CAS DE DECONNEXION BLUETOOTH ---
            try:
                res = subprocess.run(["bluetoothctl", "info", BT_MAC_ADDRESS], capture_output=True, text=True)
                if "Connected: yes" not in res.stdout:
                    print("\n⚠️ Enceinte déconnectée ! Arrêt automatique de la lecture pour éviter le spam.")
                    device.player.stop()
                    device.source = "STANDBY"
                    device.state = "STANDBY"
            except Exception:
                pass
            # -------------------------------------------------
            broadcast_update()
        time.sleep(5) # Vérifie l'état toutes les 5 secondes

def handle_ws_client(conn):
    try:
        data = conn.recv(4096).decode('utf-8', errors='ignore')
        if not data: return
        
        key_match = re.search(r'Sec-WebSocket-Key:\s+(.*?)\r\n', data)
        if not key_match: return
        
        key = key_match.group(1).strip()
        accept_key = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('utf-8')).digest()).decode('utf-8')
        
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n"
            "Sec-WebSocket-Protocol: gabbo\r\n\r\n"
        )
        conn.sendall(response.encode('utf-8'))
        ws_clients.append(conn)
        
        ws_send(conn, '<SoundTouchSdkInfo serverVersion="4" serverBuild="trunk r46330 v4 epdbuild hepdswbld04" />')
        ws_send(conn, f'<updates deviceID="{MAC_ADDRESS}"><nowPlayingUpdated>{generate_now_playing_xml()}</nowPlayingUpdated></updates>')
        ws_send(conn, f'<updates deviceID="{MAC_ADDRESS}"><volumeUpdated>{generate_volume_xml()}</volumeUpdated></updates>')
        
        while True:
            frame = conn.recv(4096)
            if not frame: break
            
            if len(frame) >= 2:
                opcode = frame[0] & 0x0F
                if opcode == 0x09:
                    pong_frame = bytearray([0x8A, frame[1]])
                    if len(frame) > 2:
                        pong_frame.extend(frame[2:])
                    conn.sendall(pong_frame) 
                elif opcode == 0x08: 
                    break
    except Exception as e:
        print(f"Erreur WS client: {e}")
    finally:
        if conn in ws_clients:
            ws_clients.remove(conn)
        conn.close()

def ws_server_loop():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', WS_PORT))
    server.listen(5)
    print(f"📡 Serveur WebSocket émulé en écoute sur le port {WS_PORT}...")
    
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_ws_client, args=(conn,), daemon=True).start()

# --- API HTTP ---
@app.route('/info', methods=['GET'])
def get_info():
    current_time = time.strftime('%Y-%m-%dT%H:%M:%S.000+00:00', time.gmtime())
    xml = f'''<?xml version="1.0" encoding="UTF-8" ?>
    <info deviceID="{MAC_ADDRESS}">
        <name>{DEVICE_NAME}</name>
        <type>SoundTouch Virtual</type>
        <components>
            <component>
                <componentCategory>SCM</componentCategory>
                <softwareVersion>27.0.6.46330.5043500</softwareVersion>
                <serialNumber>VIRTUAL-SCM-{MAC_ADDRESS}</serialNumber>
            </component>
        </components>
        <networkInfo type="SCM">
            <macAddress>{MAC_ADDRESS}</macAddress>
            <ipAddress>{LOCAL_IP}</ipAddress>
        </networkInfo>
        <margeAccountUUID>{ACCOUNT_UUID}</margeAccountUUID>
        <margeURL>http://{MARGE_ADDR}:{MARGE_PORT}/marge</margeURL>
        <createdOn>2012-09-19T12:43:00.000+00:00</createdOn>
        <updatedOn>{current_time}</updatedOn>
    </info>'''
    return Response(xml, mimetype='text/xml')

@app.route('/supportedURLs', methods=['GET'])
def get_supported_urls():
    urls = [
        "/info", "/capabilities", "/powerManagement", "/nowPlaying", "/volume", "/key", 
        "/select", "/presets", "/sources", "/listMediaServers", "/getGroup", "/notification", 
        "/masterMsg", "/slaveMsg", "/setZone", "/addZoneSlave", "/removeZoneSlave"
    ]
    xml = f'<?xml version="1.0" encoding="UTF-8" ?><supportedURLs deviceID="{MAC_ADDRESS}">'
    for url in urls:
        xml += f'<URL location="{url}" />'
    xml += '</supportedURLs>'
    return Response(xml, mimetype='text/xml')

@app.route('/listMediaServers', methods=['GET'])
def list_media_servers():
    xml = '<?xml version="1.0" encoding="UTF-8" ?>\n<ListMediaServersResponse>'
    for srv in media_servers:
        xml += f'<media_server id="{srv["id"]}" ip="{srv["ip"]}" manufacturer="{saxutils.escape(srv["manufacturer"])}" model_name="{saxutils.escape(srv["model_name"])}" friendly_name="{saxutils.escape(srv["friendly_name"])}" model_description="{saxutils.escape(srv["model_description"])}" location="{saxutils.escape(srv["location"])}" />'
    xml += '</ListMediaServersResponse>'
    return Response(xml, mimetype='text/xml')

@app.route('/sources', methods=['GET'])
def get_sources():
    xml = f'''<?xml version="1.0" encoding="UTF-8" ?>
    <sources deviceID="{MAC_ADDRESS}">
        <sourceItem source="LOCAL_INTERNET_RADIO" status="READY" isLocal="false" />
        <sourceItem source="RADIO_BROWSER" status="READY" isLocal="false" />
        <sourceItem source="BLUETOOTH" status="READY" isLocal="true" />
    '''
    for srv in media_servers:
        xml += f'<sourceItem source="STORED_MUSIC" sourceAccount="{srv["id"]}/0" status="READY" isLocal="false">{saxutils.escape(srv["friendly_name"])}</sourceItem>\n'
    xml += '</sources>'
    return Response(xml, mimetype='text/xml')

@app.route('/presets', methods=['GET'])
def get_presets():
    xml = '<?xml version="1.0" encoding="UTF-8" ?><presets>'
    for btn, data in device_presets.items():
        xml += f'''
        <preset id="{btn}">
            <ContentItem source="{data['source']}" location="{data['location']}" isPresetable="true">
                <itemName>{saxutils.escape(data['itemName'])}</itemName>
            </ContentItem>
        </preset>'''
    xml += '</presets>'
    return Response(xml, mimetype='text/xml')

@app.route('/nowPlaying', methods=['GET'])
def get_now_playing():
    xml = '<?xml version="1.0" encoding="UTF-8" ?>\n' + generate_now_playing_xml()
    return Response(xml, mimetype='text/xml')

@app.route('/volume', methods=['GET', 'POST'])
def handle_volume():
    if request.method == 'POST':
        try:
            root = ET.fromstring(request.data)
            if root.tag == 'volume':
                device.set_volume(int(root.text))
        except: pass
    xml = '<?xml version="1.0" encoding="UTF-8" ?>\n' + generate_volume_xml()
    return Response(xml, mimetype='text/xml')

@app.route('/key', methods=['POST'])
def handle_key():
    try:
        root = ET.fromstring(request.data)
        state = root.attrib.get('state')
        key = root.text
        
        if state in ['press', 'repeat']:
            if key == "VOLUME_UP": device.set_volume(device.volume + 2)
            elif key == "VOLUME_DOWN": device.set_volume(device.volume - 2)
        
        if state in ['release', None]:
            if key == "PLAY_PAUSE": device.toggle_pause()
            elif key == "PLAY":
                if device.state == "PAUSE_STATE":
                    device.player.play()
                    device.state = "PLAY_STATE"
                    broadcast_update()
            elif key == "PAUSE":
                if device.state == "PLAY_STATE":
                    device.player.pause()
                    device.state = "PAUSE_STATE"
                    broadcast_update()
            elif key == "STOP":
                device.player.stop()
                device.source = "STANDBY"
                device.state = "STANDBY"
                broadcast_update()
            elif key == "POWER":
                if device.state != "STANDBY":
                    device.player.stop()
                    device.source = "STANDBY"
                    device.state = "STANDBY"
                broadcast_update()
            elif key == "MUTE": device.toggle_mute()
            elif key == "SHUFFLE_ON": device.shuffle = "SHUFFLE_ON"; broadcast_update()
            elif key == "SHUFFLE_OFF": device.shuffle = "SHUFFLE_OFF"; broadcast_update()
            elif key in ["REPEAT_OFF", "REPEAT_ONE", "REPEAT_ALL"]:
                device.repeat = key
                broadcast_update()
            elif key == "AUX_INPUT":
                device.player.stop()
                device.source = "AUX"
                device.track = "Entrée Auxiliaire"
                device.item_type = "track"
                device.stream_type = "TRACK_ONDEMAND"
                device.state = "PLAY_STATE"
                broadcast_update()
            elif key.startswith("PRESET_"):
                preset_id = key.split('_')[1]
                if preset_id in device_presets:
                    p = device_presets[preset_id]
                    resolve_and_play(p['source'], p['location'], p['itemName'], "")
                
    except Exception as e:
        print(f"Erreur Key : {e}")
    return Response('<?xml version="1.0" encoding="UTF-8" ?><status>Gabbo</status>', mimetype='text/xml')

@app.route('/select', methods=['POST'])
def handle_select():
    try:
        root = ET.fromstring(request.data)
        source = root.attrib.get('source')
        location = root.attrib.get('location', '')
        source_account = root.attrib.get('sourceAccount', '')
        item_name = root.findtext('itemName') or 'Stream Inconnu'
        resolve_and_play(source, location, item_name, source_account)
    except Exception as e:
        print(f"Erreur Select : {e}")
    return Response('<?xml version="1.0" encoding="UTF-8" ?><status>Gabbo</status>', mimetype='text/xml')

@app.route('/powerManagement', methods=['GET'])
def get_power():
    xml = '<?xml version="1.0" encoding="UTF-8" ?><powerManagementResponse><powerState>FullPower</powerState><battery><capable>false</capable></battery></powerManagementResponse>'
    return Response(xml, mimetype='text/xml')

@app.route('/getGroup', methods=['GET'])
def get_group():
    return Response(generate_404_xml(), status=404, mimetype='text/xml')

@app.route('/getZone', methods=['GET'])
def get_zone():
    return Response('<?xml version="1.0" encoding="UTF-8" ?><zone />', mimetype='text/xml')

@app.route('/capabilities', methods=['GET'])
def get_capa():
    xml = f'''<?xml version="1.0" encoding="UTF-8" ?>
    <capabilities deviceID="{MAC_ADDRESS}">
        <networkConfig>
            <hostedWifiConfigWebPage/>
            <wsapiproxy>false</wsapiproxy>
            <allInterfacesSupported/>
            <wlanInterfaces/>
            <security/>
        </networkConfig>
        <dspCapabilities>
            <dspMonoStereo/>
        </dspCapabilities>
        <lightswitch>false</lightswitch>
        <clockDisplay>false</clockDisplay>
        <capability name="systemtimeout" url="/systemtimeout" info=""/>
        <capability name="rebroadcastlatencymode" url="/rebroadcastlatencymode" info=""/>
        <lrStereoCapable>false</lrStereoCapable>
        <bcoresetCapable>false</bcoresetCapable>
        <disablePowerSaving>true</disablePowerSaving>
    </capabilities>'''
    return Response(xml, mimetype='text/xml')

@app.route('/notification', methods=['POST'])
def handle_notification():
    return Response('<?xml version="1.0" encoding="UTF-8" ?><status>/notification</status>', mimetype='text/xml')

@app.route('/masterMsg', methods=['POST'])
def handle_master_msg():
    return Response('<?xml version="1.0" encoding="UTF-8" ?><status>/masterMsg</status>', mimetype='text/xml')

@app.route('/slaveMsg', methods=['POST'])
def handle_slave_msg():
    return Response('<?xml version="1.0" encoding="UTF-8" ?><status>/slaveMsg</status>', mimetype='text/xml')

@app.route('/setZone', methods=['POST'])
def set_zone():
    return Response('<?xml version="1.0" encoding="UTF-8" ?><status>/setZone</status>', mimetype='text/xml')

@app.route('/addZoneSlave', methods=['POST'])
def add_zone_slave():
    return Response('<?xml version="1.0" encoding="UTF-8" ?><status>/addZoneSlave</status>', mimetype='text/xml')

@app.route('/removeZoneSlave', methods=['POST'])
def remove_zone_slave():
    return Response('<?xml version="1.0" encoding="UTF-8" ?><status>/removeZoneSlave</status>', mimetype='text/xml')

# --- MDNS ANNONCE ---
def register_mdns():
    info = ServiceInfo(
        "_soundtouch._tcp.local.",
        f"{DEVICE_NAME}._soundtouch._tcp.local.",
        addresses=[socket.inet_aton(LOCAL_IP)],
        port=HTTP_PORT,
        properties={'MAC': MAC_ADDRESS.encode('utf-8')}
    )
    zeroconf = Zeroconf()
    zeroconf.register_service(info)
    print(f"🔊 Annonce mDNS envoyée : {DEVICE_NAME} ({MAC_ADDRESS}) sur {LOCAL_IP}")
    return zeroconf

if __name__ == '__main__':
    threading.Thread(target=ws_server_loop, daemon=True).start()
    threading.Thread(target=background_preset_sync, daemon=True).start()
    threading.Thread(target=background_ssdp_discover, daemon=True).start()
    threading.Thread(target=periodic_status_broadcast, daemon=True).start()
    zc = register_mdns()
    
    try:
        app.run(host='0.0.0.0', port=HTTP_PORT, threaded=True)
    finally:
        zc.close()

```
<br>

### `docker-compose.yml`

```yaml
services:
  # --- APPLICATION PRINCIPALE UNIFIÉE (SOUNDCORK + RADIO FRANCE) ---
  sc_app:
    container_name: sc_app
    build: . 
    network_mode: host
    privileged: true
    env_file:
      - .env
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    volumes:
      - ./app:/app
      - ./www:/app/www
      - ./data:/app/tools_data
      - ./Podcasts:/app/rf_podcasts
      - /home/pi/sc_tools/Music:/media:ro
      - /home/pi/soundcork/data:/data
      - /var/run/docker.sock:/var/run/docker.sock
      - /home/pi/sc_tools/tools:/home/pi/sc_tools/tools
      - /var/run/dbus:/var/run/dbus
      - /var/run/avahi-daemon/socket:/var/run/avahi-daemon/socket
      - /etc/localtime:/etc/localtime:ro     
    environment:
      - RF_TOKEN=${RF_TOKEN}
      - FLASK_ENV=production
      - SOUNDCORK_PORT=8000
    restart: always

  # --- MINI-DLNA LOCAL ---
  local_dlna:
    image: vladgh/minidlna
    container_name: local_dlna
    network_mode: host 
    environment:
      - MINIDLNA_MEDIA_DIR=A,/media
      - MINIDLNA_PORT=8282
      - MINIDLNA_FRIENDLY_NAME=SoundCork
      - MINIDLNA_INOTIFY=no
      - MINIDLNA_NETWORK_INTERFACE=${DLNA_INTERFACE:-eth0}
      - MINIDLNA_ALBUM_ART_NAMES=Cover.jpg/cover.jpg
      - MINIDLNA_NOTIFY_INTERVAL=86400
      # Force l'affichage du dossier Musique par défaut
      - MINIDLNA_ROOT_CONTAINER=M
    volumes:
      # Lecture dynamique du chemin de la musique
      - ${MEDIA_PATH:-./Music}:/media:ro
      - ./playlists:/playlists:ro
      - ./dlna_cache:/minidlna 
    restart: unless-stopped

```
<br>

### `Dockerfile`

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 1. Installation des utilitaires (incluant gcc pour Radio France)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    netcat-openbsd \
    xmlstarlet \
    avahi-utils \
    openssh-client \
    procps \
    hostname \
    iputils-ping \
    dnsutils \
    util-linux \
    dosfstools \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 2. Copie de l'exécutable Docker officiel
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/

# 3. Installation manuelle de ttyd (Dashboard Tools)
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then TTYD_ARCH="x86_64"; \
    elif [ "$ARCH" = "aarch64" ]; then TTYD_ARCH="aarch64"; \
    elif [ "$ARCH" = "armv7l" ] || [ "$ARCH" = "armv6l" ]; then TTYD_ARCH="armhf"; \
    else TTYD_ARCH="i686"; fi && \
    curl -sSL -o /usr/local/bin/ttyd https://github.com/tsl0922/ttyd/releases/download/1.7.4/ttyd.${TTYD_ARCH} && \
    chmod +x /usr/local/bin/ttyd

EXPOSE 80 8080 8081
CMD ["python", "app.py"]
```
<br>

### `www/alarm.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
 	<!-- PWA et Manifest -->
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#121212">

    <!-- Optimisations spécifiques pour iOS (Apple) -->
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoundCork">
    <link rel="apple-touch-icon" href="img/icon-192.png">

   <title>⏰ Réveil - SoundTouch</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <link rel="stylesheet" href="css/global.css">
    <style>
        /* --- CACHER LES ÉLÉMENTS GLOBAUX INUTILES POUR LE RÉVEIL --- */
        #speakers-list, .nav-section:first-child .action-buttons { display: none !important; }
        .nav-section:first-child h3 { display: none !important; }

        /* --- STYLES DU FORMULAIRE --- */
        .form-section { background-color: var(--bg-elevated); padding: 20px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);}
        .form-title { font-size: 16px; font-weight: bold; margin-bottom: 15px; color: var(--spotify-green); border-bottom: 1px solid #333; padding-bottom: 10px;}
        
        /* Enceintes (Grille) */
        .alarm-spk-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; }
        .alarm-spk-btn { background-color: var(--bg-base); color: var(--text-base); border: 2px solid transparent; padding: 15px; border-radius: 8px; cursor: pointer; text-align: center; transition: all 0.2s; display: flex; flex-direction: column; gap: 5px;}
        .alarm-spk-btn:hover { background-color: var(--bg-highlight); }
        .alarm-spk-btn.active { border-color: var(--spotify-green); background-color: rgba(29, 185, 84, 0.1); }
        .alarm-spk-btn.disabled { opacity: 0.5; cursor: not-allowed; }

        /* Jours d'activation (Pills) */
        .days-container { display: flex; flex-wrap: wrap; gap: 10px; }
        .day-checkbox { display: none; }
        .day-label { background-color: var(--bg-base); color: var(--text-subdued); padding: 10px 15px; border-radius: 500px; cursor: pointer; font-weight: bold; transition: all 0.2s; border: 1px solid transparent; user-select: none;}
        .day-checkbox:checked + .day-label { background-color: var(--spotify-green); color: black; border-color: var(--spotify-green); }

        /* Selects (Heures/Minutes) */
        .time-select-container { display: flex; gap: 20px; }
        .time-select-group { flex: 1; display: flex; flex-direction: column; gap: 8px;}
        .time-select { padding: 15px; border-radius: 8px; border: none; background-color: var(--bg-base); color: white; font-size: 18px; outline: none; cursor: pointer; font-weight: bold; text-align: center;}

        /* Bouton Valider */
        .btn-submit-alarm { background-color: var(--spotify-green); color: black; border: none; padding: 15px; border-radius: 500px; font-size: 16px; font-weight: bold; cursor: pointer; width: 100%; transition: transform 0.1s; margin-top: 10px;}
        .btn-submit-alarm:hover { transform: scale(1.02); background-color: #1ed760; }

        /* --- MINI SVG --- */
        .mini-remote-wrapper { max-width: 200px; margin: 0 auto; display: block; }
        .active-preset { fill: rgba(29, 185, 84, 0.4) !important; }

        /* --- LISTE DES ALARMES --- */
        .alarm-card { background-color: var(--bg-elevated); border-left: 4px solid var(--spotify-green); padding: 15px 20px; border-radius: 6px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .alarm-time { font-size: 24px; font-weight: bold; color: var(--text-base); }
        .alarm-info { font-size: 13px; color: var(--text-subdued); margin-top: 5px;}
        .badge-preset { background-color: #333; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; margin-right: 10px;}
        
        .status-bar { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background-color: #333; color: white; padding: 12px 24px; border-radius: 500px; font-weight: bold; box-shadow: 0 8px 24px rgba(0,0,0,0.5); z-index: 2000; display: none; transition: opacity 0.3s; }
        .status-success { background-color: var(--spotify-green); color: black; }
        .status-error { background-color: #FA243C; color: white;}
    </style>
</head>
<body>

    <div id="status-bar" class="status-bar">Notification</div>

    <div class="main-container">
        <div id="mobile-overlay" class="sidebar-overlay" onclick="toggleMobileMenu()"></div>
        <nav class="sidebar"></nav>

        <main class="main-view">
            
            <div class="top-bar">
                <div style="display: flex; width: 100%; align-items: center;">
                    <button class="mobile-menu-btn" onclick="toggleMobileMenu(event)">
                        <i class="fas fa-bars"></i>
                    </button>
                    <h2 class="section-title" style="margin: 0; padding-left: 15px;">
                        <i class="fas fa-clock" style="color: var(--spotify-green); margin-right: 10px;"></i> Programmer un Réveil
                    </h2>
                </div>
            </div>

            <form id="alarm-form">
                
                <div class="form-section">
                    <div class="form-title">1. Choisir l'enceinte (Même en veille)</div>
                    <div id="alarm-speakers" class="alarm-spk-grid">
                        <div class="loader"></div>
                    </div>
                </div>

                <div class="form-section">
                    <div class="form-title">2. Choisir la station (Préréglage)</div>
                    <div class="mini-remote-wrapper" id="mini-remote-wrapper"></div>
                </div>

                <div class="form-section">
                    <div class="form-title">3. Heure du réveil</div>
                    <div class="time-select-container">
                        <div class="time-select-group">
                            <span style="color: var(--text-subdued); font-size: 13px;">Heure :</span>
                            <select id="alarm-hour" class="time-select" required></select>
                        </div>
                        <div class="time-select-group">
                            <span style="color: var(--text-subdued); font-size: 13px;">Minute :</span>
                            <select id="alarm-minute" class="time-select" required></select>
                        </div>
                    </div>
                </div>

                <div class="form-section">
                    <div class="form-title">4. Jours d'activation</div>
                    <div class="days-container">
                        <input class="day-checkbox" type="checkbox" value="1" id="day-1"><label class="day-label" for="day-1">Lun</label>
                        <input class="day-checkbox" type="checkbox" value="2" id="day-2"><label class="day-label" for="day-2">Mar</label>
                        <input class="day-checkbox" type="checkbox" value="3" id="day-3"><label class="day-label" for="day-3">Mer</label>
                        <input class="day-checkbox" type="checkbox" value="4" id="day-4"><label class="day-label" for="day-4">Jeu</label>
                        <input class="day-checkbox" type="checkbox" value="5" id="day-5"><label class="day-label" for="day-5">Ven</label>
                        <input class="day-checkbox" type="checkbox" value="6" id="day-6"><label class="day-label" for="day-6">Sam</label>
                        <input class="day-checkbox" type="checkbox" value="0" id="day-0"><label class="day-label" for="day-0">Dim</label>
                    </div>
                </div>

                <button type="submit" class="btn-submit-alarm">💾 Enregistrer le réveil</button>
            </form>

            <h2 class="section-title" style="margin-top: 50px;">Alarmes Programmées</h2>
            <div id="alarms-list" style="margin-bottom: 60px;">
                </div>

        </main>
    </div>

    <footer class="player-bar"></footer>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
	<script src="js/app.js"></script>

<script>
        const dayMap = { "1": "Lun", "2": "Mar", "3": "Mer", "4": "Jeu", "5": "Ven", "6": "Sam", "0": "Dim" };
        
        let selectedAlarmIp = "";
        let selectedAlarmSpeakerName = "";
        let selectedAlarmPreset = "";

        document.addEventListener("DOMContentLoaded", async () => {
            // Remplir les Selects Heure/Min
            initTimeSelects();
            
            // Forcer un cache-buster pour le mini SVG
            const cacheBuster = "?t=" + new Date().getTime();
            await loadComponent(null, "components/remotemini.svg" + cacheBuster, "#mini-remote-wrapper");

            // Remplacer intelligemment le clic sur le preset pour CE formulaire (On ne lit pas la musique, on la sélectionne !)
            window.playPreset = function(id) {
                selectedAlarmPreset = "PRESET_" + id;
                updatePresetSelectionUI();
            };

            if (typeof fetchState === "function") fetchState();
            updateAlarmsList();
        });

        // --- LE CORRECTIF EST ICI ---
        // On demande à la page de se mettre à jour toutes les secondes en lisant globalData
        setInterval(onStateUpdated, 1000);
        // ----------------------------

        // ----------------------------------------------------
        // NOTIFICATIONS
        // ----------------------------------------------------
        function showNotification(msg, type = "success") {
            const statusBar = document.getElementById('status-bar');
            statusBar.innerText = msg;
            statusBar.className = `status-bar status-${type}`;
            statusBar.style.display = 'block';
            setTimeout(() => { statusBar.style.display = 'none'; }, 4000);
        }

        function initTimeSelects() {
            const hSel = document.getElementById('alarm-hour');
            let hHtml = '';
            for (let i = 0; i < 24; i++) {
                let s = i.toString().padStart(2, '0');
                hHtml += `<option value="${s}">${s} h</option>`;
            }
            hSel.innerHTML = hHtml;

            const mSel = document.getElementById('alarm-minute');
            let mHtml = '';
            for (let i = 0; i < 60; i++) {
                let s = i.toString().padStart(2, '0');
                mHtml += `<option value="${s}">${s} min</option>`;
            }
            mSel.innerHTML = mHtml;
        }

        // ----------------------------------------------------
        // HOOK PRINCIPAL : RENDU DES ENCEINTES & SVG
        // ----------------------------------------------------
        function onStateUpdated() {
            // Sécurité : on attend que app.js ait récupéré les données
            if (!globalData || !globalData.speakers) return;

            // 1. Liste des Enceintes pour le réveil (On affiche tout, même celles en OFF)
            const spkDiv = document.getElementById('alarm-speakers');
            if (Object.keys(globalData.speakers).length > 0) {
                spkDiv.innerHTML = Object.entries(globalData.speakers).map(([ip, s]) => {
                    const isSelected = (selectedAlarmIp === ip);
                    const activeClass = isSelected ? 'active' : '';
                    
                    let stateColor = "var(--spotify-green)";
                    if(s.state === "STANDBY") stateColor = "#FF9900";
                    if(s.state === "OFF") stateColor = "red";

                    return `
                        <div class="alarm-spk-btn ${activeClass}" onclick="selectAlarmSpeaker('${ip}', '${s.name.replace(/'/g, "\\'")}')">
                            <div style="font-weight:bold; font-size:14px;">${s.name}</div>
                            <div style="font-size:12px; color:var(--text-subdued);">
                                <span style="color:${stateColor}; margin-right:5px;">●</span>${s.state}
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                spkDiv.innerHTML = '<div style="color:var(--text-subdued);">Aucune enceinte détectée.</div>';
            }

            // 2. Mise à jour des noms de Presets sur le mini SVG
            if (globalData.presets) {
                for (let i = 1; i <= 6; i++) {
                    let presetName = globalData.presets[i] || "";
                    const svgTextEl = document.getElementById(`preset-text-${i}`);
                    if (svgTextEl) {
                        svgTextEl.textContent = presetName.length > 14 ? presetName.substring(0, 13) + "..." : presetName;
                    }
                }
            }
        }

        function selectAlarmSpeaker(ip, name) {
            selectedAlarmIp = ip;
            selectedAlarmSpeakerName = name;
            onStateUpdated(); // Rafraichit juste la vue locale
        }

        function updatePresetSelectionUI() {
            for (let i = 1; i <= 6; i++) {
                const rectEl = document.getElementById(`preset-rect-${i}`);
                if (rectEl) {
                    if (selectedAlarmPreset === `PRESET_${i}`) {
                        rectEl.classList.add('active-preset');
                    } else {
                        rectEl.classList.remove('active-preset');
                    }
                }
            }
        }

        // ----------------------------------------------------
        // SOUMISSION DU FORMULAIRE
        // ----------------------------------------------------
        document.getElementById('alarm-form').addEventListener('submit', async (e) => {
            e.preventDefault();

            if (!selectedAlarmIp) return showNotification("Veuillez sélectionner une enceinte.", "error");
            if (!selectedAlarmPreset) return showNotification("Veuillez sélectionner un bouton Préréglage.", "error");

            const checkedDays = Array.from(document.querySelectorAll('.day-checkbox:checked')).map(cb => cb.value);
            if (checkedDays.length === 0) return showNotification("Veuillez cocher au moins un jour.", "error");

            const payload = {
                ip: selectedAlarmIp,
                speakerName: selectedAlarmSpeakerName,
                hour: parseInt(document.getElementById('alarm-hour').value, 10).toString(),
                minute: parseInt(document.getElementById('alarm-minute').value, 10).toString(),
                days: checkedDays.join(','),
                vol: "25", // Valeur par défaut imposée
                preset: selectedAlarmPreset
            };

            try {
                const response = await fetch('/api/alarms', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    showNotification("⏰ Réveil enregistré !", "success");
                    // Reset UI
                    selectedAlarmPreset = "";
                    document.getElementById('alarm-form').reset();
                    updatePresetSelectionUI();
                    updateAlarmsList();
                } else {
                    const txt = await response.text();
                    showNotification("Erreur : " + txt, "error");
                }
            } catch (err) {
                showNotification("Erreur réseau.", "error");
            }
        });

        // ----------------------------------------------------
        // LISTE DES ALARMES (Fetch indépendant)
        // ----------------------------------------------------
        async function updateAlarmsList() {
            const listDiv = document.getElementById('alarms-list');
            try {
                const res = await fetch('/api/alarms');
                const alarms = await res.json();

                if (!alarms || alarms.length === 0) {
                    listDiv.innerHTML = '<div style="color:var(--text-subdued); text-align:center;">Vous n\'avez aucun réveil actif.</div>';
                    return;
                }

                listDiv.innerHTML = alarms.map((a, index) => {
                    const cleanDays = a.days.split(',').map(d => dayMap[d] || d).join(', ');
                    const prNum = a.preset.replace('PRESET_', '');
                    return `
                        <div class="alarm-card">
                            <div>
                                <span class="badge-preset">Preset ${prNum}</span>
                                <span style="font-weight:bold;">${a.speakerName}</span>
                                <div class="alarm-time">${a.hour.padStart(2, '0')}:${a.minute.padStart(2, '0')}</div>
                                <div class="alarm-info"><i class="fas fa-calendar-alt"></i> ${cleanDays}</div>
                            </div>
                            <button class="btn-action" style="border-color:#FA243C; color:#FA243C; width:auto; padding:8px 15px;" onclick="deleteAlarm(${index})">
                                <i class="fas fa-trash"></i> Supprimer
                            </button>
                        </div>
                    `;
                }).join('');
            } catch (e) {
                console.error(e);
            }
        }

        async function deleteAlarm(index) {
            if (confirm("Voulez-vous vraiment supprimer ce réveil ?")) {
                await fetch(`/api/alarms?index=${index}`, { method: 'DELETE' });
                showNotification("🗑️ Réveil supprimé", "success");
                updateAlarmsList();
            }
        }
    </script>
</body>
</html>
```
<br>

### `www/components/footer.html`

```html
<div class="now-playing">
    <div class="cover-art" id="player-cover" onclick="window.location.href='now.html'">
        <i class="fas fa-music" style="color:#555;"></i>
    </div>
    <div class="track-info">
        <span class="track-name" id="player-track">Sélectionnez une enceinte</span>
        <span class="album-name" id="player-album">-</span>
        <span class="artist-name" id="player-artist">-</span>
    </div>
</div>

<div class="volume-controls">
    <i class="fas fa-volume-down volume-icon"></i>
    <input type="range" id="volume-slider" min="0" max="100" value="0" onchange="changeVolume(this.value)">
    <i class="fas fa-volume-up volume-icon"></i>
</div>
```
<br>

### `www/components/sidebar.html`

```html
<!-- www/components/sidebar.html -->
<div class="brand" onclick="window.location.href='index.html'">
    <i id="dynamic-logo" class="fab fa-spotify" style="color: var(--spotify-green);"></i>
    <span>SoundTouch Custom</span>
</div>

<div class="nav-section">
    <div class="section-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <h3 onclick="forcePollAll(event)" style="cursor: pointer; margin: 0;" title="Forcer la reconnexion des enceintes">
            Enceintes <i class="fas fa-sync-alt" style="font-size: 0.8em; margin-left: 5px; color: var(--text-subdued);"></i>
        </h3>
        <!-- Bouton pour quitter la sélection multiple -->
        <button id="exit-multi-select" class="btn-exit-multi" style="display: none;" onclick="exitMultiSelectMode()">
            <i class="fas fa-check"></i> Terminé
        </button>
    </div>
    
    <div id="speakers-list" class="speakers-list">
        <!-- Les enceintes seront injectées ici par app.js -->
    </div>
    
    <div class="action-buttons">
        <button class="btn-action btn-action-primary" onclick="createZone()">
            <i class="fas fa-link"></i> Grouper
        </button>
        <!-- NOUVEAU : BOUTONS SPÉCIFIQUES ST-10 STEREO -->
	<!--- désactivés pour alléger l'écran, peu utilisé
		<button class="btn-action" style="border-color: #FFC107; color: #FFC107; margin-top: 5px;" onclick="createStereoPair()">
			<i class="fas fa-headphones"></i> Créer Paire Stéréo (ST-10)
		</button>
		<button class="btn-action" style="border-color: #FA243C; color: #FA243C; margin-top: 5px;" onclick="removeStereoPair()">
			<i class="fas fa-unlink"></i> Séparer Stéréo (ST-10)
		</button>
	-->
    </div>
</div>

<div class="nav-section">
	<a href="https://open.spotify.com/intl-fr/" target="_blank" class="nav-item id-nav-spotify">
<!--
	<a href="https://open.spotify.com/intl-fr/" target="_blank" class="id-nav-spotify">
-->
		   <i class="fab fa-spotify"></i> Spotify
	</a>
    <h3>Applications</h3>
    <a href="radios.html" class="nav-item id-nav-index">
   <i class="fas fa-broadcast-tower"></i> Webradios
    </a>
    <a href="podcasts.html" class="nav-item id-nav-podcast">
           <i class="fas fa-podcast"></i> Podcasts
    </a>
    <a href="dlna_browser.html" class="nav-item id-nav-dlna">
     <i class="fas fa-network-wired"></i> Diffusion réseau
    </a>
    <a href="dlna.html" class="nav-item id-nav-dlna">
               <i class="fas fa-hdd"></i> Musique enregistrée
    </a>
    <a href="upload.html" class="nav-item id-nav-upload">
        <i class="fas fa-mobile-alt"></i> Diffuser depuis l'appareil
    </a>
    <a href="remote.html" class="nav-item id-nav-remote">
           <i class="fas fa-gamepad"></i> Télécommande
    </a>
    <a href="alarm.html" class="nav-item id-nav-reveil">
             <i class="fas fa-clock"></i> Réveil
    </a>
    <a href="config.html" class="nav-item id-nav-config">
           <i class="fas fa-cog"></i> Configuration
    </a>
    <a href="#" class="nav-item" target="_blank" onclick="window.location.href = 'http://' + window.location.hostname + '/tools'">
             <i class="fas fa-tools"></i> Administration
    </a>
</div>

```
<br>

### `www/config.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#121212">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoundCork">
    <link rel="apple-touch-icon" href="img/icon-192.png">

    <title>⚙️ Configuration - SoundTouch</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <link rel="stylesheet" href="css/global.css">
    <style>
        .config-container { max-width: 800px; margin: 0 auto; padding-bottom: 50px; }
        .config-section { background-color: var(--bg-elevated); padding: 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
        .config-header { font-size: 18px; font-weight: bold; margin-bottom: 20px; color: var(--spotify-green); border-bottom: 1px solid #333; padding-bottom: 10px; display: flex; align-items: center; gap: 10px; }
        .config-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; flex-wrap: wrap; gap: 15px; }
        .config-input, .config-select { padding: 12px; border-radius: 6px; border: 1px solid #333; background: var(--bg-base); color: white; flex: 1; min-width: 200px; outline: none; }
        .config-input:focus, .config-select:focus { border-color: var(--spotify-green); }
        .config-btn { background: var(--spotify-green); color: black; border: none; padding: 12px 24px; border-radius: 500px; font-weight: bold; cursor: pointer; transition: transform 0.1s; white-space: nowrap; }
        .config-btn:hover { transform: scale(1.05); background: #1ed760; }
        
        .config-toggle { display: flex; align-items: center; gap: 10px; cursor: pointer; }
        .toggle-switch { position: relative; width: 50px; height: 26px; background-color: #333; border-radius: 26px; transition: 0.3s; }
        .toggle-switch::after { content: ''; position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; background-color: white; border-radius: 50%; transition: 0.3s; }
        input[type="checkbox"]:checked + .toggle-switch { background-color: var(--spotify-green); }
        input[type="checkbox"]:checked + .toggle-switch::after { transform: translateX(24px); }
        
        .slider-container { display: flex; align-items: center; gap: 15px; flex: 1; min-width: 200px; }
        input[type="range"] { flex: 1; accent-color: var(--spotify-green); cursor: pointer; }
        .range-val { font-weight: bold; width: 35px; text-align: center; background: #333; padding: 5px; border-radius: 4px; }
        
        .status-bar { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background-color: #333; color: white; padding: 12px 24px; border-radius: 500px; font-weight: bold; box-shadow: 0 8px 24px rgba(0,0,0,0.5); z-index: 2000; display: none; transition: opacity 0.3s; }
        .status-success { background-color: var(--spotify-green); color: black; }
        .status-error { background-color: #FA243C; color: white;}
        .status-warning { background-color: #FF9900; color: black;}
    </style>
</head>
<body>
    <div id="status-bar" class="status-bar">Notification</div>

    <div class="main-container">
        <div id="mobile-overlay" class="sidebar-overlay" onclick="toggleMobileMenu()"></div>
        <nav class="sidebar"></nav>

        <main class="main-view">
            <div class="top-bar">
                <div style="display: flex; flex: 1; min-width: 0; align-items: center;">
                    <button class="mobile-menu-btn" onclick="toggleMobileMenu(event)">
                        <i class="fas fa-bars"></i>
                    </button>
                    <h2 class="section-title" style="margin: 0; padding-left: 15px;">
                        <i class="fas fa-cog" style="color: var(--spotify-green); margin-right: 10px;"></i> Configuration de l'enceinte
                    </h2>
                </div>
                <div class="remote-wrapper" id="remote-wrapper"></div>
            </div>

            <div class="config-container">
                <div id="no-speaker-msg" style="text-align: center; color: var(--text-subdued); margin: 40px 0;">
                    <div class="loader" style="margin: 0 auto 15px auto;"></div>
                    Sélectionne une enceinte dans le menu pour la configurer...
                </div>

                <div id="config-forms" class="hidden">
                    
                    <!-- Nom de l'enceinte -->
                    <div class="config-section">
                        <div class="config-header"><i class="fas fa-tag"></i> Nom de l'enceinte</div>
                        <div class="config-row">
                            <input type="text" id="conf-name" class="config-input" placeholder="Ex: Salon">
                            <button class="config-btn" onclick="saveName()">Enregistrer</button>
                        </div>
                    </div>

                    <!-- Basses -->
                    <div class="config-section">
                        <div class="config-header"><i class="fas fa-volume-down"></i> Réduction des Basses</div>
                        <p style="font-size:13px; color:var(--text-subdued); margin-bottom:15px;">Ajuste le niveau des basses de ton enceinte (plage de -9 à 0).</p>
                        <div class="config-row">
                            <div class="slider-container">
                                <input type="range" id="conf-bass" min="-9" max="0" value="0" oninput="document.getElementById('bass-val').innerText = this.value">
                                <span id="bass-val" class="range-val">0</span>
                            </div>
                            <button class="config-btn" onclick="saveBass()">Appliquer</button>
                        </div>
                    </div>

                    <!-- Horloge -->
                    <div class="config-section">
                        <div class="config-header"><i class="fas fa-clock"></i> Horloge</div>
                        <p style="font-size:13px; color:var(--text-subdued); margin-bottom:15px;">Affiche et configure l'horloge sur l'écran (disponible selon le modèle).</p>
                        
                        <div class="config-row">
                            <label class="config-toggle">
                                <input type="checkbox" id="conf-clock-enable" style="display:none;" checked>
                                <div class="toggle-switch"></div>
                                <span>Afficher l'horloge</span>
                            </label>
                        </div>
                        
                        <div class="config-row">
                            <select id="conf-TZ" class="config-select">
                                <option value="Europe/Paris" selected>Europe/Paris</option>
                                <option value="Europe/London">Europe/London</option>
                                <option value="Europe/Berlin">Europe/Berlin</option>
                            </select>
                            <label class="config-toggle">
                                <input type="checkbox" id="conf-clock-24" style="display:none;" checked>
                                <div class="toggle-switch"></div>
                                <span>Format 24h</span>
                            </label>
                        </div>
                        
                        <div class="config-row">
                            <span style="font-size: 14px; width: 90px; color: var(--text-subdued);">Luminosité :</span>
                            <div class="slider-container">
                                <input type="range" id="conf-bri" min="0" max="100" value="70" oninput="document.getElementById('bri-val').innerText = this.value">
                                <span id="bri-val" class="range-val">70</span>
                            </div>
                        </div>

                        <div class="config-row" style="justify-content: flex-end; margin-top: 15px;">
                            <button class="config-btn" onclick="saveClock()">Mettre à jour l'horloge</button>
                        </div>
                    </div>

                    <!-- Langue -->
                    <div class="config-section">
                        <div class="config-header"><i class="fas fa-language"></i> Langue système</div>
                        <div class="config-row">
                            <select id="conf-language" class="config-select">
                                <option value="5" selected>Français</option>
                                <option value="1">Dansk</option>
                                <option value="2">Deutsch</option>
                                <option value="3">English</option>
                                <option value="4">Español</option>
                                <option value="6">Italiano</option>
                                <option value="7">Nederlands</option>
                                <option value="8">Svenska</option>
                                <option value="9">日本語</option>
                                <option value="10">简体中文</option>
                                <option value="11">繁體中文</option>
                                <option value="12">한국어</option>
                                <option value="13">ไทย</option>
                                <option value="14">Čeština</option>
                                <option value="15">Suomi</option>
                                <option value="16">Ελληνικά</option>
                                <option value="17">Norsk</option>
                                <option value="18">Polski</option>
                                <option value="19">Português</option>
                                <option value="20">Română</option>
                                <option value="21">Русский</option>
                                <option value="22">Slovenščina</option>
                                <option value="23">Türkçe</option>
                                <option value="24">Magyar</option>
                            </select>
                            <button class="config-btn" onclick="saveLanguage()">Appliquer</button>
                        </div>
                    </div>

                    <!-- Mise en veille -->
                    <div class="config-section">
                        <div class="config-header"><i class="fas fa-power-off"></i> Mise en veille automatique</div>
                        <p style="font-size:13px; color:var(--text-subdued); margin-bottom:15px;">L'enceinte se mettra en veille d'elle-même après 20 minutes d'inactivité.</p>
                        <div class="config-row">
                            <label class="config-toggle">
                                <input type="checkbox" id="conf-timeout-enable" style="display:none;" checked>
                                <div class="toggle-switch"></div>
                                <span>Activer la mise en veille</span>
                            </label>
                            <button class="config-btn" onclick="saveTimeout()">Appliquer</button>
                        </div>
                    </div>

                    <!-- Optimisation AirPlay -->
                    <div class="config-section">
                        <div class="config-header"><i class="fab fa-apple"></i> Optimisation AirPlay (Vidéo Sync)</div>
                        <p style="font-size:13px; color:var(--text-subdued); margin-bottom:15px;">Désactive le délai audio de traitement pour éviter le décalage lors du visionnage d'une vidéo.</p>
                        <div class="config-row">
                            <label class="config-toggle">
                                <input type="checkbox" id="conf-airplay-sync" style="display:none;">
                                <div class="toggle-switch"></div>
                                <span>Désactiver le délai (Optimisation activée)</span>
                            </label>
                            <button class="config-btn" onclick="saveAirplay()">Appliquer</button>
                        </div>
                    </div>

                </div>
            </div>
        </main>
    </div>

    <footer class="player-bar"></footer>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script src="js/app.js"></script>
    
    <script>
        let currentConfigIp = null;

        function showNotification(msg, type = "warning") {
            const statusBar = document.getElementById('status-bar');
            statusBar.innerText = msg;
            statusBar.className = `status-bar status-${type}`;
            statusBar.style.display = 'block';
            setTimeout(() => { statusBar.style.display = 'none'; }, 4000);
        }

        document.addEventListener("DOMContentLoaded", async () => {
            await loadComponent(null, "components/remotesimple.svg", "#remote-wrapper");
            setInterval(checkSelectedSpeaker, 1000);
        });

        function checkSelectedSpeaker() {
            if (typeof getSelectedIps !== "function" || !globalData.speakers) return;
            const ips = getSelectedIps();
            const forms = document.getElementById("config-forms");
            const noMsg = document.getElementById("no-speaker-msg");

            if (ips.length === 0 || !globalData.speakers[ips[0]]) {
                forms.classList.add('hidden');
                noMsg.classList.remove('hidden');
                currentConfigIp = null;
                return;
            }

            if (currentConfigIp !== ips[0]) {
                currentConfigIp = ips[0];
                forms.classList.remove('hidden');
                noMsg.classList.add('hidden');
                document.getElementById('conf-name').value = globalData.speakers[currentConfigIp].name || "";
                fetchCurrentConfig(currentConfigIp);
            }
        }

        async function fetchCurrentConfig(ip) {
            // Lecture des Basses
            try {
                let res = await fetch(`http://${ip}:8090/bass`);
                if (res.ok) {
                    let text = await res.text();
                    let match = text.match(/<targetbass>(-?\d+)<\/targetbass>/);
                    if (match) {
                        let val = parseInt(match[1]);
                        if (val > 0) val = 0; 
                        document.getElementById('conf-bass').value = val;
                        document.getElementById('bass-val').innerText = val;
                    }
                }
            } catch (e) {
                console.log("Impossible de lire les basses.");
            }

            // Lecture du Nom
            try {
                let resName = await fetch(`http://${ip}:8090/name`);
                if (resName.ok) {
                    let textName = await resName.text();
                    let matchName = textName.match(/<name>(.*?)<\/name>/);
                    if (matchName) {
                        document.getElementById('conf-name').value = matchName[1];
                    }
                }
            } catch (e) {
                console.log("Impossible de lire le nom.");
            }
        }

        async function sendDirectXml(endpoint, xmlData) {
            if (!currentConfigIp) return showNotification("Sélectionne une enceinte.", "error");
            const url = `http://${currentConfigIp}:8090/${endpoint}`;
            
            try {
                const res = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/xml' },
                    body: xmlData
                });
                
                if (res.ok || res.type === 'opaque') {
                    showNotification("Mise à jour envoyée avec succès !", "success");
                    setTimeout(() => fetch('/api/poll', {method:'POST'}), 1000);
                } else {
                    showNotification("Erreur lors de la communication avec l'enceinte.", "error");
                }
            } catch (e) {
                // Tentative en mode no-cors
                try {
                    await fetch(url, { method: 'POST', mode: 'no-cors', body: xmlData });
                    showNotification("Commande envoyée à l'enceinte.", "success");
                    setTimeout(() => fetch('/api/poll', {method:'POST'}), 1000);
                } catch (err) {
                    showNotification("Impossible de joindre l'enceinte.", "error");
                }
            }
        }

        function saveName() {
            const name = document.getElementById('conf-name').value;
            if(!name) return;
            sendDirectXml('name', `<name>${name}</name>`);
            
            // Met à jour l'UI locale immédiatement pour la sensation de fluidité
            if (globalData.speakers[currentConfigIp]) {
                globalData.speakers[currentConfigIp].name = name;
            }
        }

        function saveBass() {
            const val = document.getElementById('conf-bass').value;
            sendDirectXml('bass', `<bass>${val}</bass>`);
        }

        function saveClock() {
            const isEnabled = document.getElementById('conf-clock-enable').checked;
            const tz = document.getElementById('conf-TZ').value;
            const is24h = document.getElementById('conf-clock-24').checked;
            const format = is24h ? "TIME_FORMAT_24HOUR_ID" : "TIME_FORMAT_12HOUR_ID";
            const brightness = document.getElementById('conf-bri').value;
            
            const xml = `<clockDisplay><clockConfig timezoneInfo="${tz}" userEnable="${isEnabled}" timeFormat="${format}" userOffsetMinute="0" brightnessLevel="${brightness}" userUtcTime="0"/></clockDisplay>`;
            sendDirectXml('clockDisplay', xml);
        }

        function saveLanguage() {
            const val = document.getElementById('conf-language').value;
            sendDirectXml('language', `<sysLanguage>${val}</sysLanguage>`);
        }

        function saveTimeout() {
            const isEnabled = document.getElementById('conf-timeout-enable').checked;
            sendDirectXml('systemtimeout', `<systemtimeout><powersaving_enabled>${isEnabled}</powersaving_enabled></systemtimeout>`);
        }

        function saveAirplay() {
            const syncActive = document.getElementById('conf-airplay-sync').checked;
            const delay = syncActive ? "0" : "100";
            sendDirectXml('audiodspcontrols', `<audiodspcontrols videosyncaudiodelay="${delay}"/>`);
        }
    </script>
</body>
</html>

```
<br>

### `www/css/global.css`

```text
:root {
    --spotify-green: #1DB954;
    --bg-base: #121212;
    --bg-elevated: #181818;
    --bg-highlight: #282828;
    --text-base: #FFFFFF;
    --text-subdued: #B3B3B3;
}

* { 
    margin: 0; 
    padding: 0; 
    box-sizing: border-box; 
    font-family: 'Helvetica Neue', Arial, sans-serif; 
}

body { 
    background-color: var(--bg-base); 
    color: var(--text-base); 
    height: 100dvh; 
    display: flex; 
    flex-direction: column; 
    overflow: hidden; 
}

/* --- LAYOUT PRINCIPAL --- */
.main-container { 
    display: flex; 
    flex: 1; 
    overflow: hidden; 
    position: relative; 
}

/* --- SIDEBAR & OVERLAY MOBILE --- */
.sidebar-overlay { 
    display: none; 
    position: absolute; 
    top: 0; left: 0; right: 0; bottom: 0; 
    background: rgba(0, 0, 0, 0.7); 
    z-index: 999; 
    backdrop-filter: blur(2px); 
    transition: opacity 0.3s; 
}
.sidebar-overlay.active { display: block; }

.sidebar { 
    width: 250px; 
    background-color: #000000; 
    padding: 24px 12px; 
    display: flex; 
    flex-direction: column; 
    overflow-y: auto; 
    z-index: 1000; 
    transition: left 0.3s ease; 
}
.sidebar::-webkit-scrollbar { width: 6px; }
.sidebar::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }

.brand { font-size: 24px; font-weight: bold; margin-bottom: 30px; padding-left: 12px; display: flex; align-items: center; gap: 10px; cursor: pointer; user-select: none; }
.nav-section { margin-bottom: 24px; }
.nav-section h3 { font-size: 12px; color: var(--text-subdued); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; padding-left: 12px; }

.nav-item { display: flex; align-items: center; padding: 10px 12px; color: var(--text-subdued); cursor: pointer; border-radius: 4px; transition: color 0.2s; font-size: 14px; font-weight: bold; gap: 15px; text-decoration: none;}
.nav-item:hover, .nav-item.active { color: var(--text-base); }
.nav-item.active { background-color: rgba(255,255,255,0.1); }
.nav-item input[type="checkbox"] { accent-color: var(--spotify-green); width: 16px; height: 16px; cursor: pointer; }
/*
#id-nav-spotify { color: var(--spotify-green); }
*/

.action-buttons { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; padding: 0 12px; }
.btn-action { background-color: transparent; border: 1px solid var(--text-subdued); color: var(--text-base); padding: 8px; border-radius: 500px; cursor: pointer; width: 100%; font-weight: bold; transition: all 0.2s; display: flex; justify-content: center; align-items: center; gap: 8px; font-size: 13px; }
.btn-action:hover { border-color: white; color: white; background-color: rgba(255,255,255,0.1); }
.btn-action-primary { border-color: var(--spotify-green); color: var(--spotify-green); }
.btn-action-primary:hover { background-color: rgba(29, 185, 84, 0.1); border-color: #1ed760; color: #1ed760; }

/* --- CONTENU PRINCIPAL & HAUT DE PAGE --- */
.main-view { flex: 1; background: linear-gradient(180deg, #2a2a2a 0%, var(--bg-base) 100%); padding: 24px; overflow-y: auto; display: flex; flex-direction: column; }
/* .top-bar { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 30px; height: 20%}*/
/* .top-bar : centrer verticalement au lieu d'aligner en haut */
.top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; height: 20%; }

/* Empêcher les wrappers d'icônes de se faire écraser par le bloc recherche */
.sources-wrapper, .remote-wrapper, .mid-remote-wrapper { flex-shrink: 0; }

.search-container { display: flex; gap: 10px; max-width: 500px; flex: 1; height: 45px;}
.search-input { flex: 1; padding: 0 20px; border-radius: 500px; border: none; background-color: #fff; color: #000; font-size: 14px; outline: none; }
.search-select { padding: 0 15px; border-radius: 500px; border: none; background-color: #333; color: white; font-size: 14px; outline: none; cursor: pointer; }
.btn-search { background-color: var(--spotify-green); color: white; border: none; border-radius: 500px; padding: 0 24px; font-weight: bold; cursor: pointer; transition: transform 0.1s;}
.btn-search:hover { transform: scale(1.04); background-color: #1ed760; }

.section-title { font-size: 24px; font-weight: bold; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }

/* --- GRILLES & CARTES DE RÉSULTATS --- */
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 24px; }
.card { background-color: var(--bg-elevated); padding: 16px; border-radius: 8px; transition: background-color 0.3s; display: flex; flex-direction: column; }
.card:hover { background-color: var(--bg-highlight); }
.card-icon { width: 100%; aspect-ratio: 1; background-color: #333; border-radius: 4px; margin-bottom: 16px; display: flex; justify-content: center; align-items: center; font-size: 48px; color: var(--text-subdued); box-shadow: 0 8px 24px rgba(0,0,0,0.5); cursor: pointer; transition: color 0.2s; background-size: cover; background-position: center;}
.card-icon:hover { color: white; }
.card-title { font-weight: bold; font-size: 16px; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-subtitle { font-size: 14px; color: var(--text-subdued); }

.card-actions { display: flex; justify-content: flex-end; margin-top: 15px; gap: 8px; }
.btn-card { padding: 8px 16px; border: none; border-radius: 500px; font-weight: bold; cursor: pointer; font-size: 12px; transition: all 0.1s; }

.btn-card-play { background-color: var(--text-base); color: black; }
.btn-card-play:hover { transform: scale(1.05); background-color: white; }
.btn-card-add { background-color: transparent; border: 1px solid var(--text-subdued); color: var(--text-base); }
.btn-card-add:hover { border-color: white; color: white; }

/* --- BARRE DE LECTURE (FOOTER) --- */
.player-bar { height: 90px; background-color: var(--bg-elevated); border-top: 1px solid #282828; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; position: relative; z-index: 10; }
.now-playing { display: flex; align-items: center; width: 30%; gap: 14px; }
.cover-art { width: 56px; height: 56px; background-color: #282828; border-radius: 4px; background-size: cover; background-position: center; display: flex; justify-content: center; align-items: center; cursor: pointer; }
.track-info { display: flex; flex-direction: column; overflow: hidden; }
.track-name { font-size: 14px; font-weight: bold; color: var(--text-base); margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.artist-name { font-size: 12px; color: var(--text-subdued); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.album-name { font-size: 13px; color: var(--text-subdued); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-style: italic; }

.player-controls { display: flex; flex-direction: column; align-items: center; width: 40%; }
.buttons { display: flex; align-items: center; gap: 24px; margin-bottom: 8px; }
.btn-control { background: none; border: none; color: var(--text-subdued); font-size: 16px; cursor: pointer; transition: color 0.2s; }
.btn-control:hover { color: var(--text-base); }
.btn-play { background-color: var(--text-base); color: black; width: 32px; height: 32px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 14px; }
.btn-play:hover { transform: scale(1.05); background-color: white; color: black; }

/* --- INTERRUPTEURS & UTILS --- */
.hidden { display: none !important; }
.loader { border: 4px solid #f3f3f3; border-top: 4px solid var(--spotify-green); border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

.mobile-menu-btn { display: none; background: none; border: none; color: var(--text-base); font-size: 24px; cursor: pointer; z-index: 1001; }

/* --- SVG REMOTE (Bose) --- */
.remote-wrapper { 
    background-color: rgba(0,0,0,0.3); 
    border-radius: 12px; 
    padding: 10px; 
    box-shadow: 0 8px 24px rgba(0,0,0,0.5); 
}
.invisible-btn { 
    cursor: pointer; 
    fill: transparent; 
    pointer-events: all; 
    transition: fill 0.15s ease; 
}
.invisible-btn:hover { 
    fill: rgba(255, 255, 255, 0.15); 
}

.preset-label { 
    font-size: 11px; 
    fill: #ffffff; 
    pointer-events: none; 
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
    font-weight: bold; 
    text-shadow: 0px 1px 2px rgba(0,0,0,0.8); 
}
.preset-labelg { 
    font-size: 19px; 
    fill: #ffffff; 
    pointer-events: none; 
    font-family: 'Segoe UI', Tahoma, sans-serif; 
    font-weight: bold; 
    text-shadow: 0px 0.2px 0.5px rgba(0,0,0,0.8); 
}

.preset-labelm {}

/* ========================================================================= */
/* ENCEINTES & ÉTATS (ZONES) + SÉLECTION HYBRIDE                             */
/* ========================================================================= */

.speaker-item {
    display: flex;
    justify-content: space-between; /* Aligne le contenu à gauche et la coche à droite */
    align-items: center;
    padding: 10px 12px;
    margin-bottom: 8px;
    background-color: var(--bg-elevated);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 1px solid transparent;
    
    /* TRÈS IMPORTANT : Empêche la sélection native de texte sur appui long mobile */
    -webkit-user-select: none;
    -moz-user-select: none;
    -ms-user-select: none;
    user-select: none; 
}

.speaker-item:hover {
    background-color: var(--bg-highlight);
}

.speaker-item.selected {
    border-color: var(--spotify-green);
    background-color: rgba(29, 185, 84, 0.1);
}

.speaker-checkbox {
    accent-color: var(--spotify-green);
    width: 16px;
    height: 16px;
    cursor: pointer;
    margin-right: 12px;
}

.status-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 10px;
    flex-shrink: 0;
}

.status-green { 
    background-color: var(--spotify-green); 
    box-shadow: 0 0 6px var(--spotify-green); 
}

.status-orange { 
    background-color: #FFC107; 
    box-shadow: 0 0 6px #FFC107; 
}

.status-red { 
    background-color: #FA243C; 
    box-shadow: 0 0 6px #FA243C; 
}

.speaker-name {
    font-size: 14px;
    font-weight: bold;
    color: var(--text-base);
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* --- INDICATEUR DE SÉLECTION MULTIPLE (Caché par défaut) --- */
.multi-check-indicator {
    display: none;
    width: 20px;
    height: 20px;
    border: 2px solid #555;
    border-radius: 4px;
    align-items: center;
    justify-content: center;
    color: transparent;
    font-size: 12px;
}

.multi-select-active .multi-check-indicator {
    display: flex;
}

.multi-select-active .speaker-item.selected .multi-check-indicator {
    background-color: var(--spotify-green);
    border-color: var(--spotify-green);
    color: black;
}

/* --- BOUTON QUITTER MODE MULTI --- */
.btn-exit-multi {
    background-color: var(--bg-elevated);
    color: var(--text-base);
    border: 1px solid #555;
    padding: 4px 10px;
    border-radius: 500px;
    font-size: 12px;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-exit-multi:hover {
    background-color: var(--spotify-green);
    color: black;
    border-color: var(--spotify-green);
}

/* --- LE WRAPPER DE LA TÉLÉCOMMANDE --- */
.mid-remote-wrapper {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 100%;
    max-width: 300px; 
    margin: 20px auto 40px auto;
    position: relative;
    z-index: 105;
}

/* --- LE SVG : ON RÉPARE LE BUG DE DÉCALAGE --- */
#mid-remote-wrapper svg {
    width: 100% !important; 
    height: auto !important;
    display: block;
    position: relative !important; 
    filter: drop-shadow(0 15px 25px rgba(0,0,0,0.5));
    pointer-events: auto !important; 
}

#mid-remote-wrapper svg rect.invisible-btn {
    cursor: pointer;
    pointer-events: all !important; 
}

#mid-remote-wrapper svg text {
    pointer-events: none !important;
}

/* ==========================================
   FOOTER : JAUGE DE VOLUME & SMARTPHONE
   ========================================== */
.volume-controls {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 300px;
}

.volume-controls input[type="range"] {
    width: 100%;
    cursor: pointer;
    accent-color: #1DB954;
}

.volume-icon {
    color: #888;
    font-size: 1rem;
}

/* --- AFFICHAGE RESPONSIVE TABLETTES & SMARTPHONES --- */
@media (max-width: 768px) {
    .sidebar { position: absolute; left: -260px; top: 0; bottom: 0; box-shadow: 4px 0 15px rgba(0,0,0,0.8); }
    .sidebar.active { left: 0; }
    .mobile-menu-btn { display: block; margin-right: 15px; }
    .search-container { max-width: 100%; flex-wrap: wrap; height: auto; justify-content: center; }
    .search-input { width: 100%; flex: none; height: 45px; margin-bottom: 10px; }
    .grid { grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 15px; }

    /* --- ON DÉBLOQUE LA HAUTEUR DE LA BARRE --- */
    .top-bar { 
        flex-direction: column !important; 
        align-items: center !important; 
        gap: 20px !important; 
        height: auto !important;       
        min-height: auto !important;
        padding-bottom: 25px !important; 
        position: relative !important; 
    }

    .remote-container {
        position: relative !important; 
        top: auto !important;
        right: auto !important;
        width: 100% !important;
        height: auto !important; 
    }

    .remote-wrapper { 
        display: block !important;
        width: 100% !important;
        max-width: 320px !important; 
        margin: 0 auto !important; 
        position: relative !important;
        height: auto !important; 
    }

    .mid-remote-wrapper {
        display: block !important;
        width: 100% !important;
        max-width: 320px !important; 
        margin: 0 auto !important; 
        position: relative !important;
        height: auto !important; 
    }

    #mid-remote-wrapper svg {
        width: 100%; 
        height: auto;
        pointer-events: none; 
    }

    #mid-remote-wrapper svg g, 
    #mid-remote-wrapper svg path, 
    #mid-remote-wrapper svg rect, 
    #mid-remote-wrapper svg circle, 
    #mid-remote-wrapper svg text {
        pointer-events: auto;
    }

    .player-bar { display: flex !important; height: 75px; padding: 0 10px; }
    .now-playing { width: 55%; gap: 10px; }
    .cover-art { width: 45px; height: 45px; min-width: 45px; }
    .player-controls { width: 45%; }
    .buttons { gap: 15px; }

    .now-playing .track-info {
        display: none !important;
    }
    
    .volume-controls {
        width: 100%;
    }
}

```
<br>

### `www/dlna_browser.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
 	<!-- PWA et Manifest -->
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#121212">

    <!-- Optimisations spécifiques pour iOS (Apple) -->
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoundCork">
    <link rel="apple-touch-icon" href="img/icon-192.png">

   <title>Navigateur NAS - SoundTouch</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <link rel="stylesheet" href="css/global.css">
    <style>
        .dlna-nav-header { 
            display: flex; 
            align-items: center; 
            justify-content: space-between;
            background-color: var(--bg-elevated); 
            padding: 15px 20px; 
            border-radius: 8px; 
            margin-bottom: 20px; 
        }
        .dlna-path-container { display: flex; align-items: center; gap: 15px; flex: 1;}
        .current-path { font-size: 16px; font-weight: bold; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
        
        .list-content { display: flex; flex-direction: column; gap: 8px; padding-bottom: 20px; }
        
        .dlna-item { 
            display: flex; 
            align-items: center; 
            padding: 10px 15px; 
            background-color: var(--bg-elevated); 
            border-radius: 6px; 
            cursor: pointer; 
            transition: background-color 0.2s; 
        }
        .dlna-item:hover { background-color: var(--bg-highlight); }
        
        .item-icon-wrapper { 
            width: 45px; 
            height: 45px; 
            background-color: #333; 
            border-radius: 4px; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            margin-right: 15px; 
            font-size: 20px; 
            flex-shrink: 0;
            overflow: hidden;
            color: var(--text-subdued);
        }
        .item-img { width: 100%; height: 100%; object-fit: cover; }
        .item-details { flex: 1; overflow: hidden; }
        .item-title { font-weight: bold; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 2px;}
        .item-subtitle { font-size: 12px; color: var(--text-subdued); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}

        .status-bar { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background-color: #333; color: white; padding: 12px 24px; border-radius: 500px; font-weight: bold; box-shadow: 0 8px 24px rgba(0,0,0,0.5); z-index: 2000; display: none; transition: opacity 0.3s; }
        .status-success { background-color: var(--spotify-green); color: black; }
        .status-error { background-color: #FA243C; color: white;}
        .status-warning { background-color: #FF9900; color: black;}
    </style>
</head>
<body>
    <div id="status-bar" class="status-bar">Notification</div>

    <div class="main-container">
        <div id="mobile-overlay" class="sidebar-overlay" onclick="toggleMobileMenu()"></div>
        <nav class="sidebar"></nav>

        <main class="main-view">
            <div class="top-bar">
                <div style="display: flex; flex: 1; min-width: 0; align-items: center;">
					<button class="mobile-menu-btn" onclick="toggleMobileMenu(event)">
                        <i class="fas fa-bars"></i>
                    </button>
                    
                    <div class="search-container" style="margin-left: 15px; flex: 1;">
                        <input type="text" id="dlna-search-input" class="search-input" placeholder="Rechercher sur le NAS...">
                        <select id="dlna-search-type" class="search-select">
                            <option value="all">Tous</option>
                            <option value="title">Titre</option>
                            <option value="artist">Artiste</option>
                            <option value="album">Album</option>
                        </select>
                        <button class="btn-search" onclick="performSearch()">Rechercher</button>
						<h2>Serveur DLNA</h2>
                    </div>
                </div>
                
                <div class="remote-wrapper" id="remote-wrapper"></div>
            </div>

            <div class="dlna-nav-header">
                <div class="dlna-path-container">
                    <button class="btn-action" id="backBtn" onclick="goBack()" style="width: auto; display: none; padding: 6px 15px;">
                        <i class="fas fa-arrow-left"></i> Retour
                    </button>
                    <h3 id="current-path" class="current-path">Recherche des serveurs...</h3>
                </div>
            </div>

            <div class="list-content" id="content-list">
                <div style="text-align: center; color: var(--text-subdued); margin-top: 40px;">
                    <div class="loader" style="margin: 0 auto 15px auto;"></div>
                    Recherche sur le réseau...
                </div>
            </div>

        </main>
    </div>

    <footer class="player-bar"></footer>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
	<script src="js/app.js"></script>
    <script>
        let navigationHistory = [];
        let currentAccount = null; 

        function showNotification(msg, type = "warning") {
            const statusBar = document.getElementById('status-bar');
            statusBar.innerText = msg;
            statusBar.className = `status-bar status-${type}`;
            statusBar.style.display = 'block';
            setTimeout(() => { statusBar.style.display = 'none'; }, 3000);
        }

        function escapeXml(unsafe) {
            if (!unsafe) return "";
            return unsafe.replace(/[<>&'"]/g, function (c) {
                switch (c) {
                    case '<': return '&lt;'; case '>': return '&gt;';
                    case '&': return '&amp;'; case '\'': return '&apos;';
                    case '"': return '&quot;';
                }
            });
        }

        async function loadServers() {
            navigationHistory = [];
            currentAccount = null;
            document.getElementById('backBtn').style.display = 'none';
            document.getElementById('current-path').innerText = 'Serveurs Réseau';
            
            const ips = getSelectedIps();
            if (ips.length === 0) {
                document.getElementById('content-list').innerHTML = '<p style="text-align:center; color:#FA243C; margin-top:40px;">Veuillez sélectionner au moins une enceinte.</p>';
                return;
            }

            try {
                const res = await fetch(`/api/upnp/servers?ip=${ips[0]}`);
                const servers = await res.json();

                if (servers.error) throw new Error("Erreur Backend: " + servers.error);

                if (!Array.isArray(servers) || servers.length === 0) {
                    document.getElementById('content-list').innerHTML = '<p style="text-align:center; color:var(--text-subdued); margin-top:40px;">Aucun serveur DLNA détecté.</p>';
                    return;
                }

                let html = '';
                servers.forEach(srv => {
                    html += `
                        <div class="dlna-item" onclick="openFolder('${srv.location}', '${srv.account}', '0', '${escapeXml(srv.name)}')">
                            <div class="item-icon-wrapper"><i class="fas fa-server" style="color: #1DB954;"></i></div>
                            <div class="item-details">
                                <div class="item-title">${srv.name}</div>
                                <div class="item-subtitle">Serveur DLNA/UPnP</div>
                            </div>
                            <i class="fas fa-chevron-right" style="color: var(--text-subdued);"></i>
                        </div>
                    `;
                });
                
                document.getElementById('content-list').innerHTML = html;
            } catch (e) {
                console.error(e);
                document.getElementById('content-list').innerHTML = '<p style="text-align:center; color:#FA243C; margin-top:40px;">Erreur de communication.</p>';
            }
        }

        async function openFolder(location, account, nodeId, title, isBack = false) {
            currentAccount = account;

            if (!isBack) {
                navigationHistory.push({ location, account, nodeId, title });
            }

            document.getElementById('backBtn').style.display = 'block';
            document.getElementById('current-path').innerText = title;
            document.getElementById('content-list').innerHTML = '<div style="text-align: center; color: var(--text-subdued); margin-top: 40px;"><div class="loader" style="margin: 0 auto 15px auto;"></div>Chargement du dossier...</div>';

            try {
                const res = await fetch('/api/upnp/navigate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ location: location, node_id: nodeId })
                });
                
                const data = await res.json();
                
                if (data.error) throw new Error(data.error);
                if (!data.items || data.items.length === 0) {
                    document.getElementById('content-list').innerHTML = '<p style="text-align:center; color:var(--text-subdued); margin-top:40px;">Dossier vide.</p>';
                    return;
                }

                let html = '';
                let trackIndex = 0; 

				data.items.forEach(item => {
                    const cleanName = item.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    
                    if (item.is_dir) {
                        html += `
                            <div class="dlna-item" onclick="openFolder('${location}', '${account}', '${item.node_id}', '${cleanName}')">
                                <div class="item-icon-wrapper" style="background-color: transparent;"><i class="fas fa-folder" style="color: #FFC107; font-size: 28px;"></i></div>
                                <div class="item-details">
                                    <div class="item-title">${item.name}</div>
                                </div>
                                <i class="fas fa-chevron-right" style="color: var(--text-subdued);"></i>
                            </div>
                        `;
                    } else {
                        let currentIndex = trackIndex;
                        const coverHtml = item.cover 
                            ? `<img src="${item.cover}" class="item-img" onerror="this.style.display='none'">` 
                            : `<i class="fas fa-music"></i>`;

                        html += `
                            <div class="dlna-item" onclick="playNativePurist('${item.node_id}', '${nodeId}', ${currentIndex}, '${cleanName}')">
                                <div class="item-icon-wrapper">${coverHtml}</div>
                                <div class="item-details">
                                    <div class="item-title">${item.name}</div>
                                    <div class="item-subtitle">${item.artist || 'Artiste inconnu'} ${item.album ? '• ' + item.album : ''}</div>
                                </div>
                                <button class="btn-card btn-card-play" style="padding: 5px 15px; border-radius: 500px; font-weight: bold; background: white; color: black; border: none; cursor: pointer; margin-left: 10px;">▶ Lire</button>
                            </div>
                        `;
                        trackIndex++;
                    }
                });
                
                document.getElementById('content-list').innerHTML = html;
            } catch (e) {
                console.error(e);
                document.getElementById('content-list').innerHTML = '<p style="text-align:center; color:#FA243C; margin-top:40px;">Erreur avec le NAS.</p>';
            }
        }

        function goBack() {
            if (navigationHistory.length > 1) {
                navigationHistory.pop();
                const parent = navigationHistory[navigationHistory.length - 1]; 
                openFolder(parent.location, parent.account, parent.nodeId, parent.title, true);
            } else {
                loadServers();
            }
        }

        async function playNativePurist(nodeId, folderId, offsetIndex, trackTitle) {
            const ips = getSelectedIps();
            if (ips.length === 0) return showNotification("Sélectionnez au moins une enceinte.", "error");

            showNotification("⏳ Lancement natif sur l'enceinte...", "warning");
            
            const currentFolder = navigationHistory[navigationHistory.length - 1];

            try {
                const res = await fetch('/api/upnp/play', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ 
                        ip: ips[0], 
                        node_id: nodeId,
                        folder_id: folderId,
                        offset: offsetIndex,
                        account: currentAccount,
                        track_title: escapeXml(trackTitle),
                        folder_title: escapeXml(currentFolder.title)
                    })
                });
                
                if (res.ok) {
                    showNotification("✅ Lecture native fluide lancée !", "success");
                    setTimeout(fetchState, 1500); 
                } else {
                    showNotification("❌ Erreur de l'enceinte", "error");
                }
            } catch (e) {
                showNotification("❌ Erreur réseau", "error");
            }
        }

        async function performSearch() {
            const query = document.getElementById('dlna-search-input').value.trim();
            const type = document.getElementById('dlna-search-type').value;
            
            if (!query) return showNotification("Veuillez entrer un terme de recherche.", "warning");
            if (!currentAccount) return showNotification("Veuillez d'abord sélectionner un serveur ou un dossier.", "error");

            if (navigationHistory.length === 0) return showNotification("Naviguez d'abord dans un serveur.", "warning");
            const serverLocation = navigationHistory[0].location;

            document.getElementById('current-path').innerText = `Recherche : "${query}"`;
            document.getElementById('content-list').innerHTML = '<div style="text-align: center; color: var(--text-subdued); margin-top: 40px;"><div class="loader" style="margin: 0 auto 15px auto;"></div>Recherche en cours...</div>';
            document.getElementById('backBtn').style.display = 'block';

            try {
                const res = await fetch('/api/upnp/search', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ location: serverLocation, query: query, type: type })
                });
                
                const data = await res.json();
                
                if (data.error) throw new Error(data.error);
                if (!data.items || data.items.length === 0) {
                    document.getElementById('content-list').innerHTML = '<p style="text-align:center; color:var(--text-subdued); margin-top:40px;">Aucun résultat trouvé.</p>';
                    return;
                }

                let html = '';
                data.items.forEach(item => {
                    const cleanName = item.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    const parentId = item.parent_id || '0'; 
                    
                    const coverHtml = item.cover 
                        ? `<img src="${item.cover}" class="item-img" onerror="this.style.display='none'">` 
                        : `<i class="fas fa-search" style="color: var(--spotify-green);"></i>`;
                    
                    html += `
                        <div class="dlna-item" onclick="playNativePurist('${item.node_id}', '${parentId}', 0, '${cleanName}')">
                            <div class="item-icon-wrapper">${coverHtml}</div>
                            <div class="item-details">
                                <div class="item-title">${item.name}</div>
                                <div class="item-subtitle">${item.artist || 'Artiste inconnu'} ${item.album ? '• ' + item.album : ''}</div>
                            </div>
                            <button class="btn-card btn-card-play" style="padding: 5px 15px; border-radius: 500px; font-weight: bold; background: white; color: black; border: none; cursor: pointer; margin-left: 10px;">▶ Lire</button>
                        </div>
                    `;
                });
                
                document.getElementById('content-list').innerHTML = html;
            } catch (e) {
                console.error(e);
                document.getElementById('content-list').innerHTML = '<p style="text-align:center; color:#FA243C; margin-top:40px;">Erreur. Le NAS ne supporte peut-être pas la fonction de recherche UPnP.</p>';
            }
        }

        document.addEventListener("DOMContentLoaded", () => {
            const initCheck = setInterval(() => {
                if (typeof hasInitializedSpeakers !== 'undefined' && hasInitializedSpeakers) {
                    clearInterval(initCheck);
                    loadServers();
                }
            }, 100);

            document.addEventListener('change', (e) => {
                if (e.target && e.target.classList.contains('speaker-checkbox')) {
                    if (navigationHistory.length === 0) loadServers();
                }
            });

            const searchInput = document.getElementById('dlna-search-input');
            if(searchInput) {
                searchInput.addEventListener('keypress', function (e) {
                    if (e.key === 'Enter') performSearch();
                });
            }
        });
    </script>
</body>
</html>
```
<br>

### `www/dlna.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
	<!-- PWA et Manifest -->
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#121212">

    <!-- Optimisations spécifiques pour iOS (Apple) -->
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoundCork">
    <link rel="apple-touch-icon" href="img/icon-192.png">

    <title>Musique Locale - SoundTouch</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <link rel="stylesheet" href="css/global.css">
    <style>
        .dlna-nav-header { 
            display: flex; 
            align-items: center; 
            justify-content: space-between;
            background-color: var(--bg-elevated); 
            padding: 15px 20px; 
            border-radius: 8px; 
            margin-bottom: 20px; 
        }
        .dlna-path-container { display: flex; align-items: center; gap: 15px; flex: 1;}
        .current-path { font-size: 16px; font-weight: bold; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
        
        .list-content { display: flex; flex-direction: column; gap: 8px; padding-bottom: 20px; }
        
        .dlna-item { 
            display: flex; 
            align-items: center; 
            padding: 10px 15px; 
            background-color: var(--bg-elevated); 
            border-radius: 6px; 
            cursor: pointer; 
            transition: background-color 0.2s; 
        }
        .dlna-item:hover { background-color: var(--bg-highlight); }
        
        .item-icon-wrapper { 
            width: 45px; 
            height: 45px; 
            background-color: #333; 
            border-radius: 4px; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            margin-right: 15px; 
            font-size: 20px; 
            flex-shrink: 0;
            overflow: hidden;
        }
        .item-img { width: 100%; height: 100%; object-fit: cover; }
        .item-details { flex: 1; overflow: hidden; }
        .item-title { font-weight: bold; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 2px;}
        .item-subtitle { font-size: 12px; color: var(--text-subdued); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}

        .status-bar { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background-color: #333; color: white; padding: 12px 24px; border-radius: 500px; font-weight: bold; box-shadow: 0 8px 24px rgba(0,0,0,0.5); z-index: 2000; display: none; transition: opacity 0.3s; }
        .status-success { background-color: var(--spotify-green); color: black; }
        .status-error { background-color: #FA243C; color: white;}
        .status-warning { background-color: #FF9900; color: black;}
    </style>
</head>
<body>

    <div id="status-bar" class="status-bar">Notification</div>

    <div class="main-container">
        <div id="mobile-overlay" class="sidebar-overlay" onclick="toggleMobileMenu()"></div>
        <nav class="sidebar"></nav>

        <main class="main-view">
            
            <div class="top-bar">
                <!-- <div style="display: flex; width: 100%; align-items: center;"> -->
				<div style="display: flex; flex: 1; min-width: 0; align-items: center;">
                    <button class="mobile-menu-btn" onclick="toggleMobileMenu(event)">
                        <i class="fas fa-bars"></i>
                    </button>
                    
                    <div class="search-container" style="margin-left: 10px;">
                        <input type="text" id="search-input" class="search-input" placeholder="Rechercher une musique...">
                        <select id="search-type" class="search-select">
                            <option value="all" selected>Tous</option>
                            <option value="title">Titre</option>
                            <option value="artist">Artiste</option>
                            <option value="album">Album</option>
                        </select>
                        <button class="btn-search" onclick="searchDLNA()">Rechercher</button>
 						<h2>Données locales</h2>
                   </div>
                </div>
                
                <!-- <div class="sources-wrapper" id="sources-wrapper" style="max-width: 150px; width: 20%; margin: 0 15px;"></div> -->
                <div class="remote-wrapper" id="remote-wrapper" style="max-width: 250px; width: 20%; margin: 0 15px;"></div>
            </div>

            <div class="dlna-nav-header">
                <div class="dlna-path-container">
                    <button class="btn-action" id="backBtn" onclick="goBack()" style="width: auto; display: none; padding: 6px 15px;">
                        <i class="fas fa-arrow-left"></i> Retour
                    </button>
                    <h3 id="current-path" class="current-path">Recherche du serveur...</h3>
                </div>
                
                <button class="btn-action" id="btn-repeat" onclick="toggleDLNARepeat()" style="width: auto; padding: 6px 15px;" title="Répéter la file locale">
                    <i class="fas fa-redo"></i>
                </button>
            </div>

            <div class="list-content" id="content-list">
                <div style="text-align: center; color: var(--text-subdued); margin-top: 40px;">
                    <div class="loader" style="margin: 0 auto 15px auto;"></div>
                    Connexion au serveur local (MiniDLNA)...
                </div>
            </div>

        </main>
    </div>

    <footer class="player-bar"></footer>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
	<script src="js/app.js"></script>
    
    <script>
        let currentUdn = null;
        let navigationHistory = [];
        let currentFolderAudioItems = []; 
        let isDlnaRepeatActive = false;
        const rootDlnaName = "Ma Musique";

        async function syncDLNAStatus() {
            if (typeof getSelectedIps !== "function") return; 
            
            const ips = getSelectedIps();
            if (ips.length === 0) return;
            
            try {
                const res = await fetch(`/api/queue/status?ip=${ips[0]}`);
                const data = await res.json();
                
                const btn = document.getElementById('btn-repeat');
                if (btn) {
                    if (data.repeat) {
                        btn.classList.add('btn-action-primary');
                    } else {
                        btn.classList.remove('btn-action-primary');
                    }
                }
            } catch(e) {}
        }

        setTimeout(syncDLNAStatus, 1000);
        setInterval(syncDLNAStatus, 4000);
		
        function showNotification(msg, type = "warning") {
            const statusBar = document.getElementById('status-bar');
            statusBar.innerText = msg;
            statusBar.className = `status-bar status-${type}`;
            statusBar.style.display = 'block';
            setTimeout(() => { statusBar.style.display = 'none'; }, 3000);
        }

		document.addEventListener("DOMContentLoaded", () => {
            const initCheck = setInterval(() => {
                if (typeof hasInitializedSpeakers !== 'undefined' && hasInitializedSpeakers) {
                    clearInterval(initCheck);
                    loadServers();
                }
            }, 100);

            document.addEventListener('change', (e) => {
                if (e.target && e.target.classList.contains('speaker-checkbox')) {
                    if (navigationHistory.length === 0) {
                        loadServers();
                    }
                }
            });

            const searchInput = document.getElementById('search-input');
            if (searchInput) {
                searchInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') searchDLNA();
                });
            }
        });

        async function loadServers() {
            currentUdn = null; 
            navigationHistory = [];
            document.getElementById('backBtn').style.display = 'none';
            document.getElementById('current-path').innerText = rootDlnaName;
            
            try {
                const response = await fetch('/api/dlna/servers');
                const servers = await response.json();
                
                const dockerServer = servers.find(s => s.name.toLowerCase().includes('soundcork') || s.name.toLowerCase().includes('minidlna'));
                
                if (dockerServer) {
                    currentUdn = dockerServer.udn;
                    const rootResponse = await fetch(`/api/dlna/browse?udn=${encodeURIComponent(dockerServer.udn)}&id=0`);
                    const rootItems = await rootResponse.json();
                    
                    if (rootItems.error) throw new Error(rootItems.error);
                    
                    let musicFolder = null;
                    if (Array.isArray(rootItems)) {
                        musicFolder = rootItems.find(i => i.title.toLowerCase() === 'music' || i.title.toLowerCase() === 'musique');
                    }
                    
                    if (musicFolder) {
                        browseFolder(dockerServer.udn, musicFolder.id, rootDlnaName);
                    } else {
                        browseFolder(dockerServer.udn, '0', rootDlnaName);
                    }
                } else {
                    document.getElementById('content-list').innerHTML = '<p style="text-align:center; margin-top:40px; color:#FA243C;">Serveur Media introuvable.<br><small style="color:var(--text-subdued)">Patientez 30s s\'il vient d\'être redémarré.</small></p>';
                }
            } catch (e) {
                console.error("Erreur serveur :", e);
                document.getElementById('content-list').innerHTML = '<p style="text-align:center; color:#FA243C; margin-top:40px;">Erreur de connexion au serveur DLNA.</p>';
            }
        }

        async function browseFolder(udn, objectId, title) {
            currentUdn = udn;
            navigationHistory.push({id: objectId, title: title});
            
            document.getElementById('backBtn').style.display = (navigationHistory.length > 1) ? 'block' : 'none';
            document.getElementById('current-path').innerText = title;
            document.getElementById('content-list').innerHTML = '<div style="text-align: center; color: var(--text-subdued); margin-top: 40px;"><div class="loader" style="margin: 0 auto 15px auto;"></div>Chargement du dossier...</div>';

            try {
                const response = await fetch(`/api/dlna/browse?udn=${encodeURIComponent(udn)}&id=${encodeURIComponent(objectId)}`);
                const items = await response.json();
                
                if (items.error) {
                    document.getElementById('content-list').innerHTML = `<p style="text-align:center; color:#FA243C; margin-top:40px;"><i class="fas fa-exclamation-triangle"></i> Impossible d'ouvrir ce dossier : ${items.error}</p>`;
                    return;
                }
                
                if (!Array.isArray(items) || items.length === 0) {
                    document.getElementById('content-list').innerHTML = `<p style="text-align:center; color:var(--text-subdued); margin-top:40px;">Ce dossier est vide.</p>`;
                    return;
                }

                currentFolderAudioItems = items.filter(i => i.type === 'audio');
                let html = '';

                items.forEach((item) => {
                    if (item.type === 'folder') {
                        html += `
                            <div class="dlna-item" onclick="browseFolder('${udn}', '${item.id}', '${item.title.replace(/'/g, "\\'")}')">
                                <div class="item-icon-wrapper" style="background-color: transparent;"><i class="fas fa-folder" style="color: #FFC107; font-size: 28px;"></i></div>
                                <div class="item-details">
                                    <div class="item-title">${item.title}</div>
                                </div>
                                <i class="fas fa-chevron-right" style="color: var(--text-subdued);"></i>
                            </div>`;
                    } else {
                        const audioIndex = currentFolderAudioItems.findIndex(i => i.id === item.id);
                        const coverHtml = item.cover 
                            ? `<img src="${item.cover}" class="item-img" onerror="this.style.display='none'">` 
                            : `<i class="fas fa-music" style="color: var(--text-subdued);"></i>`;
                            
                        html += `
                            <div class="dlna-item" onclick="sendPlaylistToServer(${audioIndex})">
                                <div class="item-icon-wrapper">${coverHtml}</div>
                                <div class="item-details">
                                    <div class="item-title">${item.title}</div>
                                    <div class="item-subtitle">${item.artist || 'Artiste inconnu'}</div>
                                </div>
                            </div>`;
                    }
                });
                document.getElementById('content-list').innerHTML = html;

            } catch (e) {
                console.error("Erreur de navigation :", e);
                document.getElementById('content-list').innerHTML = `<p style="text-align:center; color:#FA243C; margin-top:40px;"><i class="fas fa-exclamation-triangle"></i> Erreur lors de la lecture du dossier.</p>`;
            }
        }

        async function searchDLNA() {
            const query = document.getElementById('search-input').value.trim();
            const searchType = document.getElementById('search-type').value;
            
            if (!query) {
                return loadServers();
            }

            if (!currentUdn) {
                showNotification("Aucun serveur DLNA connecté.", "error");
                return;
            }

            navigationHistory.push({ id: 'search', title: `Résultats pour "${query}"` });
            
            document.getElementById('backBtn').style.display = 'block';
            document.getElementById('current-path').innerText = `Résultats pour "${query}"`;
            document.getElementById('content-list').innerHTML = '<div style="text-align: center; color: var(--text-subdued); margin-top: 40px;"><div class="loader" style="margin: 0 auto 15px auto;"></div>Recherche en cours...</div>';

            try {
                const response = await fetch('/api/dlna/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ udn: currentUdn, query: query, type: searchType })
                });
                
                const items = await response.json();
                
                if (items.error) {
                    document.getElementById('content-list').innerHTML = `<p style="text-align:center; color:#FA243C; margin-top:40px;"><i class="fas fa-exclamation-triangle"></i> Erreur : ${items.error}</p>`;
                    return;
                }
                
                if (!Array.isArray(items) || items.length === 0) {
                    document.getElementById('content-list').innerHTML = `<p style="text-align:center; color:var(--text-subdued); margin-top:40px;">Aucun résultat trouvé pour "${query}".</p>`;
                    return;
                }

                currentFolderAudioItems = items;
                let html = '';

                items.forEach((item, index) => {
                    const coverHtml = item.cover 
                        ? `<img src="${item.cover}" class="item-img" onerror="this.style.display='none'">` 
                        : `<i class="fas fa-music" style="color: var(--text-subdued);"></i>`;
                        
                    html += `
                        <div class="dlna-item" onclick="sendPlaylistToServer(${index})">
                            <div class="item-icon-wrapper">${coverHtml}</div>
                            <div class="item-details">
                                <div class="item-title">${item.title}</div>
                                <div class="item-subtitle">${item.artist || 'Artiste inconnu'} ${item.album ? '• ' + item.album : ''}</div>
                            </div>
                        </div>`;
                });
                document.getElementById('content-list').innerHTML = html;

            } catch (e) {
                console.error("Erreur de recherche :", e);
                document.getElementById('content-list').innerHTML = `<p style="text-align:center; color:#FA243C; margin-top:40px;"><i class="fas fa-exclamation-triangle"></i> Erreur de communication avec le serveur.</p>`;
            }
        }

        function goBack() {
            if (navigationHistory.length > 1) {
                navigationHistory.pop(); 
                const parent = navigationHistory.pop(); 
                
                if (parent.id === 'search') {
                    loadServers();
                } else {
                    browseFolder(currentUdn, parent.id, parent.title);
                }
            }
        }

        async function sendPlaylistToServer(startIndex) {
            const ips = getSelectedIps();
            if (ips.length === 0) return showNotification("Sélectionnez au moins une enceinte active.", "error");
            
            showNotification("⏳ Préparation de la file d'attente...", "warning");
            
            try {
                await fetch('/api/queue/play', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ips: ips, tracks: currentFolderAudioItems, index: startIndex })
                });
                showNotification("✅ Lecture lancée !", "success");
                
                setTimeout(() => { if(typeof fetchState === 'function') fetchState(); }, 1500);
            } catch (e) {
                showNotification("❌ Erreur réseau.", "error");
            }
        }

        async function toggleDLNARepeat() {
            const ips = getSelectedIps();
            if (ips.length === 0) return showNotification("Sélectionnez une enceinte pour piloter la file.", "error");
            
            try {
                const res = await fetch('/api/queue/control', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ip: ips[0], action: 'toggle_repeat' })
                });
                const data = await res.json();
                
                const btn = document.getElementById('btn-repeat');
                if (data.repeat) {
                    btn.classList.add('btn-action-primary');
                    showNotification("🔁 Répétition de la file activée", "success");
                } else {
                    btn.classList.remove('btn-action-primary');
                    showNotification("➡️ Répétition désactivée", "warning");
                }
            } catch(e) {
                console.error("Erreur toggle repeat DLNA:", e);
            }
        }
    </script>
</body>
</html>
```
<br>

### `www/index.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Démarrage...</title>
    <script>
        // Fonction asynchrone pour lire la configuration et rediriger
        async function initApp() {
            try {
                // Tente de récupérer le fichier config.json
                const response = await fetch('config.json');
                
                if (!response.ok) {
                    throw new Error("Fichier de configuration introuvable.");
                }

                const config = await response.json();

                // Récupère la page cible, ou utilise 'radios.html' par sécurité
                const targetPage = config.defaultPage || 'radios.html';

                // Redirige vers la page choisie
                window.location.replace(targetPage);

            } catch (error) {
                console.error("Erreur :", error);
                // En cas de problème de chargement, on lance les radios par défaut
                window.location.replace('radios.html');
            }
        }

        // Lancer la fonction dès que la page s'ouvre
        window.onload = initApp;
    </script>
    <style>
        /* Un petit style basique pour patienter pendant la milliseconde de chargement */
        body {
            background-color: #121212;
            color: #ffffff;
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
    </style>
</head>
<body>
    <p>Chargement de l'interface...</p>
</body>
</html>
```
<br>

### `www/js/app.js`

```javascript
let globalData = { speakers: {}, presets: {}, radios: [] };
let hasInitializedSpeakers = false;
let isFetchingState = false;

let selectedSpeakersOrder = [];
let isMultiSelectMode = false;
let longPressTimer;
let isPresetRecordMode = false;
const LONG_PRESS_DURATION = 500;

function handleSpeakerTouchStart(event, ip) {
    const spk = globalData.speakers[ip];
    if (!spk || (spk.state !== 'ON' && spk.state !== 'STANDBY')) return;

    longPressTimer = setTimeout(() => {
        isMultiSelectMode = true;
        if (navigator.vibrate) navigator.vibrate(50); 
        toggleSpeakerSelection(ip);
    }, LONG_PRESS_DURATION);
}

function handleSpeakerTouchEnd(event) {
    clearTimeout(longPressTimer);
}

function handleSpeakerClick(event, ip) {
    clearTimeout(longPressTimer);
    
    const spk = globalData.speakers[ip];
    if (!spk || (spk.state !== 'ON' && spk.state !== 'STANDBY')) return;

    const isMultiModifierPressed = event.ctrlKey || event.metaKey;

    if (isMultiModifierPressed || isMultiSelectMode) {
        isMultiSelectMode = true;
        toggleSpeakerSelection(ip);
    } else {
        clearAllSpeakerSelections();
        selectSpeaker(ip);
    }
}

function toggleSpeakerSelection(ip) {
    const chk = document.getElementById(`chk-${ip}`);
    if (chk && !chk.disabled) {
        chk.checked = !chk.checked;
        chk.closest('.speaker-item').classList.toggle('selected', chk.checked);
        
        if (chk.checked) {
            if (!selectedSpeakersOrder.includes(ip)) selectedSpeakersOrder.push(ip);
        } else {
            selectedSpeakersOrder = selectedSpeakersOrder.filter(item => item !== ip);
        }
    }
    
    const selectedCount = selectedSpeakersOrder.length;
    if (selectedCount <= 1) {
        isMultiSelectMode = false;
    }
    
    updateSidebarUI();
    updatePlayerInfo();
    routePageUpdates(); // <-- FIX : Force la page centrale (now.html) à se rafraîchir
}

function clearAllSpeakerSelections() {
    document.querySelectorAll('.speaker-checkbox').forEach(chk => {
        chk.checked = false;
        const item = chk.closest('.speaker-item');
        if(item) item.classList.remove('selected');
    });
    selectedSpeakersOrder = [];
    isMultiSelectMode = false;
    updateSidebarUI();
    updatePlayerInfo(); // <-- FIX : Vide la barre de lecture en bas
    routePageUpdates(); // <-- FIX : Vide la page centrale
}

function selectSpeaker(ip) {
    const chk = document.getElementById(`chk-${ip}`);
    if (chk && !chk.disabled) {
        chk.checked = true;
        const item = chk.closest('.speaker-item');
        if(item) item.classList.add('selected');
        
        if (!selectedSpeakersOrder.includes(ip)) selectedSpeakersOrder.push(ip);
    }
    updateSidebarUI();
    updatePlayerInfo();
    routePageUpdates(); // <-- FIX : Force la page centrale (now.html) à se rafraîchir
}

function exitMultiSelectMode() {
    isMultiSelectMode = false;
    const previousMaster = selectedSpeakersOrder.length > 0 ? selectedSpeakersOrder[0] : null;
    clearAllSpeakerSelections();
    if (previousMaster) {
        selectSpeaker(previousMaster);
    }
    updateSidebarUI();
}

function updateSidebarUI() {	
    const sidebar = document.getElementById('speakers-list');
    const exitBtn = document.getElementById('exit-multi-select');
    
    if (!sidebar) return;

    if (isMultiSelectMode) {
        sidebar.classList.add('multi-select-active');
        if (exitBtn) exitBtn.style.display = 'inline-block';
    } else {
        sidebar.classList.remove('multi-select-active');
        if (exitBtn) exitBtn.style.display = 'none';
    }
    
    document.querySelectorAll('.master-badge').forEach(el => el.remove());
    
    const speakersKeys = Object.keys(globalData.speakers);
    for (const ip of speakersKeys) {
        const spk = globalData.speakers[ip];
        
        const isIntendedMaster = (isMultiSelectMode && selectedSpeakersOrder.length > 0 && selectedSpeakersOrder[0] === ip);
        const isActualMaster = (spk.is_zone_master === true);
        
        if (isIntendedMaster || isActualMaster) {
            const spkItem = document.getElementById(`chk-${ip}`);
            if (spkItem) {
                const nameDiv = spkItem.closest('.speaker-item').querySelector('.speaker-name');
                if (nameDiv && !nameDiv.querySelector('.master-badge')) {
                    nameDiv.innerHTML += ' <span class="master-badge" style="background:var(--spotify-green); color:black; font-size:10px; padding:2px 5px; border-radius:4px; margin-left:5px; font-weight:bold; vertical-align: middle;" title="Enceinte Maître">Maître</span>';
                }
            }
        }
    }
}

function mergeSpeakerData(newSpeakers) {
    for (const existingIp in globalData.speakers) {
        if (!newSpeakers[existingIp]) {
            delete globalData.speakers[existingIp];
        }
    }

    for (const ip in newSpeakers) {
        const newSpk = newSpeakers[ip];
        
        if (newSpk.is_stereo_slave) {
            if (globalData.speakers[ip]) delete globalData.speakers[ip];
            continue;
        }

        if (newSpk.source === 'RADIO_BROWSER' || newSpk.source === 'LOCAL_INTERNET_RADIO') {
            if (!newSpk.cover || newSpk.cover === 'FA_ICON' || newSpk.cover === 'SHOW_DEFAULT_IMAGE') {
                const matchName = newSpk.track || newSpk.playlist || "";
                
                if (globalData.radios && globalData.radios.length > 0 && matchName) {
                    const matchedRadio = globalData.radios.find(r => 
                        matchName.toLowerCase().includes(r.name.toLowerCase()) || 
                        r.name.toLowerCase().includes(matchName.toLowerCase())
                    );
                    if (matchedRadio && matchedRadio.logo) {
                        newSpk.cover = matchedRadio.logo;
                    } else {
                        newSpk.cover = 'FA_ICON';
                    }
                } else {
                    newSpk.cover = 'FA_ICON';
                }
            }
        }

        const oldSpk = globalData.speakers[ip] || {};

        if (newSpk.time_position !== oldSpk.time_position || newSpk.playStatus !== oldSpk.playStatus) {
            newSpk.local_time_anchor = Date.now(); 
            newSpk.local_time_base = parseInt(newSpk.time_position || 0);
        } else {
            newSpk.local_time_anchor = oldSpk.local_time_anchor || Date.now();
            newSpk.local_time_base = oldSpk.local_time_base || 0;
        }
        
        globalData.speakers[ip] = newSpk;
    }
}

const socket = io();

socket.on('bose_update', function(data) {
    mergeSpeakerData(data.speakers);
    renderSidebarDynamicElements();
    updatePlayerInfo();
    routePageUpdates();
});

document.addEventListener("DOMContentLoaded", async () => {
    await loadComponent("mobile-overlay", "components/sidebar.html", ".sidebar");
    await loadComponent(null, "components/footer.html", ".player-bar");
    await loadComponent(null, "components/remotesimple.svg", "#remote-wrapper");
    
    if (document.querySelector("#sources-wrapper")) {
        await loadComponent(null, "components/sources.svg", "#sources-wrapper");
        updateSourcesSVG(); 
    }

    highlightActiveNav();
    fetchState(); 
    setupPageListeners();
});

async function loadComponent(overlayId, fileUrl, targetSelector) {
    const target = document.querySelector(targetSelector);
    if (!target) return;
    try {
        const response = await fetch(fileUrl);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        target.innerHTML = await response.text();
    } catch (e) {
        console.error(`Erreur chargement ${fileUrl}:`, e);
    }
}

function highlightActiveNav() {
    const page = window.location.pathname.split("/").pop().replace(".html", "") || 'index';
    const activeLink = document.querySelector(`.id-nav-${page}`);
    if (activeLink) activeLink.classList.add("active");
}

function toggleMobileMenu(event) {
    if (event) event.stopPropagation();
    document.querySelector('.sidebar').classList.toggle('active');
    document.getElementById('mobile-overlay').classList.toggle('active');
}

function setupPageListeners() {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') searchRadios();
        });
    }
}

function getSelectedIps() {
    return selectedSpeakersOrder;
}

async function fetchState() {
    if (isFetchingState) return;
    isFetchingState = true;
    try {
        const response = await fetch('/api/data');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const newData = await response.json();
        
        globalData.presets = newData.presets;
        globalData.radios = newData.radios;
        
        mergeSpeakerData(newData.speakers);
        
        renderSidebarDynamicElements();
        updatePlayerInfo();
        routePageUpdates();
    } catch (error) {
    } finally {
        isFetchingState = false;
    }
}

function routePageUpdates() {
    const page = window.location.pathname.split("/").pop();
    if (page === "index.html" || page === "") {
        const searchInput = document.getElementById('search-input');
        if (searchInput && searchInput.value.trim() === '') renderHomeGrid();
    } else if (page === "now.html") {
        if (typeof onStateUpdated === "function") {
            onStateUpdated();
        }
    }
}

function renderSidebarDynamicElements() {
    const speakersDiv = document.getElementById('speakers-list');
    if (!speakersDiv) return;

    let currentlySelected = getSelectedIps();
    const speakersKeys = Object.keys(globalData.speakers);
    let htmlSpeakers = '';
    
    if (!hasInitializedSpeakers && speakersKeys.length > 0) {
        let onSpeaker = speakersKeys.find(ip => globalData.speakers[ip].state === 'ON');
        let standbySpeaker = speakersKeys.find(ip => globalData.speakers[ip].state === 'STANDBY');
        let defaultIp = onSpeaker || standbySpeaker;
        if (defaultIp) {
            selectedSpeakersOrder = [defaultIp];
            currentlySelected = selectedSpeakersOrder;
        }
    }

    let validSelections = [];

    for (const ip of speakersKeys) {
        const data = globalData.speakers[ip];
        
        if (data.is_stereo_slave) continue;

        let statusClass = 'status-red'; 
        let isDisabled = true; 

        if (data.state === 'ON') {
            statusClass = 'status-green';
            isDisabled = false; 
        } else if (data.state === 'STANDBY') {
            statusClass = 'status-orange';
            isDisabled = false; 
        }

        let isChecked = currentlySelected.includes(ip) ? 'checked' : '';
        if (isDisabled) isChecked = '';

        if (isChecked === 'checked') validSelections.push(ip);

        let selectedClass = (isChecked === 'checked') ? 'selected' : '';
        let disabledAttr = isDisabled ? 'disabled' : '';
        let disabledStyle = isDisabled ? 'style="opacity: 0.5; cursor: not-allowed;"' : '';

        // --- GESTION DE LA BATTERIE ET DU SECTEUR ---
        let batteryHtml = '';
        if (data.battery_capable && data.battery_percent !== undefined) {
            let pct = parseInt(data.battery_percent);
            let iconClass = "fa-battery-full";
            let color = "var(--text-subdued)";
            
            if (data.running_on_battery === false) {
                iconClass = "fa-plug";
                color = "var(--spotify-green)";
            } else {
                if (pct <= 15) { iconClass = "fa-battery-empty"; color = "#FA243C"; }
                else if (pct <= 35) { iconClass = "fa-battery-quarter"; }
                else if (pct <= 65) { iconClass = "fa-battery-half"; }
                else if (pct <= 85) { iconClass = "fa-battery-three-quarters"; }
            }
            
            batteryHtml = `
            <div style="color: ${color}; font-size: 11px; display: flex; align-items: center; gap: 4px; padding-left: 5px; flex-shrink: 0;" title="${data.running_on_battery === false ? 'Sur secteur' : 'Sur batterie'}">
                <i class="fas ${iconClass}"></i> ${pct}%
            </div>`;
        }

        htmlSpeakers += `
            <div class="speaker-item ${selectedClass}" ${disabledStyle}
                 onclick="handleSpeakerClick(event, '${ip}')"
                 ontouchstart="handleSpeakerTouchStart(event, '${ip}')"
                 ontouchend="handleSpeakerTouchEnd(event)"
                 ontouchcancel="handleSpeakerTouchEnd(event)"
                 ontouchmove="handleSpeakerTouchEnd(event)">
                
                <div style="display:flex; align-items:center; gap:10px; flex: 1; min-width: 0;">
                    <div class="status-indicator ${statusClass}"></div>
                    <div class="speaker-name">${data.name || ip}</div>
                    ${batteryHtml}
                </div>
                
                <input type="checkbox" class="speaker-checkbox" id="chk-${ip}" value="${ip}" ${isChecked} ${disabledAttr} onclick="event.stopPropagation(); toggleSpeakerSelection('${ip}')">
                
                <div class="multi-check-indicator">
                    <i class="fas fa-check"></i>
                </div>
            </div>`;
    }
    
    selectedSpeakersOrder = selectedSpeakersOrder.filter(ip => validSelections.includes(ip));
    validSelections.forEach(ip => {
        if (!selectedSpeakersOrder.includes(ip)) selectedSpeakersOrder.push(ip);
    });

    speakersDiv.innerHTML = htmlSpeakers;
    
    updateSidebarUI();

    if (!hasInitializedSpeakers && speakersKeys.length > 0) {
        hasInitializedSpeakers = true;
        setTimeout(updatePlayerInfo, 100); 
    }

    const presetsDiv = document.getElementById('presets-list');
    if (presetsDiv) {
        let htmlPresets = '';
        for (let i = 1; i <= 6; i++) {
            let presetName = (globalData.presets && globalData.presets[i]) ? globalData.presets[i] : "";
            if (presetName) htmlPresets += `<div class="nav-item" onclick="playPreset('${i}')"><i class="fas fa-bookmark"></i> ${i}. ${presetName}</div>`;
        }
        presetsDiv.innerHTML = htmlPresets || '<div class="nav-item">Aucun preset</div>';
    }
    
    for (let i = 1; i <= 6; i++) {
        let presetName = (globalData.presets && globalData.presets[i]) ? globalData.presets[i] : "";
        const svgTextEl = document.getElementById(`preset-text-${i}`);
        if (svgTextEl) {
            svgTextEl.textContent = presetName.length > 14 ? presetName.substring(0, 13) + "_" : presetName;
        }
    }
}

function formatTime(seconds) {
    if (isNaN(seconds)) return "--:--";
    let m = Math.floor(seconds / 60);
    let s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
}

function updateSourcesSVG() {
    const ips = getSelectedIps();
    if (ips.length === 0) return;
    const spk = globalData.speakers[ips[0]];
    if (!spk) return;

    const supported = spk.supported_sources || [];
    
    const sourceMap = {
        'aux': 'AUX',
        'hdmi': 'HDMI_1',
        'tv': 'TV',
        'bt': 'BLUETOOTH'
    };

    for (const [svgId, srcName] of Object.entries(sourceMap)) {
        const el = document.getElementById(svgId);
        if (el) {
            if (supported.includes(srcName)) {
                el.style.opacity = "1";
                el.style.pointerEvents = "auto";
            } else {
                el.style.opacity = "0.3";
                el.style.pointerEvents = "none";
            }
        }
    }
}

function updatePlayerInfo() {
    const ips = getSelectedIps();
    if (ips.length === 0) {
        // Nettoie l'affichage si aucune enceinte
        const trackEl = document.getElementById('player-track');
        const artistEl = document.getElementById('player-artist');
        const albumEl = document.getElementById('player-album');
        if (trackEl) trackEl.innerText = "Sélectionnez une enceinte";
        if (artistEl) artistEl.innerText = "-";
        if (albumEl) albumEl.innerText = "-";
        const coverDiv = document.getElementById('player-cover');
        if (coverDiv) {
            coverDiv.style.backgroundImage = 'none';
            coverDiv.innerHTML = `<i class="fas fa-music" style="color:#555;"></i>`;
        }
        return;
    }
    
    const spk = globalData.speakers[ips[0]];
    if (!spk) return;

    updateSourcesSVG();

    const track = spk.track || spk.playlist || "Prêt";
    const artist = spk.artist || spk.source || "Artiste inconnu";
    const album = spk.album || ""; 
    
    const trackEl = document.getElementById('player-track');
    const artistEl = document.getElementById('player-artist');
    const albumEl = document.getElementById('player-album');
    
    if (trackEl) trackEl.innerText = track;
    if (artistEl) artistEl.innerText = artist;
    if (albumEl) {
        albumEl.innerText = album;
        albumEl.style.display = album ? 'block' : 'none'; 
    }
    
    let finalCoverUrl = spk.cover;
    if (finalCoverUrl && finalCoverUrl !== 'FA_ICON' && finalCoverUrl !== 'SHOW_DEFAULT_IMAGE') {
        if (!finalCoverUrl.includes('cb=')) {
            const separator = finalCoverUrl.includes('?') ? '&' : '?';
            finalCoverUrl += `${separator}cb=${encodeURIComponent(track)}`;
        }
    }

    const coverDiv = document.getElementById('player-cover');
    if (coverDiv) {
        if (finalCoverUrl && finalCoverUrl !== 'FA_ICON' && finalCoverUrl !== 'SHOW_DEFAULT_IMAGE') {
            coverDiv.style.backgroundImage = `url('${finalCoverUrl}')`;
            coverDiv.style.backgroundSize = 'contain'; 
            coverDiv.style.backgroundPosition = 'center';
            coverDiv.style.backgroundRepeat = 'no-repeat';
            coverDiv.innerHTML = '';
        } else {
            coverDiv.style.backgroundImage = 'none';
            const iconClass = (spk.source === 'LOCAL_INTERNET_RADIO' || spk.source === 'RADIO_BROWSER') 
                              ? 'fas fa-broadcast-tower' 
                              : 'fas fa-music';
            coverDiv.innerHTML = `<i class="${iconClass}" style="color:#555;"></i>`;
        }
    }

    const playIcon = document.getElementById('play-icon');
    if (playIcon) playIcon.className = spk.playStatus === 'PLAY_STATE' ? 'fas fa-pause' : 'fas fa-play';

    const volumeSlider = document.getElementById('volume-slider'); 
    if (volumeSlider && spk.volume !== undefined) {
        if (document.activeElement !== volumeSlider) {
            volumeSlider.value = spk.volume;
        }
    }

    if ('mediaSession' in navigator) {
        let artworkArray = [];
        if (finalCoverUrl && finalCoverUrl !== 'FA_ICON' && finalCoverUrl !== 'SHOW_DEFAULT_IMAGE') {
            artworkArray = [{ src: finalCoverUrl, sizes: '512x512', type: 'image/jpeg' }];
        }
        
        navigator.mediaSession.metadata = new MediaMetadata({ 
            title: track, 
            artist: artist, 
            artwork: artworkArray 
        });
        navigator.mediaSession.setActionHandler('play', () => sendCommand('PLAY_PAUSE'));
        navigator.mediaSession.setActionHandler('pause', () => sendCommand('PLAY_PAUSE'));
        navigator.mediaSession.setActionHandler('previoustrack', () => sendCommand('PREV_TRACK'));
        navigator.mediaSession.setActionHandler('nexttrack', () => sendCommand('NEXT_TRACK'));
    }   
}

setInterval(() => {
    const ips = getSelectedIps();
    if (ips.length === 0) return;
    const spk = globalData.speakers[ips[0]];
    if (!spk) return;

    const progressFill = document.getElementById('progress-bar-fill'); 
    const timeCurrent = document.getElementById('time-current');       
    const timeTotal = document.getElementById('time-total');           

    if (spk.time_total && parseInt(spk.time_total) > 0) {
        let pos = spk.local_time_base || 0;
        if (spk.playStatus === 'PLAY_STATE') {
            pos += (Date.now() - spk.local_time_anchor) / 1000;
        }
        
        let tot = parseInt(spk.time_total);
        if (pos > tot) pos = tot;

        if (progressFill) progressFill.style.width = `${(pos / tot) * 100}%`;
        if (timeCurrent) timeCurrent.innerText = formatTime(pos);
        if (timeTotal) timeTotal.innerText = formatTime(tot);
    } else {
        if (progressFill) progressFill.style.width = `0%`;
        if (timeCurrent) timeCurrent.innerText = "--:--";
        if (timeTotal) timeTotal.innerText = "--:--";
    }
}, 250);

async function sendCommand(keyName, keyState = 'both') {
    const ips = getSelectedIps();
    if (ips.length === 0) return alert("Sélectionnez au moins une enceinte !");
    
    await fetch('/api/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ips: ips, key: keyName, state: keyState })
    });
}

// Fonction à appeler au clic sur ton nouveau bouton "Enregistrer Preset" (ex bt/aux)
function togglePresetRecordMode() {
    isPresetRecordMode = !isPresetRecordMode;
    
    // (Optionnel) Retour visuel sur le bouton pour indiquer que le mode est actif
    const btn = document.querySelector('[onclick*="togglePresetRecordMode"]');
    if (btn) {
        if (isPresetRecordMode) {
            btn.style.fill = "#FA243C"; // Rouge
            btn.style.opacity = "0.8";
        } else {
            btn.style.fill = ""; // Réinitialise
            btn.style.opacity = "0.3";
        }
    }
}

async function playPreset(presetId) {
    const ips = getSelectedIps();
    if (ips.length === 0) return alert("Sélectionnez au moins une enceinte !");

    if (isPresetRecordMode) {
        // Mode ENREGISTREMENT : Envoi de l'état 'press'
        await fetch('/api/key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ips: ips, key: 'PRESET_' + presetId, state: 'press' })
        });
        
        // Désactivation du mode après l'enregistrement
        togglePresetRecordMode();
        
        // Rafraîchissement forcé pour mettre à jour les noms des presets
        setTimeout(() => fetch('/api/poll', {method: 'POST'}), 1000);
        
    } else {
        // Mode LECTURE NORMAL
        await fetch('/api/play_preset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ips, preset_id: presetId })
        });
    }
}

async function createZone() {
    const ips = getSelectedIps();
    if (ips.length < 2) {
        alert("Sélectionnez au moins 2 enceintes pour créer une zone !");
        return;
    }
    try {
        const response = await fetch('/api/create_zone', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ips: ips })
        });
        const result = await response.json();
        if(result.status === 'success') {
            const masterIp = ips[0];
            const masterName = globalData.speakers[masterIp] ? globalData.speakers[masterIp].name : masterIp;
            alert(`Zone multi-room créée avec succès !\nL'enceinte maître est : ${masterName}`);
        } else {
            alert("Erreur: " + (result.message || "Impossible de grouper."));
        }
    } catch (e) {
        console.error("Erreur groupe :", e);
    }
}

async function createStereoPair() {
    const ips = getSelectedIps();
    if (ips.length !== 2) {
        alert("Pour l'option Stéréo, vous devez sélectionner EXACTEMENT 2 enceintes SoundTouch 10 !");
        return;
    }
    const groupName = prompt("Saisissez un nom pour cette Paire Stéréo (Ex: Salon) :", "Paire Stéréo");
    if (!groupName) return;
    
    try {
        const response = await fetch('/api/create_stereo', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ master_ip: ips[0], slave_ip: ips[1], name: groupName })
        });
        const result = await response.json();
        if (result.status === 'success') {
            alert("Paire stéréo créée avec succès ! L'enceinte Maître sera la Gauche (L).");
            setTimeout(fetchState, 2000);
        } else {
            alert("Erreur: " + (result.message || "Impossible de créer la paire."));
        }
    } catch (e) {
        console.error("Erreur création stéréo :", e);
    }
}

async function removeStereoPair() {
    const ips = getSelectedIps();
    if (ips.length === 0) {
        alert("Sélectionnez la paire stéréo (Maître) que vous souhaitez séparer !");
        return;
    }
    
    if (!confirm("Voulez-vous vraiment séparer cette paire stéréo ?")) return;
    
    try {
        const response = await fetch('/api/remove_stereo', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ip: ips[0] })
        });
        const result = await response.json();
        if (result.status === 'success') {
            alert("Paire stéréo séparée ! (L'esclave va redémarrer et réapparaître d'ici quelques instants).");
            setTimeout(fetchState, 3000);
        }
    } catch (e) {
        console.error("Erreur suppression stéréo :", e);
    }
}

function renderHomeGrid() {
    const grid = document.getElementById('main-grid');
    if (!grid) return; 

    document.getElementById('main-title').innerText = "Vos Radios Favorites";
    if (!globalData.radios || globalData.radios.length === 0) {
        grid.innerHTML = '<p style="color:var(--text-subdued)">Vous n\'avez pas encore ajouté de radios favorites.</p>';
        return;
    }

    grid.innerHTML = globalData.radios.map(radio => {
        const cleanName = radio.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        let visualHtml = '<i class="fas fa-broadcast-tower" style="font-size: 35px; color: #888;"></i>';
        if (radio.logo && radio.logo !== 'FA_ICON') {
            visualHtml = `<img src="${radio.logo}" alt="${cleanName}" style="width: 100%; height: 100%; border-radius: 8px; object-fit: contain;">`;
        }

        return `
            <div class="card">
                <div class="card-icon" onclick="playRadio('${radio.uuid}', '${cleanName}')" title="Lancer" style="cursor: pointer; display: flex; align-items: center; justify-content: center; width: 100%; height: 70px; margin-bottom: 10px;">
                    ${visualHtml}
                </div>
                <div class="card-title" title="${radio.name}">${radio.name}</div>
                <div class="card-subtitle">Radio Web</div>
                <div class="card-actions">
                    <button class="btn-card btn-card-play" onclick="playRadio('${radio.uuid}', '${cleanName}')">▶ Lancer</button>
                    <button class="btn-card btn-card-add" style="border-color: #FA243C; color: #FA243C;" onclick="removeRadio('${radio.uuid}')" title="Supprimer"><i class="fas fa-trash"></i></button>
                </div>
            </div>`;
    }).join('');
}

async function changeVolume(volValue) {
    const ips = getSelectedIps();
    if (ips.length === 0) return;
    
    try {
        await fetch('/api/volume', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ips: ips, volume: parseInt(volValue) })
        });
    } catch (e) {
        console.error("Erreur lors de la modification du volume :", e);
    }
}

async function forcePollAll(event) {
    let icon = null;
    if (event && event.currentTarget) {
        icon = event.currentTarget.querySelector('i');
        if (icon) icon.classList.add('fa-spin');
    }

    try {
        await fetch('/api/poll', { method: 'POST' });
        setTimeout(fetchState, 1000); 
    } catch (e) {
        console.error("Erreur de polling forcé", e);
    } finally {
        if (icon) {
            setTimeout(() => icon.classList.remove('fa-spin'), 1500);
        }
    }
}

async function changeSource(source) {
    const ips = getSelectedIps();
    if (ips.length === 0) {
        if (typeof showNotification === 'function') showNotification("Sélectionnez une enceinte !", "error");
        return;
    }

    if (typeof showNotification === 'function') showNotification(`Basculement sur ${source}...`, "warning");
    try {
        const response = await fetch('/api/select_source', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ip: ips[0], source: source })
        });
        if (response.ok) {
            if (typeof showNotification === 'function') showNotification(`✅ Source ${source} active`, "success");
            setTimeout(fetchState, 1500);
        } else {
            if (typeof showNotification === 'function') showNotification("❌ Erreur de basculement", "error");
        }
    } catch (e) {
        if (typeof showNotification === 'function') showNotification("❌ Erreur réseau", "error");
    }
}


```
<br>

### `www/js/player.js`

```javascript
// --- CONFIGURATION DU SERVEUR ---
const SERVER_URL = "http://192.168.1.116:4533";
const API_USER = "pi";
const API_PASS = "pi";

// Base commune pour toutes les requêtes
const AUTH_PARAMS = `u=${API_USER}&p=${API_PASS}&v=1.16.1&c=web&f=json`;

// Variables globales pour gérer la navigation et la lecture en continu
let historyStack = [];
let currentPlaylist = [];
let currentTrackIndex = -1;
let currentCoverUrl = "";

// Image de secours propre
const FALLBACK_IMG = "data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Crect width='100' height='100' fill='%23333'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%23777' font-size='20'%3E%E2%99%AB%3C/text%3E%3C/svg%3E";

const contentDiv = document.getElementById('content');
const pageTitle = document.getElementById('page-title');
const btnBack = document.getElementById('btn-back');
const audioPlayer = document.getElementById('audio-player');

// NOUVEAU : Éléments du "Now Playing" visuel
const npCover = document.getElementById('now-playing-cover');
const npTitle = document.getElementById('now-playing-title');
const npArtist = document.getElementById('now-playing-artist');

// Formate les secondes en MM:SS
function formatTime(seconds) {
    if (!seconds) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
}

function updateBackButton() {
    btnBack.disabled = historyStack.length === 0;
}

function goBack() {
    if (historyStack.length > 0) {
        const previousState = historyStack.pop();
        updateBackButton();
        if (previousState.type === 'artists') {
            loadArtists(false);
        } else if (previousState.type === 'albums') {
            loadAlbums(previousState.id, previousState.name, false);
        }
    }
}

// --- 1.5 CHARGER LA PLAYLIST DU JOUR ---
async function loadPlaylistDuJour() {
    try {
        historyStack.push({ type: 'artists' }); 
        updateBackButton();

        contentDiv.innerHTML = "<p>Chargement de la playlist...</p>";
        const response = await fetch(`${SERVER_URL}/rest/getPlaylist?id=play_1&${AUTH_PARAMS}`);
        const data = await response.json();
        
        if (data['subsonic-response'].status === "failed" || !data['subsonic-response'].playlist.entry) {
            contentDiv.innerHTML = "<p>Aucune playlist du jour n'a été trouvée.</p>";
            pageTitle.innerText = "Playlist du jour";
            return;
        }

        contentDiv.innerHTML = "<div class='track-list'></div>";
        const listContainer = contentDiv.querySelector('.track-list');
        pageTitle.innerText = "Playlist du jour";

        const entries = data['subsonic-response'].playlist.entry;
        currentPlaylist = Array.isArray(entries) ? entries : [entries];
        
        currentPlaylist.forEach((track, index) => {
            const div = document.createElement('div');
            div.className = 'track';
            div.onclick = () => playAudioByIndex(index);
            
            const trackNum = index + 1;
            const time = formatTime(track.duration);
            
            div.innerHTML = `
                <span class="track-num">${trackNum}</span>
                <span class="track-title">${track.title} <br><small style="color:#888; font-size:0.85em;">${track.artist} - ${track.album}</small></span>
                <span class="track-duration">${time}</span>
            `;
            listContainer.appendChild(div);
        });
    } catch (error) {
        contentDiv.innerHTML = "<p>Erreur lors du chargement de la playlist.</p>";
    }
}

// --- 1. CHARGER LES ARTISTES ---
async function loadArtists(pushHistory = true) {
    try {
        contentDiv.innerHTML = "<p>Chargement des artistes...</p>";
        const response = await fetch(`${SERVER_URL}/rest/getIndexes?${AUTH_PARAMS}`);
        const data = await response.json();
        
        contentDiv.innerHTML = "";
        pageTitle.innerText = "Artistes";
        
        if (pushHistory) {
            historyStack = []; 
            updateBackButton();
        }

        if (!data['subsonic-response'].indexes || !data['subsonic-response'].indexes.index) {
            contentDiv.innerHTML = "<p>Aucun artiste trouvé. Le scan est peut-être en cours.</p>";
            return;
        }

        const indices = data['subsonic-response'].indexes.index;
        
        indices.forEach(indexNode => {
            const artists = Array.isArray(indexNode.artist) ? indexNode.artist : [indexNode.artist];
            artists.forEach(artist => {
                if(artist) {
                    const card = document.createElement('div');
                    card.className = 'card';
                    card.onclick = () => loadAlbums(artist.id, artist.name);
                    
                    const coverUrl = `${SERVER_URL}/rest/getCoverArt?id=${artist.id}&size=300&${AUTH_PARAMS}`;
                    
                    card.innerHTML = `
                        <img src="${coverUrl}" onerror="this.src='${FALLBACK_IMG}'">
                        <p>${artist.name}</p>
                    `;
                    contentDiv.appendChild(card);
                }
            });
        });
    } catch (error) {
        contentDiv.innerHTML = "<p>Erreur de connexion au serveur.</p>";
    }
}

// --- 2. CHARGER LES ALBUMS D'UN ARTISTE ---
async function loadAlbums(artistId, artistName, pushHistory = true) {
    try {
        if (pushHistory) {
            historyStack.push({ type: 'artists' });
            updateBackButton();
        }

        contentDiv.innerHTML = "<p>Chargement des albums...</p>";
        const response = await fetch(`${SERVER_URL}/rest/getMusicDirectory?id=${artistId}&${AUTH_PARAMS}`);
        const data = await response.json();
        
        contentDiv.innerHTML = "";
        pageTitle.innerText = artistName;

        const children = data['subsonic-response'].directory.child;
        if (!children) return;

        const albums = Array.isArray(children) ? children : [children];
        
        albums.forEach(album => {
            const card = document.createElement('div');
            card.className = 'card';
            card.onclick = () => loadTracks(album.id, album.title, artistId, artistName, album.coverArt);
            
            const coverUrl = `${SERVER_URL}/rest/getCoverArt?id=${album.coverArt}&size=300&${AUTH_PARAMS}`;
            
            card.innerHTML = `
                <img src="${coverUrl}" onerror="this.src='${FALLBACK_IMG}'">
                <p>${album.title}</p>
            `;
            contentDiv.appendChild(card);
        });
    } catch (error) {
        contentDiv.innerHTML = "<p>Erreur de chargement.</p>";
    }
}

// --- 3. CHARGER LES PISTES D'UN ALBUM ---
async function loadTracks(albumId, albumName, parentArtistId, parentArtistName, coverArtId) {
    try {
        historyStack.push({ type: 'albums', id: parentArtistId, name: parentArtistName });
        updateBackButton();

        contentDiv.innerHTML = "<p>Chargement des pistes...</p>";
        const response = await fetch(`${SERVER_URL}/rest/getMusicDirectory?id=${albumId}&${AUTH_PARAMS}`);
        const data = await response.json();
        
        contentDiv.innerHTML = "<div class='track-list'></div>";
        const listContainer = contentDiv.querySelector('.track-list');
        pageTitle.innerText = albumName;

        const children = data['subsonic-response'].directory.child;
        if (!children) return;

        const tracks = Array.isArray(children) ? children : [children];
        currentPlaylist = tracks;
        currentCoverUrl = `${SERVER_URL}/rest/getCoverArt?id=${coverArtId}&size=500&${AUTH_PARAMS}`;
        
        tracks.forEach((track, index) => {
            const div = document.createElement('div');
            div.className = 'track';
            div.onclick = () => playAudioByIndex(index);
            
            const trackNum = track.track || (index + 1);
            const time = formatTime(track.duration);
            
            div.innerHTML = `
                <span class="track-num">${trackNum}</span>
                <span class="track-title">${track.title}</span>
                <span class="track-duration">${time}</span>
            `;
            listContainer.appendChild(div);
        });
    } catch (error) {
        contentDiv.innerHTML = "<p>Erreur de chargement.</p>";
    }
}

// --- 4. LIRE LA MUSIQUE ---
function playAudioByIndex(index) {
    if (index < 0 || index >= currentPlaylist.length) return; 
    
    currentTrackIndex = index;
    const track = currentPlaylist[index];
    
    const streamUrl = `${SERVER_URL}/rest/stream?id=${track.id}&maxBitRate=128&${AUTH_PARAMS}`;
    audioPlayer.src = streamUrl;
    audioPlayer.play().catch(e => console.error("Erreur de lecture :", e));
    
    pageTitle.innerText = `▶ ${track.title}`;

    const trackCover = track.coverArt 
        ? `${SERVER_URL}/rest/getCoverArt?id=${track.coverArt}&size=500&${AUTH_PARAMS}` 
        : currentCoverUrl;

    // NOUVEAU : MISE À JOUR VISUELLE DU LECTEUR EN BAS DE PAGE
    npCover.src = trackCover;
    npCover.style.display = "block"; // Affiche l'image
    npCover.onerror = () => { npCover.src = FALLBACK_IMG; }; // En cas d'erreur de chargement
    npTitle.innerText = track.title;
    npArtist.innerText = track.artist || "Artiste inconnu";

    // MISE À JOUR ÉCRAN DE VEILLE / BLUETOOTH
    if ('mediaSession' in navigator) {
        navigator.mediaSession.metadata = new MediaMetadata({
            title: track.title,
            artist: track.artist || "Inconnu",
            album: track.album || "Inconnu",
            artwork: [{ src: trackCover, sizes: '500x500', type: 'image/jpeg' }]
        });

        navigator.mediaSession.setActionHandler('play', () => audioPlayer.play());
        navigator.mediaSession.setActionHandler('pause', () => audioPlayer.pause());
        navigator.mediaSession.setActionHandler('previoustrack', () => playAudioByIndex(currentTrackIndex - 1));
        navigator.mediaSession.setActionHandler('nexttrack', () => playAudioByIndex(currentTrackIndex + 1));
    }
}

// Enchaînement automatique
audioPlayer.onended = () => {
    playAudioByIndex(currentTrackIndex + 1);
};

window.onload = loadArtists;

```
<br>

### `www/now.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
 	<!-- PWA et Manifest -->
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#121212">

    <!-- Optimisations spécifiques pour iOS (Apple) -->
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoundCork">
    <link rel="apple-touch-icon" href="img/icon-192.png">

   <title>En Direct - SoundTouch</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <link rel="stylesheet" href="css/global.css">
    <style>
        .now-playing-container {
            display: flex;
            gap: 40px;
            background-color: var(--bg-elevated);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 40px;
            align-items: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        
        .np-cover-wrapper {
            width: 250px;
            height: 250px;
            flex-shrink: 0;
            background-color: #333;
            border-radius: 8px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
            font-size: 64px;
            color: var(--text-subdued);
        }
        .np-cover-img { width: 100%; height: 100%; object-fit: contain; display: none; }
        
        .np-details { flex: 1; min-width: 0; }
        .np-track { font-size: 36px; font-weight: bold; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .np-artist { font-size: 20px; color: var(--text-subdued); margin-bottom: 20px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        .np-meta-grid {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 8px 15px;
            font-size: 13px;
            color: var(--text-subdued);
            margin-bottom: 25px;
            background: var(--bg-highlight);
            padding: 15px;
            border-radius: 8px;
        }
        .np-meta-grid span { color: var(--text-base); font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}

        .progress-container { margin-top: 15px; }
        .progress-bar-bg { 
            width: 100%; 
            height: 6px; 
            background: #404040; 
            border-radius: 3px; 
            overflow: hidden; 
        }
        .progress-bar-fill { 
            height: 100%; 
            background: var(--spotify-green); 
            width: 0%; 
            transition: width 0.25s linear; 
        }
        .progress-time { 
            display: flex; 
            justify-content: space-between; 
            font-size: 12px; 
            color: var(--text-subdued); 
            margin-top: 8px; 
            font-family: monospace;
            font-weight: bold;
        }

        .np-live-show {
            display: flex;
            gap: 15px;
            margin-top: 25px;
            padding: 15px;
            background: var(--bg-highlight);
            border-left: 4px solid #E63946; 
            border-radius: 0 8px 8px 0;
            align-items: center;
        }
        .np-show-img {
            width: 100px;
            height: 60px;
            border-radius: 4px;
            object-fit: cover;
            display: none; 
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }
        .np-show-info {
            flex: 1;
            min-width: 0; 
        }
        .np-show-badge {
            font-size: 11px;
            text-transform: uppercase;
            color: #E63946;
            font-weight: bold;
            letter-spacing: 1px;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .np-show-badge i {
            font-size: 8px; 
        }
        .np-show-title {
            font-size: 16px;
            font-weight: bold;
            color: var(--text-base);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .np-show-desc {
            font-size: 13px;
            color: var(--text-subdued);
            margin-top: 4px;
            display: -webkit-box;
            -webkit-line-clamp: 2; 
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .mid-remote-wrapper {
            display: flex;
            justify-content: flex-end; 
            align-items: center;
            width: 100%;
            max-width: 250px; 
            margin: 0; 
            position: relative;
            z-index: 105;
        }
        
        #mid-remote-wrapper svg {
            width: 100%; 
            height: auto;
            display: block;
            filter: drop-shadow(0 15px 25px rgba(0,0,0,0.5));
            pointer-events: auto; 
        }

        #mid-remote-wrapper svg text {
            pointer-events: none; 
        }
        
        @media (max-width: 768px) {
            .now-playing-container {
                flex-direction: column !important; 
                padding: 15px !important; 
                gap: 20px !important; 
                margin-bottom: 20px !important; 
                text-align: center; 
            }
            .np-cover-wrapper {
                width: 240px !important;
                margin: 0 auto; 
            }
            .np-details {
                width: 100% !important;
                flex: none !important; 
            }
            .np-track {
                font-size: 22px !important;
                white-space: normal !important; 
            }
            .np-artist {
                font-size: 16px !important;
                margin-bottom: 15px !important;
            }
            .np-meta-grid {
                padding: 10px !important;
                margin-bottom: 15px !important;
                text-align: left; 
            }
        }
    </style>
</head>
<body>

    <div class="main-container">
        <div id="mobile-overlay" class="sidebar-overlay" onclick="toggleMobileMenu()"></div>
        <nav class="sidebar"></nav>

        <main class="main-view">
            <div class="top-bar">
                <!-- <div style="display: flex; width: 100%; align-items: center;"> -->
				<div style="display: flex; flex: 1; min-width: 0; align-items: center;">
                    <button class="mobile-menu-btn" onclick="toggleMobileMenu(event)">
                        <i class="fas fa-bars"></i>
                    </button>
                    <h2 class="section-title" style="margin: 0; padding-left: 15px;">
                        <i class="fas fa-broadcast-tower" style="color: var(--spotify-green); margin-right: 10px;"></i> Lecture en cours
                    </h2>
                </div>
                <div class="sources-wrapper" id="sources-wrapper" style="max-width: 150px; width: 100%; margin: 0 15px;"></div>
                <div class="mid-remote-wrapper" id="mid-remote-wrapper">
                </div>
            </div>

            <div id="no-speaker-msg" style="text-align: center; color: var(--text-subdued); margin: 40px 0;">
                <div class="loader" style="margin: 0 auto 15px auto;"></div>
                Recherche des enceintes en cours...
            </div>

            <div class="now-playing-container hidden" id="nowPlayingCard">
                <div class="np-cover-wrapper">
                    <i class="fas fa-music" id="np-cover-fallback"></i>
                    <img id="np-cover-img" class="np-cover-img" src="" alt="Cover">
                </div>
                
                <div class="np-details">
                    <div class="np-track" id="np-track">En attente...</div>
                    <div class="np-artist" id="np-artist">Veuillez sélectionner une enceinte</div>
                    
                    <div class="np-meta-grid">
                        <div>Album :</div><span id="np-album">-</span>
                        <div>Playlist :</div><span id="np-playlist">-</span>
                        <div>Source :</div><span id="np-source">-</span>
                        <div>Statut :</div><span id="np-status">-</span>
                    </div>

                    <div class="progress-container">
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill" id="np-progress-fill"></div>
                        </div>
                        <div class="progress-time">
                            <span id="np-time-current">0:00</span>
                            <span id="np-time-total">0:00</span>
                        </div>
                    </div>

                    <div id="np-live-show" class="np-live-show hidden">
                        <img id="np-show-img" class="np-show-img" src="" alt="Émission">
                        <div class="np-show-info">
                            <div class="np-show-badge"><i class="fas fa-circle"></i> En direct</div>
                            <div class="np-show-title" id="np-show-title">-</div>
                            <div class="np-show-desc" id="np-show-desc">-</div>
                        </div>
                    </div>
                </div>
            </div>

        </main>
    </div>

    <footer class="player-bar"></footer>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script src="js/app.js"></script>
    
    <script>
        let currentShuffle = "SHUFFLE_OFF";
        let currentRepeat = "REPEAT_OFF";

        document.addEventListener("DOMContentLoaded", async () => {
            await loadComponent(null, "components/remotemid.svg", "#mid-remote-wrapper");
            
            window.sendKey = async function(keyName) { if(typeof sendCommand === "function") await sendCommand(keyName); };
            window.sendPreset = async function(id) { if(typeof playPreset === "function") await playPreset(id); };
            
            onStateUpdated();
        });

        function onStateUpdated() {
            if (typeof getSelectedIps !== "function" || !globalData.speakers) return;

            const ips = getSelectedIps();
            const npCard = document.getElementById("nowPlayingCard");
            const noMsg = document.getElementById("no-speaker-msg");

            if (ips.length === 0 || !globalData.speakers[ips[0]]) {
                npCard.classList.add('hidden');
                noMsg.classList.remove('hidden');
                noMsg.innerText = "Cochez une enceinte dans le menu pour voir les détails.";
                updateBigRemoteUI({}); 
                return;
            }
            
            const spk = globalData.speakers[ips[0]];
            
            if (spk.state === 'OFF' || spk.state === 'STANDBY') {
                npCard.classList.add('hidden');
                noMsg.classList.remove('hidden');
                noMsg.innerText = "L'enceinte sélectionnée est actuellement en veille.";
                updateBigRemoteUI({}); 
                return;
            }

            npCard.classList.remove('hidden');
            noMsg.classList.add('hidden');

            document.getElementById("np-track").textContent = spk.track || "Prêt";
            document.getElementById("np-artist").textContent = spk.artist || "Artiste inconnu";
            document.getElementById("np-album").textContent = spk.album || "-";
            document.getElementById("np-playlist").textContent = spk.playlist || "Flux Direct";
            document.getElementById("np-source").textContent = spk.source || "-";

            const progressContainer = document.querySelector(".progress-container");
            const radioSources = ['TUNEIN', 'RADIO_BROWSER', 'LOCAL_INTERNET_RADIO'];

            if (radioSources.includes(spk.source)) {
                progressContainer.style.display = 'none';
            } else {
                progressContainer.style.display = 'block';
            }
    
            let statusText = spk.playStatus;
            if (statusText === "PLAY_STATE") statusText = "▶ Lecture";
            if (statusText === "PAUSE_STATE") statusText = "⏸ Pause";
            if (statusText === "BUFFERING_STATE") statusText = "⏳ Chargement...";
            if (statusText === "STOP_STATE") statusText = "⏹ Arrêté";
            document.getElementById("np-status").textContent = statusText || "Prêt";

            const coverImg = document.getElementById("np-cover-img");
            const fallbackIcon = document.getElementById("np-cover-fallback");
            
            let finalCoverUrl = spk.cover;
            
            if (finalCoverUrl && finalCoverUrl !== "FA_ICON" && finalCoverUrl !== "SHOW_DEFAULT_IMAGE") {
                const currentTrackName = spk.track || spk.playlist || "Unknown";
                if (!finalCoverUrl.includes('cb=')) {
                    const separator = finalCoverUrl.includes('?') ? '&' : '?';
                    finalCoverUrl += `${separator}cb=${encodeURIComponent(currentTrackName)}`;
                }            
                
                coverImg.src = finalCoverUrl;
                coverImg.style.display = "block";
                fallbackIcon.style.display = "none";
            } else {
                coverImg.style.display = "none";
                fallbackIcon.style.display = "block";
                
                if (spk.source === 'LOCAL_INTERNET_RADIO' || spk.source === 'RADIO_BROWSER') {
                    fallbackIcon.className = "fas fa-broadcast-tower";
                } else {
                    fallbackIcon.className = "fas fa-music";
                }
            }

            const liveShowBlock = document.getElementById("np-live-show");
            
            if (spk.show_title) {
                liveShowBlock.classList.remove('hidden');
                document.getElementById("np-show-title").textContent = spk.show_title;
                document.getElementById("np-show-desc").textContent = spk.show_desc || ""; 
                
                const showImg = document.getElementById("np-show-img");
                if (spk.show_image && spk.show_image !== "" && spk.show_image !== "FA_ICON") {
                    showImg.src = spk.show_image;
                    showImg.style.display = "block";
                } else {
                    showImg.style.display = "none";
                }
            } else {
                liveShowBlock.classList.add('hidden');
            }

            updateBigRemoteUI(spk);
        }

        setInterval(function runFluidTimer() {
            if (typeof getSelectedIps !== "function" || !globalData.speakers) return;
            const ips = getSelectedIps();
            if (ips.length === 0) return;
            const spk = globalData.speakers[ips[0]];
            if (!spk) return;

            if (spk.time_total && parseInt(spk.time_total) > 0) {
                let pos = spk.local_time_base || 0;
                
                if (spk.playStatus === "PLAY_STATE") {
                    pos += (Date.now() - (spk.local_time_anchor || Date.now())) / 1000;
                }
                
                let tot = parseInt(spk.time_total);
                if (pos > tot) pos = tot;
                
                refreshProgressDOM(pos, tot);
            } else {
                refreshProgressDOM(0, 0);
            }
        }, 250);

        function refreshProgressDOM(elapsed, total) {
            const progressFill = document.getElementById("np-progress-fill");
            const timeCurrent = document.getElementById("np-time-current");
            const timeTotal = document.getElementById("np-time-total");
            
            if (total > 0) {
                const pct = (elapsed * 100) / total;
                if (progressFill) progressFill.style.width = pct + "%";
                if (timeCurrent) timeCurrent.textContent = formatTime(elapsed);
                if (timeTotal) timeTotal.textContent = formatTime(total);
            } else {
                if (progressFill) progressFill.style.width = "0%";
                if (timeCurrent) timeCurrent.textContent = formatTime(elapsed);
                if (timeTotal) timeTotal.textContent = "Live / Direct";
            }
        }

        function updateBigRemoteUI(spk) {
            currentShuffle = spk.shuffleSetting || "SHUFFLE_OFF";
            currentRepeat = spk.repeatSetting || "REPEAT_OFF";

            const opActive = "1";        
            const opInactive = "0.3";    

            const logoShuff = document.getElementById('logoShuff');
            const logoRep = document.getElementById('logoRep');
            const logoRepOne = document.getElementById('logoRepOne');

            if (logoShuff) logoShuff.style.opacity = currentShuffle === "SHUFFLE_ON" ? opActive : opInactive;

            if (logoRep && logoRepOne) {
                if (currentRepeat === "REPEAT_ALL") {
                    logoRep.style.opacity = opActive;
                    logoRepOne.style.display = "none";
                } else if (currentRepeat === "REPEAT_ONE") {
                    logoRep.style.opacity = opActive;
                    logoRepOne.style.display = "block"; 
                    logoRepOne.style.opacity = opActive;
                } else {
                    logoRep.style.opacity = opInactive;
                    logoRepOne.style.display = "none";  
                }
            }

            for (let i = 1; i <= 6; i++) {
                let presetName = (globalData.presets && globalData.presets[i]) ? globalData.presets[i] : "";
                const svgTextEl = document.getElementById(`preset-text-${i}`);
                if (svgTextEl) {
                    svgTextEl.textContent = presetName.length > 14 ? presetName.substring(0, 13) + "_" : presetName;
                }
            }
        }

        async function toggleShuffle() {
            const targetKey = currentShuffle === "SHUFFLE_ON" ? "SHUFFLE_OFF" : "SHUFFLE_ON";
            if (typeof sendCommand === "function") await sendCommand(targetKey);
        }

        async function toggleRepeat() {
            let targetKey = "REPEAT_OFF";
            if (currentRepeat === "REPEAT_OFF") targetKey = "REPEAT_ALL";
            else if (currentRepeat === "REPEAT_ALL") targetKey = "REPEAT_ONE";
            else if (currentRepeat === "REPEAT_ONE") targetKey = "REPEAT_OFF";
            if (typeof sendCommand === "function") await sendCommand(targetKey);
        }
    </script>
</body>
</html>
```
<br>

### `www/player.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pi Web Player</title>
    <style>
        /* --- Styles de base et Mode Sombre --- */
        body { 
            margin: 0; 
            font-family: system-ui, -apple-system, sans-serif; 
            background: #121212; 
            color: #ffffff; 
            padding-bottom: 90px; /* Espace pour le lecteur audio fixe */
        }
        
        header { 
            background: #1f1f1f; 
            padding: 15px 20px; 
            display: flex; 
            align-items: center; 
            gap: 15px;
            position: sticky; 
            top: 0; 
            z-index: 100;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        
        h1 { margin: 0; font-size: 1.2rem; flex-grow: 1; text-align: center; }
        
        button { 
            background: #007bff; 
            color: white; 
            border: none; 
            padding: 8px 16px; 
            border-radius: 6px; 
            font-weight: bold;
            cursor: pointer; 
            transition: background 0.2s;
        }
        button:hover { background: #0056b3; }
        button:disabled { background: #333; color: #777; cursor: not-allowed; }

        #content { 
            padding: 20px; 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); 
            gap: 20px; 
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .card { 
            background: #1e1e1e; 
            border-radius: 10px; 
            overflow: hidden; 
            cursor: pointer; 
            transition: transform 0.2s, background 0.2s; 
            text-align: center; 
            padding-bottom: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .card:hover { transform: translateY(-5px); background: #2a2a2a; }
        
        .card img { 
            width: 100%; 
            aspect-ratio: 1; 
            object-fit: cover; 
            background: #333; 
            border-bottom: 2px solid #007bff;
        }
        
        .card p { 
            margin: 10px 10px 0; 
            font-size: 0.95rem; 
            font-weight: bold; 
            white-space: nowrap; 
            overflow: hidden; 
            text-overflow: ellipsis;
        }

        .track-list { 
            display: flex; 
            flex-direction: column; 
            gap: 8px; 
            grid-column: 1 / -1; 
        }
        
        .track { 
            background: #1e1e1e; 
            padding: 15px; 
            border-radius: 8px; 
            display: flex; 
            align-items: center;
            cursor: pointer; 
            transition: background 0.2s;
        }
        .track:hover { background: #2a2a2a; }
        .track .track-num { color: #888; width: 30px; font-weight: bold; }
        .track .track-title { flex-grow: 1; font-weight: 500; }
        .track .track-duration { color: #888; font-size: 0.9rem; }

        /* --- LECTEUR AUDIO FIXE (NOUVEAU DESIGN) --- */
        #player-container { 
            position: fixed; 
            bottom: 0; left: 0; right: 0; 
            background: #181818; 
            padding: 10px 20px; 
            border-top: 1px solid #333; 
            display: flex; 
            align-items: center; 
            gap: 15px; /* Espace entre pochette, texte et lecteur */
            z-index: 200;
        }
        
        #now-playing-cover {
            width: 50px;
            height: 50px;
            border-radius: 5px;
            object-fit: cover;
            display: none; /* Caché au démarrage */
        }
        
        #now-playing-info {
            flex: 1; /* Prend l'espace nécessaire */
            min-width: 0; /* Empêche le texte long de casser la mise en page */
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        
        #now-playing-title { margin: 0; font-weight: bold; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        #now-playing-artist { margin: 0; color: #888; font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        audio { flex: 2; min-width: 200px; outline: none; }

        /* Mode mobile */
        @media (max-width: 600px) {
            #player-container { padding: 8px 10px; gap: 10px; }
            #now-playing-cover { width: 40px; height: 40px; }
        }
    </style>
</head>
<body>

    <header>
        <button id="btn-back" disabled onclick="goBack()">&#8592; Retour</button>
        <h1 id="page-title">Ma Musique (Pi)</h1>
        <button onclick="loadPlaylistDuJour()">🌟 Quotidienne</button>
        <button onclick="loadArtists()">Accueil</button>
    </header>

    <div id="content">
        <!-- Le contenu JavaScript s'injecte ici -->
    </div>

    <div id="player-container">
        <!-- NOUVEAU : Pochette et infos du titre en cours -->
        <img id="now-playing-cover" src="" alt="Cover">
        <div id="now-playing-info">
            <p id="now-playing-title"></p>
            <p id="now-playing-artist"></p>
        </div>
        <audio id="audio-player" controls autoplay></audio>
    </div>

    <!-- Forçage du cache navigateur avec v=3 -->
    <script src="js/player.js?v=3"></script>
</body>
</html>

```
<br>

### `www/podcasts.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
	<!-- PWA et Manifest -->
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#121212">

    <!-- Optimisations spécifiques pour iOS (Apple) -->
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoundCork">
    <link rel="apple-touch-icon" href="img/icon-192.png">

    <title>🎙 Podcasts - SoundTouch</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <link rel="stylesheet" href="css/global.css">
    <style>
        .folder-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 40px; }
        .folder-item { background-color: var(--bg-elevated); border-radius: 8px; overflow: hidden; }
        .folder-header { padding: 16px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; font-weight: bold; transition: background-color 0.2s;}
        .folder-header:hover { background-color: var(--bg-highlight); }
        .folder-content { display: none; padding: 0 16px 16px 16px; }
        .folder-content.open { display: block; }
        .track-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #282828;}
        .track-item:last-child { border-bottom: none; }
        
        .status-bar { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background-color: #333; color: white; padding: 12px 24px; border-radius: 500px; font-weight: bold; box-shadow: 0 8px 24px rgba(0,0,0,0.5); z-index: 2000; display: none; transition: opacity 0.3s; }
        .status-success { background-color: var(--spotify-green); color: black; }
        .status-error { background-color: #FA243C; color: white; }
        .status-warning { background-color: #FF9900; color: black;}

		.preset-label {
			font-size: 2px;
			font-family: Arial, sans-serif;
		}
    </style>
</head>
<body>
    <div id="status-bar" class="status-bar">Notification</div>

    <div class="main-container">
        <div id="mobile-overlay" class="sidebar-overlay" onclick="toggleMobileMenu()"></div>
        <nav class="sidebar"></nav>

        <main class="main-view">
            <div class="top-bar">
			<!-- avant -->
			<!-- <div style="display: flex; width: 100%; align-items: center;"> -->
			<!-- après -->
			<div style="display: flex; flex: 1; min-width: 0; align-items: center;">                  
				<button class="mobile-menu-btn" onclick="toggleMobileMenu(event)">
					<i class="fas fa-bars"></i>
					</button>
                    <div class="search-container">
                        <input type="text" id="search-podcast-q" class="search-input" placeholder="Chercher un podcast en ligne...">
                        <select id="country" class="search-select">
                            <option value="fr" selected>🇫🇷 FR</option>
                            <option value="be">🇧🇪 BE</option>
                            <option value="ch">🇨🇭 CH</option>
                            <option value="ca">🇨🇦 CA</option>
                        </select>
                        <button class="btn-search" onclick="searchPodcasts()">Rechercher</button>
                    </div>
                </div>
                
                <!-- <div class="sources-wrapper" id="sources-wrapper" style="max-width: 150px; width: 100%; margin: 0 15px;"></div> -->
				<div class="remote-wrapper" id="remote-wrapper"></div>
            </div>

			<button class="btn-action btn-action-primary" style="margin-bottom: 30px; font-size: 16px; padding: 12px; background-color: rgba(29, 185, 84, 0.1);" onclick="toggleRFDownloaderPanel()">
				<i class="fas fa-cloud-download-alt"></i> <span id="rf-btn-text">Ouvrir le téléchargeur Radio France (Intégré)</span>
			</button>

			<div id="rf-downloader-panel" style="display: none; background-color: var(--bg-elevated); padding: 20px; border-radius: 8px; margin-bottom: 30px; border: 1px solid #282828;">
				<h3 style="margin-top: 0; margin-bottom: 15px; color: var(--text-base); font-size: 16px;"><i class="fas fa-search" style="color: var(--spotify-green);"></i> Rechercher une émission à télécharger</h3>
				
				<div class="search-container" style="margin-bottom: 20px; width: 100%; max-width: 100%;">
					<input type="text" id="search-rf-q" class="search-input" placeholder="Ex: Affaires sensibles, Hondelatte raconte...">
					<select id="rf-station-select" class="search-select">
						<option value="">Toutes les radios</option>
						<option value="FRANCEINTER">France Inter</option>
						<option value="FRANCECULTURE">France Culture</option>
						<option value="FRANCEINFO">franceinfo</option>
						<option value="FRANCEMUSIQUE">France Musique</option>
						<option value="FRANCEBLEU">France Bleu</option>
						<option value="FIP">FIP</option>
						<option value="MOUV">Mouv'</option>
					</select>
					<button class="btn-search" onclick="searchRFShows()">Chercher</button>
				</div>
				
				<div id="rf-search-results" class="grid"></div>
			</div>

            <div id="search-section" class="hidden">
                <h2 class="section-title">Résultats iTunes</h2>
                <div class="grid" id="podcast-results"></div>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 class="section-title" style="margin: 0;">📚 Bibliothèque Radio France</h2>
                <button class="btn-action btn-action-primary" style="width: auto; padding: 5px 15px;" onclick="loadLocalRFDownloads()">
                    <i class="fas fa-sync-alt"></i> Actualiser
                </button>
            </div>
            
            <div class="folder-list" id="local-rf-list">
                <p style="color:var(--text-subdued)">Chargement de la bibliothèque locale...</p>
            </div>
        </main>
    </div>
    
    <footer class="player-bar"></footer>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
	<script src="js/app.js"></script>
    <script>
        function showNotification(msg, type = "warning") {
            const statusBar = document.getElementById('status-bar');
            statusBar.innerText = msg;
            statusBar.className = `status-bar status-${type}`;
            statusBar.style.display = 'block';
            setTimeout(() => { statusBar.style.display = 'none'; }, 4000);
        }

        document.getElementById('search-podcast-q').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') searchPodcasts();
        });

        async function searchPodcasts() {
            const query = document.getElementById('search-podcast-q').value.trim();
            const country = document.getElementById('country').value;
            const resDiv = document.getElementById('podcast-results');
            const sectionDiv = document.getElementById('search-section');

            if (query.length < 2) return;

            sectionDiv.classList.remove('hidden');
            resDiv.innerHTML = '<p style="color:var(--text-subdued)">Recherche en cours...</p>';

            try {
                const response = await fetch(`/api/podcasts/search?q=${encodeURIComponent(query)}&country=${country}`);
                const episodes = await response.json();
                
                if (!episodes || episodes.length === 0) {
                    resDiv.innerHTML = '<p style="color:var(--text-subdued)">Aucun épisode trouvé.</p>';
                    return;
                }

                resDiv.innerHTML = episodes.map(ep => {
                    const cleanTitle = ep.title.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    return `
                        <div class="card">
                            <div class="card-icon" style="background-image: url('${ep.cover || ''}');" onclick="playPodcast('${ep.url}', '${cleanTitle}')">
                                ${ep.cover ? '' : '<i class="fas fa-podcast"></i>'}
                            </div>
                            <div class="card-title" title="${ep.title}">${ep.title}</div>
                            <div class="card-subtitle">${ep.emission} • ${ep.date}</div>
                            <div class="card-actions">
                                <button class="btn-card btn-card-play" style="width:100%" onclick="playPodcast('${ep.url}', '${cleanTitle}')">▶ Lire l'épisode</button>
                            </div>
                        </div>
                    `;
                }).join('');
            } catch (error) {
                resDiv.innerHTML = '<p style="color:#FA243C">Erreur lors de la recherche.</p>';
            }
        }

        async function playPodcast(audioUrl, title) {
            const ips = getSelectedIps(); 
            if (ips.length === 0) return showNotification("Sélectionnez au moins une enceinte active.", "error");
            
            showNotification("⏳ Chargement du flux en cours...", "warning");
            try {
                const response = await fetch('/api/play_podcast', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url: audioUrl, name: title, ips: ips })
                });
                const data = await response.json();
                if (data.status === 'ok') {
                    showNotification("✅ Lecture lancée !", "success");
                    setTimeout(fetchState, 1500); 
                } else {
                    showNotification("❌ Erreur : " + data.message, "error");
                }
            } catch (error) {
                showNotification("❌ Erreur de communication.", "error");
            }
        }

        function toggleFolder(idx) {
            document.getElementById(`folder-content-${idx}`).classList.toggle('open');
        }

        async function loadLocalRFDownloads() {
            const container = document.getElementById('local-rf-list');
            container.innerHTML = '<p style="color:var(--text-subdued)">Actualisation...</p>';
            try {
                const res = await fetch('/api/local_rf_downloads');
                const data = await res.json();
                container.innerHTML = '';
                
                const showNames = Object.keys(data);
                if (showNames.length === 0) {
                    container.innerHTML = '<p style="color:var(--text-subdued)">Aucun podcast téléchargé trouvé.</p>';
                    return;
                }
                
                showNames.forEach((name, idx) => {
                    const files = data[name];
                    const trackListHtml = files.map(f => {
                        const fullPath = `${name}/${f}`;
                        const cleanTitle = f.replace('.mp3', '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
                        const cleanPath = fullPath.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                        return `
							<div class="track-item">
								<span style="font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-right: 15px;">
									<i class="fas fa-music" style="color:var(--text-subdued); margin-right: 10px;"></i> ${f}
								</span>
								<div style="display: flex; gap: 8px;">
									<button class="btn-card btn-card-play" style="padding: 5px 15px; width: auto;" onclick="playLocalRF('${cleanPath}', '${cleanTitle}')">▶ Lire</button>
									<button class="btn-card" style="padding: 5px 15px; width: auto; background-color: #FA243C; color: white;" onclick="deleteLocalRF('${cleanPath}')" title="Supprimer l'épisode">
										<i class="fas fa-trash"></i>
									</button>
								</div>
							</div>
						`;
                    }).join('');

                    container.innerHTML += `
                        <div class="folder-item">
                            <div class="folder-header" onclick="toggleFolder(${idx})">
                                <div><i class="fas fa-folder" style="color: #FFC107; margin-right: 10px;"></i> ${name} <span style="background:var(--spotify-green); color:black; padding:2px 8px; border-radius:12px; font-size:12px; margin-left:10px;">${files.length}</span></div>
                                <i class="fas fa-chevron-down"></i>
                            </div>
                            <div class="folder-content" id="folder-content-${idx}">
                                ${trackListHtml}
                            </div>
                        </div>
                    `;
                });
            } catch (error) {
                container.innerHTML = '<p style="color:#FA243C">Impossible de charger la bibliothèque locale.</p>';
            }
        }

        async function playLocalRF(path, title) {
            const ips = getSelectedIps();
            if (ips.length === 0) return showNotification("Sélectionnez au moins une enceinte active.", "error");
            
            showNotification("⏳ Envoi du fichier local...", "warning");
            try {
                const response = await fetch('/api/play_local_rf', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ path: path, name: title, ips: ips })
                });
                const data = await response.json();
                if (data.status === 'ok') {
                    showNotification("✅ Lecture instantanée lancée !", "success");
                    setTimeout(fetchState, 1500);
                } else {
                    showNotification("❌ Erreur : " + data.message, "error");
                }
            } catch (error) {
                showNotification("❌ Erreur de communication.", "error");
            }
        }
		
		async function deleteLocalRF(path) {
			if (!confirm("Voulez-vous vraiment supprimer cet épisode ?")) return;
			
			showNotification("🗑 Suppression en cours...", "warning");
			try {
				const response = await fetch('/api/delete_local_rf', {
					method: 'POST',
					headers: {'Content-Type': 'application/json'},
					body: JSON.stringify({ path: path })
				});
				const data = await response.json();
				if (data.status === 'ok') {
					showNotification("✅ Fichier supprimé avec succès !", "success");
					loadLocalRFDownloads();
				} else {
					showNotification("❌ Erreur : " + data.message, "error");
				}
			} catch (error) {
				showNotification("❌ Erreur de communication avec le serveur.", "error");
			}
		}
		
		function toggleRFDownloaderPanel() {
			const panel = document.getElementById('rf-downloader-panel');
			const btnText = document.getElementById('rf-btn-text');
			if (panel.style.display === 'none') {
				panel.style.display = 'block';
				btnText.innerText = "Fermer le téléchargeur Radio France";
			} else {
				panel.style.display = 'none';
				btnText.innerText = "Ouvrir le téléchargeur Radio France (Intégré)";
			}
		}

		document.getElementById('search-rf-q').addEventListener('keypress', function (e) {
			if (e.key === 'Enter') searchRFShows();
		});

		async function searchRFShows() {
			const query = document.getElementById('search-rf-q').value.trim();
			const station = document.getElementById('rf-station-select').value;
			const resDiv = document.getElementById('rf-search-results');
			
			if (!query) return;
			
			resDiv.innerHTML = '<p style="color:var(--text-subdued)">Recherche en cours sur Radio France...</p>';
			
			let url = `/api/rf/shows?query=${encodeURIComponent(query)}`;
			if (station) url += `&station=${encodeURIComponent(station)}`;
			
			try {
				const response = await fetch(url);
				const shows = await response.json();
				
				if (!shows || shows.length === 0 || shows.error) {
					resDiv.innerHTML = '<p style="color:var(--text-subdued)">Aucune émission trouvée. Vérifiez votre clé API.</p>';
					return;
				}
				
				resDiv.innerHTML = shows.map((show, idx) => {
					const b64Url = btoa(unescape(encodeURIComponent(show.url)));
					return `
						<div class="card">
							<div class="card-icon" style="display: flex; align-items: center; justify-content: center; background: #282828;">
								<i class="fas fa-broadcast-tower" style="font-size: 28px; color: var(--text-subdued);"></i>
							</div>
							<div class="card-title" title="${show.title}">${show.title}</div>
							<div class="card-subtitle">${show.station}</div>
							<div class="card-actions" style="flex-direction: column; gap: 8px; width: 100%; padding-top: 10px;">
								<select id="rf-count-${idx}" style="background: #181818; color: var(--text-base); border: 1px solid #282828; padding: 6px; border-radius: 4px; width: 100%; font-size: 12px;">
									<option value="1">1 seul (dernier)</option>
									<option value="3">3 derniers</option>
									<option value="5">5 derniers</option>
									<option value="10">10 derniers</option>
								</select>
								<button class="btn-card btn-card-play" style="width: 100%; margin: 0; padding: 6px; font-size: 12px; border-radius: 4px; background-color: rgba(29, 185, 84, 0.2);" onclick="downloadRFShow('${b64Url}', 'rf-count-${idx}')">
									<i class="fas fa-download"></i> Télécharger
								</button>
							</div>
						</div>
					`;
				}).join('');
			} catch (e) {
				resDiv.innerHTML = '<p style="color:#FA243C">Erreur lors de la communication avec le serveur.</p>';
			}
		}

		async function downloadRFShow(b64Url, selectId) {
			const url = decodeURIComponent(escape(atob(b64Url)));
			const count = document.getElementById(selectId).value;
			
			showNotification("📥 Planification du téléchargement...", "warning");
			
			try {
				const response = await fetch('/api/rf/download', {
					method: 'POST',
					headers: {'Content-Type': 'application/json'},
					body: JSON.stringify({ show_url: url, latest_n: parseInt(count) })
				});
				const data = await response.json();
				
				if (data.message) {
					showNotification("✅ " + data.message, "success");
					setTimeout(loadLocalRFDownloads, 4000);
				} else {
					showNotification("❌ Erreur : " + (data.error || "Inconnue"), "error");
				}
			} catch (error) {
				showNotification("❌ Erreur de réseau lors du lancement.", "error");
			}
		}

        loadLocalRFDownloads();
    </script>
</body>
</html>
```
<br>

### `www/radios.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
	<!-- PWA et Manifest -->
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#121212">

    <!-- Optimisations spécifiques pour iOS (Apple) -->
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoundCork">
    <link rel="apple-touch-icon" href="img/icon-192.png">

    <title>SoundTouch Web Player</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <link rel="stylesheet" href="css/global.css">
	<style>
		.preset-label {
			font-size: 2px;
			font-family: Arial, sans-serif;
		}
	</style>
</head>
<body>

    <div class="main-container">
        <div id="mobile-overlay" class="sidebar-overlay" onclick="toggleMobileMenu()"></div>
        <nav class="sidebar"></nav>

        <main class="main-view">
            <div class="top-bar">
                <!-- <div style="display: flex; width: 100%; align-items: center;"> -->
				<div style="display: flex; flex: 1; min-width: 0; align-items: center;">
                    <button class="mobile-menu-btn" onclick="toggleMobileMenu(event)">
                        <i class="fas fa-bars"></i>
                    </button>
                    
                    <div class="search-container">
                        <input type="text" id="search-input" class="search-input" placeholder="Nom de la radio...">
                        <select id="country-select" class="search-select">
                            <option value="FR" selected>🇫🇷 FR</option>
                            <option value="BE">🇧🇪 BE</option>
                            <option value="ES">🇪🇸 ES</option>
                            <option value="CH">🇨🇭 CH</option>
                            <option value="GB">🇬🇧 GB</option>
                            <option value="US">🇺🇸 US</option>
                        </select>
                        <button class="btn-search" onclick="searchRadios()">Rechercher</button>
                    </div>
                </div>
                
                <!-- <div class="sources-wrapper" id="sources-wrapper" style="max-width: 150px; width: 100%; margin: 0 15px;"></div> -->
                <div class="remote-wrapper" id="remote-wrapper"></div>
            </div>

            <h2 class="section-title" id="main-title">Accueil</h2>
            <div id="loading-indicator" class="loader hidden" style="margin-bottom: 20px;"></div>
            
            <div class="grid" id="main-grid">
                </div>
        </main>
    </div>

    <footer class="player-bar"></footer>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
	<script src="js/app.js"></script>
	<script>
	async function searchRadios() {
		const query = document.getElementById('search-input').value;
		const country = document.getElementById('country-select').value;
		if (!query) return renderHomeGrid(); 

		document.getElementById('loading-indicator').classList.remove('hidden');
		document.getElementById('main-title').innerText = `Résultats pour "${query}"`;
		const grid = document.getElementById('main-grid');
		grid.innerHTML = '';

		try {
			const response = await fetch(`/api/radios/search?q=${encodeURIComponent(query)}&country=${country}`);
			const results = await response.json();
			
			if (results.length === 0) {
				grid.innerHTML = '<p style="color:var(--text-subdued)">Aucun résultat trouvé.</p>';
				return;
			}

			grid.innerHTML = results.map(r => {
				const cleanName = r.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
				
                let visualHtml = '<i class="fas fa-broadcast-tower" style="font-size: 35px; color: #888;"></i>';
                
                if (r.logo && r.logo !== 'FA_ICON') {
                    visualHtml = `<img src="${r.logo}" alt="${cleanName}" style="width: 100%; height: 100%; border-radius: 8px; object-fit: contain;">`;
                }

				return `
					<div class="card">
						<div class="card-icon" onclick="playRadio('${r.uuid}', '${cleanName}')" title="Lancer" style="cursor: pointer; display: flex; align-items: center; justify-content: center; width: 100%; height: 70px; margin-bottom: 10px;">
                            ${visualHtml}
                        </div>
						<div class="card-title" title="${r.name}">${r.name}</div>
						<div class="card-subtitle">${r.country || 'Inconnu'}</div>
						<div class="card-actions">
							<button class="btn-card btn-card-play" onclick="playRadio('${r.uuid}', '${cleanName}')">▶ Lancer</button>
                            <button class="btn-card btn-card-add" onclick="addRadio('${cleanName}', '${r.uuid}', '${r.logo || 'FA_ICON'}')">＋ Ajouter</button>
						</div>
					</div>`;
			}).join('');
		} catch (error) {
			grid.innerHTML = '<p style="color:#FA243C">Erreur lors de la recherche.</p>';
		} finally {
			document.getElementById('loading-indicator').classList.add('hidden');
		}
	}

	async function addRadio(originalName, uuid, logo) {
		if (!globalData.radios) globalData.radios = [];
		if (globalData.radios.some(r => String(r.uuid) === String(uuid))) return alert("Déjà dans vos favoris !");
		
        let cleanName = prompt("Entrez le nom de la radio (un nom simple aidera à trouver le logo automatiquement) :", originalName);
        
        if (!cleanName || cleanName.trim() === "") return; 
        
        globalData.radios.push({ name: cleanName.trim(), uuid: String(uuid), logo: logo });
		await saveRadiosToServer();
	}

	async function playRadio(uuid, name) {
		const ips = getSelectedIps();
		if (ips.length === 0) return alert("Sélectionnez au moins une enceinte !");
		await fetch('/api/play_radio', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ips, uuid, name }) });
		setTimeout(fetchState, 1500);
	}

	async function removeRadio(uuid) {
		if (!globalData.radios) return;
		globalData.radios = globalData.radios.filter(r => String(r.uuid) !== String(uuid));
		await saveRadiosToServer();
		
		const searchInput = document.getElementById('search-input');
		if (searchInput && searchInput.value.trim() === '') renderHomeGrid();
	}

	async function saveRadiosToServer() {
		try {
			const response = await fetch('/api/radios/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ radios: globalData.radios }) });
			if (response.ok) await fetchState();
		} catch (e) { console.error("Erreur sauvegarde radios:", e); }
	}
	
	document.addEventListener("DOMContentLoaded", async () => {
		try {
			if (typeof fetchState === "function") {
				await fetchState(); 
			}
		} catch (e) {
			console.error("Erreur lors du chargement des données initiales", e);
		}

		if (typeof renderHomeGrid === "function") {
			renderHomeGrid();
		}
	});
	</script>

</body>
</html>
```
<br>

### `www/remote.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
	<!-- PWA et Manifest -->
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#121212">

    <!-- Optimisations spécifiques pour iOS (Apple) -->
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoundCork">
    <link rel="apple-touch-icon" href="img/icon-192.png">

    <title>Télécommande Complète - SoundTouch</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <link rel="stylesheet" href="css/global.css">
	<style>
			/* 1. Le conteneur s'étire pour occuper tout l'espace libre de l'écran */
			.big-remote-wrapper {
				display: flex;
				justify-content: center;
				align-items: center;
				width: 100%;
				flex: 1; /* Prend toute la hauteur disponible dans le <main> */
				margin: 0 auto;
				padding-bottom: 20px;
			}
			
			/* 2. La télécommande calcule sa taille max sans jamais provoquer de scroll */
			#big-remote-wrapper svg {
				width: 100%;
				height: auto;
				/* Le calcul magique : Hauteur de l'écran visible (100dvh) - TopBar - Player (Footer) */
				max-height: calc(100dvh - 200px); 
				/* On limite la largeur à 450px pour que sur un écran d'ordinateur, la télécommande ne fasse pas 2 mètres de large ! */
				max-width: 450px; 
				display: block;
				filter: drop-shadow(0 15px 25px rgba(0,0,0,0.5));
			}
		</style>
</head>
<body>
    <div id="status-bar" class="status-bar">Notification</div>

    <div class="main-container">
        <div id="mobile-overlay" class="sidebar-overlay" onclick="toggleMobileMenu()"></div>
        <nav class="sidebar"></nav>

        <main class="main-view">
            <div class="top-bar">
                <div style="display: flex; width: 100%; align-items: center;">
                    <button class="mobile-menu-btn" onclick="toggleMobileMenu(event)">
                        <i class="fas fa-bars"></i>
                    </button>
                    <h2 class="section-title" style="margin: 0; padding-left: 15px;"></h2>  <!-- Télécommande -->
                </div>
            </div>

            <div class="big-remote-wrapper" id="big-remote-wrapper">
                <div class="loader"></div>
            </div>
        </main>
    </div>

    <footer class="player-bar"></footer>

	<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script src="js/app.js"></script>
    <script>
        let currentShuffle = "SHUFFLE_OFF";
        let currentRepeat = "REPEAT_OFF";

        // --- ALIAS POUR RÉTROCOMPATIBILITÉ SVG ---
        // (Évite d'avoir à modifier manuellement tous les boutons dans remotebig.svg)
        window.sendKey = async function(keyName) { if(typeof sendCommand === "function") await sendCommand(keyName); };
        window.sendPreset = async function(id) { if(typeof playPreset === "function") await playPreset(id); };

        // 1. On charge le SVG de manière IMMÉDIATE et FORCÉE
        loadComponent(null, "components/remotebig.svg", "#big-remote-wrapper").then(() => {
            // Dès qu'il a effacé le loader, on met à jour les boutons et les couleurs
            updateBigRemoteUI();
        });

        // 2. Boucle de rafraîchissement locale pour animer Shuffle/Repeat
        setInterval(updateBigRemoteUI, 1000);

        // --- GESTION VISUELLE ---
        function updateBigRemoteUI() {
            // Sécurité si app.js n'a pas encore fini de charger les données du Pi
            if (typeof getSelectedIps !== "function" || !globalData.speakers) return;

            const ips = getSelectedIps();
            if (ips.length === 0) return;
            
            const spk = globalData.speakers[ips[0]];
            if (!spk) return;

            currentShuffle = spk.shuffleSetting || "SHUFFLE_OFF";
            currentRepeat = spk.repeatSetting || "REPEAT_OFF";

            const opActive = "1";        
            const opInactive = "0.3";    

            const logoShuff = document.getElementById('logoShuff');
            const logoRep = document.getElementById('logoRep');
            const logoRepOne = document.getElementById('logoRepOne');

            // Mise à jour de la couleur de l'icône Shuffle
            if (logoShuff) logoShuff.style.opacity = currentShuffle === "SHUFFLE_ON" ? opActive : opInactive;

            // Mise à jour de la couleur de l'icône Repeat
            if (logoRep && logoRepOne) {
                if (currentRepeat === "REPEAT_ALL") {
                    logoRep.style.opacity = opActive;
                    logoRepOne.style.display = "none";
                } else if (currentRepeat === "REPEAT_ONE") {
                    logoRep.style.opacity = opActive;
                    logoRepOne.style.display = "block"; 
                    logoRepOne.style.opacity = opActive;
                } else {
                    logoRep.style.opacity = opInactive;
                    logoRepOne.style.display = "none";  
                }
            }

            // Mise à jour du texte des 6 presets (sans dépasser du bouton)
            for (let i = 1; i <= 6; i++) {
                let presetName = (globalData.presets && globalData.presets[i]) ? globalData.presets[i] : "";
                const svgTextEl = document.getElementById(`preset-text-${i}`);
                if (svgTextEl) {
                    svgTextEl.textContent = presetName.length > 14 ? presetName.substring(0, 13) + "_" : presetName;
                }
            }
        }

        // --- ACTIONS AU CLIC POUR SHUFFLE ET REPEAT ---
        async function toggleShuffle() {
            const targetKey = currentShuffle === "SHUFFLE_ON" ? "SHUFFLE_OFF" : "SHUFFLE_ON";
            if (typeof sendCommand === "function") await sendCommand(targetKey);
        }

        async function toggleRepeat() {
            let targetKey = "REPEAT_OFF";
            if (currentRepeat === "REPEAT_OFF") targetKey = "REPEAT_ALL";
            else if (currentRepeat === "REPEAT_ALL") targetKey = "REPEAT_ONE";
            else if (currentRepeat === "REPEAT_ONE") targetKey = "REPEAT_OFF";
            
            if (typeof sendCommand === "function") await sendCommand(targetKey);
        }
    </script>
</body>
</html>
```
<br>

### `www/tools.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Outils d'Administration</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background: #1e1e1e; color: #fff; }
        .card { background: #2d2d2d; padding: 15px; margin-bottom: 15px; border-radius: 8px; }
        input, select, button { padding: 8px; margin-top: 5px; }
        button { background: #007bff; color: white; border: none; cursor: pointer; border-radius: 4px; }
        iframe { width: 100%; height: 500px; border: 2px solid #555; border-radius: 8px; margin-top: 20px; background: #000; }
    </style>
</head>
<body>
    <nav style="padding: 10px; background-color: #f4f4f4; border-bottom: 1px solid #ccc; margin-bottom: 20px;">
    
        <a href="/" style="margin-right: 15px; color: #333; font-weight: bold; text-decoration: none;">Retour</a>
        
        <a id="lien-soundcork" target="_blank" href="#" style="margin-right: 15px; color: #333; text-decoration: none;">SoundCork</a>
        
        <a id="lien-stockholm" target="_blank" href="#" style="margin-right: 15px; color: #333; text-decoration: none;">Stockholm</a>

        <a id="lien-urlMiniDlna" target="_blank" href="#" style="margin-right: 15px; color: #333; text-decoration: none;">MiniDLNA</a>

        <a href="http://phd.dsmynas.net/sc_tools" target="_blank" style="margin-right: 15px; color: #333; text-decoration: none;">Procédure d'installation</a>

    </nav>

    <script>
        document.addEventListener("DOMContentLoaded", function() {
            // Récupère l'adresse (IP ou domaine) du serveur actuel
            var serveurCourant = window.location.hostname;
            
            // Construit l'URL avec les ports respectifs
            var urlSoundCork = window.location.protocol + "//" + serveurCourant + ":8000/admin/";
            var urlStockholm = window.location.protocol + "//" + serveurCourant + ":8088/";
            var urlMiniDlna = window.location.protocol + "//" + serveurCourant + ":8282/";
            
            // Applique l'URL aux liens
            document.getElementById("lien-soundcork").href = urlSoundCork;
            document.getElementById("lien-stockholm").href = urlStockholm;
            document.getElementById("lien-urlMiniDlna").href = urlMiniDlna;
        });
    </script>

    <h1>🎛️ Outils d'Administration</h1>
    
    <div style="display: flex; gap: 20px;">
        <div style="flex: 1;">
            {% for section, data in config.items() %}
            <div class="card">
                <h3>{{ data.titre }}</h3>
                <form action="/run_tool" method="POST" target="terminal_frame">
                    <input type="hidden" name="section" value="{{ section }}">
                    
                    {% if 'arg1_label' in data %}
                        <label>{{ data.arg1_label }}</label><br>
                        {% if data.arg1_type == 'select' %}
                            <select name="arg1" required>
                                {% for opt in data.arg1_options.split(',') %}
                                    <option value="{{ opt }}">{{ opt }}</option>
                                {% endfor %}
                            </select>
                        {% else %}
                            <input type="text" name="arg1" required>
                        {% endif %}
                        <br><br>
                    {% endif %}
                    
                    {% if 'arg2_label' in data %}
                        <label>{{ data.arg2_label }}</label><br>
                        {% if data.arg2_type == 'select' %}
                            <select name="arg2" required>
                                {% for opt in data.arg2_options.split(',') %}
                                    <option value="{{ opt }}">{{ opt }}</option>
                                {% endfor %}
                            </select>
                        {% else %}
                            <input type="text" name="arg2" required>
                        {% endif %}
                        <br><br>
                    {% endif %}
                    
                    {% if 'arg3_label' in data %}
                        <label>{{ data.arg3_label }}</label><br>
                        {% if data.arg3_type == 'select' %}
                            <select name="arg3" required>
                                {% for opt in data.arg3_options.split(',') %}
                                    <option value="{{ opt }}">{{ opt }}</option>
                                {% endfor %}
                            </select>
                        {% else %}
                            <input type="text" name="arg3" required>
                        {% endif %}
                        <br><br>
                    {% endif %}
                    
                    <button type="submit">Lancer le script</button>
                </form>
            </div>
            {% endfor %}
        </div>
        
        <div style="flex: 1;">
            <h3>Console Interactive</h3>
            <iframe name="terminal_frame" src="about:blank"></iframe>
        </div>
    </div>
</body>
</html>
```
<br>

### `www/upload.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#121212">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoundCork">
    <link rel="apple-touch-icon" href="img/icon-192.png">

    <title>Diffuser Fichier - SoundTouch</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <link rel="stylesheet" href="css/global.css">
    <style>
        .upload-container {
            background-color: var(--bg-elevated);
            padding: 40px 20px;
            border-radius: 12px;
            text-align: center;
            margin-top: 20px;
            border: 2px dashed #333;
            transition: border-color 0.3s, background-color 0.3s;
        }
        .upload-container:hover {
            border-color: var(--spotify-green);
            background-color: var(--bg-highlight);
        }
        .upload-icon {
            font-size: 48px;
            color: var(--text-subdued);
            margin-bottom: 20px;
        }
        .file-input-wrapper {
            position: relative;
            overflow: hidden;
            display: inline-block;
            margin-bottom: 20px;
        }
        .file-input-wrapper input[type=file] {
            font-size: 100px;
            position: absolute;
            left: 0;
            top: 0;
            opacity: 0;
            cursor: pointer;
        }
        .btn-upload {
            background-color: var(--text-base);
            color: black;
            border: none;
            padding: 12px 24px;
            border-radius: 500px;
            font-weight: bold;
            font-size: 16px;
            cursor: pointer;
            transition: transform 0.1s;
        }
        .btn-upload:hover {
            transform: scale(1.05);
            background-color: white;
        }
        .file-name-display {
            font-size: 14px;
            color: var(--spotify-green);
            margin-bottom: 20px;
            font-weight: bold;
            word-break: break-all;
        }
        
        .status-bar { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background-color: #333; color: white; padding: 12px 24px; border-radius: 500px; font-weight: bold; box-shadow: 0 8px 24px rgba(0,0,0,0.5); z-index: 2000; display: none; transition: opacity 0.3s; }
        .status-success { background-color: var(--spotify-green); color: black; }
        .status-error { background-color: #FA243C; color: white; }
        .status-warning { background-color: #FF9900; color: black;}
    </style>
</head>
<body>
    <div id="status-bar" class="status-bar">Notification</div>

    <div class="main-container">
        <div id="mobile-overlay" class="sidebar-overlay" onclick="toggleMobileMenu()"></div>
        <nav class="sidebar"></nav>

        <main class="main-view">
            <div class="top-bar">
                <!-- <div style="display: flex; width: 100%; align-items: center;"> -->
                <div style="display: flex; flex: 1; min-width: 0; align-items: center;">
					<button class="mobile-menu-btn" onclick="toggleMobileMenu(event)">
                        <i class="fas fa-bars"></i>
                    </button>
                    <h2 class="section-title" style="margin: 0; padding-left: 15px;">
                        <i class="fas fa-mobile-alt" style="color: var(--spotify-green); margin-right: 10px;"></i> Diffuser un fichier
                    </h2>
                </div>
                
                <!-- <div class="sources-wrapper" id="sources-wrapper" style="max-width: 150px; width: 100%; margin: 0 15px;"></div> -->
                <div class="remote-wrapper" id="remote-wrapper"></div>
            </div>

            <p style="color: var(--text-subdued); font-size: 15px; margin-bottom: 20px;">
                Sélectionnez un fichier audio (MP3, FLAC, M4A, WAV) depuis votre appareil. Il sera lu instantanément sur l'enceinte sélectionnée.
            </p>

            <div class="upload-container" id="drop-zone">
                <i class="fas fa-cloud-upload-alt upload-icon"></i>
                <div class="file-name-display" id="file-name">Aucun fichier sélectionné</div>
                
                <div class="file-input-wrapper">
                    <button class="btn-upload">Choisir un fichier</button>
                    <input type="file" id="audio-file" accept="audio/*" onchange="updateFileName()">
                </div>
                
                <div style="margin-top: 20px;">
                    <button class="btn-action btn-action-primary" style="width: auto; padding: 12px 30px; font-size: 16px; background-color: rgba(29, 185, 84, 0.1);" onclick="uploadAndPlay()">
                        <i class="fas fa-play-circle"></i> Envoyer et Lire
                    </button>
                </div>
            </div>

        </main>
    </div>

    <footer class="player-bar"></footer>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script src="js/app.js"></script>
    <script>
        function showNotification(msg, type = "warning") {
            const statusBar = document.getElementById('status-bar');
            statusBar.innerText = msg;
            statusBar.className = `status-bar status-${type}`;
            statusBar.style.display = 'block';
            setTimeout(() => { statusBar.style.display = 'none'; }, 4000);
        }

        function updateFileName() {
            const fileInput = document.getElementById('audio-file');
            const fileNameDisplay = document.getElementById('file-name');
            if (fileInput.files.length > 0) {
                fileNameDisplay.textContent = fileInput.files[0].name;
            } else {
                fileNameDisplay.textContent = "Aucun fichier sélectionné";
            }
        }

        async function uploadAndPlay() {
            const fileInput = document.getElementById('audio-file');
            const file = fileInput.files[0];
            
            if (!file) return showNotification("Veuillez d'abord sélectionner un fichier audio.", "error");

            const ips = getSelectedIps(); 
            if (ips.length === 0) return showNotification("Sélectionnez au moins une enceinte active dans le menu.", "error");

            const formData = new FormData();
            formData.append('file', file);
            formData.append('ips', JSON.stringify(ips));

            showNotification("⏳ Transfert du fichier en cours...", "warning");

            try {
                const response = await fetch('/api/upload_play', {
                    method: 'POST',
                    body: formData 
                });
                
                const data = await response.json();
                
                if (data.status === 'ok') {
                    showNotification("✅ Lecture lancée !", "success");
                    setTimeout(fetchState, 1500); 
                } else {
                    showNotification("❌ " + data.message, "error");
                }
            } catch (error) {
                showNotification("❌ Erreur de transfert avec la box.", "error");
            }
        }
    </script>
</body>
</html>
```
<br>


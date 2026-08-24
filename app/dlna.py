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

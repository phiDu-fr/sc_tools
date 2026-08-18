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
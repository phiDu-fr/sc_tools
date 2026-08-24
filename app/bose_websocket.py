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
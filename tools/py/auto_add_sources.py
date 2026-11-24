import os
import glob
import urllib.request
import socket
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ==========================================
# CONFIGURATION FIXE DANS LE CONTENEUR
# ==========================================
# DATA_DIR = "/data"  # Dossier monté dans le docker-compose
DATA_DIR = "/home/pi/soundcork/data"  # Dossier monté sans docker
# PROVIDER_ID = "7"   # 7 = Serveurs DLNA / STORED_MUSIC

def get_speaker_ip():
    """Trouve dynamiquement l'IP d'une enceinte Bose via SSDP, avec une IP de secours."""
    # --- RENSEIGNEZ VOTRE IP CONNUE ICI ---
    FALLBACK_IP = "192.168.1.65" 
    # --------------------------------------
    
    print("🔍 Recherche d'une enceinte SoundTouch sur le réseau...")
    
    msg = (
        'M-SEARCH * HTTP/1.1\r\n'
        'HOST: 239.255.255.250:1900\r\n'
        'ST: ssdp:all\r\n' # Recherche plus large pour contourner les filtres
        'MX: 2\r\n'
        'MAN: "ssdp:discover"\r\n\r\n'
    )
    
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.settimeout(3.0)
    
    # Configuration pour forcer le broadcast sur toutes les interfaces (utile pour Docker)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except Exception:
        pass

    try:
        s.sendto(msg.encode('utf-8'), ('239.255.255.250', 1900))
        while True:
            data, addr = s.recvfrom(65507)
            if b'Bose' in data or b'SoundTouch' in data:
                print(f"   ➔ Enceinte trouvée par SSDP : {addr[0]}")
                return addr[0]
    except socket.timeout:
        print(f"⚠️ Le scan réseau a échoué (blocage Docker probable).")
    finally:
        s.close()
        
    print(f"   ➔ Utilisation de l'IP de secours configurée : {FALLBACK_IP}")
    return FALLBACK_IP

def get_discovered_servers(speaker_ip):
    """Demande à l'enceinte la liste des serveurs DLNA visibles"""
    url = f"http://{speaker_ip}:8090/listMediaServers"
    servers = []
    try:
        print(f"📡 Interrogation de l'enceinte ({speaker_ip})...")
        req = urllib.request.urlopen(url, timeout=5)
        root = ET.fromstring(req.read())
        
        for ms in root.findall('media_server'):
            raw_id = ms.get('id')
            formatted_uuid = f"{raw_id}/0" if not raw_id.endswith("/0") else raw_id
            name = ms.get('friendly_name', 'Unknown DLNA')
            
            servers.append({'name': name, 'uuid': formatted_uuid})
            print(f"   ➔ Vu sur le réseau : {name} ({formatted_uuid})")
            
    except Exception as e:
        print(f"❌ Erreur de communication avec l'enceinte : {e}")
    
    return servers

def sync_sources_to_soundcork(discovered_servers):
    """Injecte les serveurs dans les fichiers Sources.xml de SoundCork"""
    if not discovered_servers:
        print("🤷 Aucun serveur DLNA détecté.")
        return

    xml_files = glob.glob(os.path.join(DATA_DIR, "*", "Sources.xml"))
    if not xml_files:
        print(f"❌ Aucun fichier Sources.xml trouvé dans {DATA_DIR}. Avez-vous retiré le ':ro' du montage Docker ?")
        return

    for file_path in xml_files:
        print(f"\n📂 Mise à jour du fichier : {file_path}")
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            existing_uuids = set()
            max_id = 100000
            
            # Analyse de l'existant
            for source in root.findall('source'):
                src_id = int(source.get('id', '0'))
                if src_id > max_id:
                    max_id = src_id
                
                key_tag = source.find('sourceKey')
                if key_tag is not None and key_tag.get('type') == 'STORED_MUSIC':
                    existing_uuids.add(key_tag.get('account'))
            
            added_count = 0
            for server in discovered_servers:
                if server['uuid'] in existing_uuids:
                    print(f"   ➔ ✔️  Déjà enregistré : {server['name']}")
                    continue
                
                max_id += 1
                new_id = str(max_id)
                now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")
                
                # Construction XML
                new_source = ET.Element("source", id=new_id, displayName=server['name'], secret="", secretType="token")
                ET.SubElement(new_source, "sourceKey", type="STORED_MUSIC", account=server['uuid'])
                ET.SubElement(new_source, "createdOn").text = now_iso
                ET.SubElement(new_source, "updatedOn").text = now_iso
                
                root.append(new_source)
                added_count += 1
                print(f"   ➔ ➕ NOUVEAU ! Ajout de {server['name']} (ID: {new_id})")
            
            if added_count > 0:
                # Sauvegarde (nécessite les droits d'écriture /data au lieu de /data:ro)
                tree.write(file_path, encoding="UTF-8", xml_declaration=True)
                print(f"   ➔ 💾 Enregistrement réussi ({added_count} source(s) ajoutée(s)).")
            else:
                print("   ➔ 🛑 Aucune modification nécessaire.")
                
        except PermissionError:
            print(f" ➔ ❌ ERREUR DE PERMISSION : Impossible de modifier le fichier. Vérifiez que le volume n'est pas monté en 'ro' (Read-Only).")
        except Exception as e:
            print(f" ➔ ❌ Erreur lors du traitement : {e}")

# ==========================================
# EXÉCUTION
# ==========================================
if __name__ == "__main__":
    print("=== SYNCHRONISATION DLNA ===")
    
    SPEAKER_IP = get_speaker_ip()
    
    if not SPEAKER_IP:
        print("❌ Impossible de trouver une enceinte allumée sur le réseau. Abandon.")
        exit(1)
        
    servers = get_discovered_servers(SPEAKER_IP)
    sync_sources_to_soundcork(servers)
    
    print("\n✅ Terminé ! Si un ajout a eu lieu, relancez le conteneur soundcork : 'docker restart soundcork'")
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from zeroconf import Zeroconf, ServiceBrowser
import requests
import time
import re

print("🔎 Détection SoundTouch via Zeroconf + API...\n")

devices = []

class SoundTouchListener:
    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info and info.addresses:
            ip = ".".join(map(str, info.addresses[0]))
            devices.append(ip)
            print(f"➡️  Appareil détecté via mDNS : {ip}")

    def remove_service(self, zeroconf, type, name):
        pass  # pas nécessaire pour ton usage

    def update_service(self, zeroconf, type, name):
        pass  # requis pour éviter le FutureWarning

# Lancer Zeroconf
zeroconf = Zeroconf()
listener = SoundTouchListener()
browser = ServiceBrowser(zeroconf, "_soundtouch._tcp.local.", listener)

# Attendre la découverte
time.sleep(2)
zeroconf.close()

if not devices:
    print("❌ Aucune SoundTouch trouvée via Zeroconf")
    exit(1)

# Fonction d'extraction XML
def extract(tag, xml):
    m = re.search(f"<{tag}>(.*?)</{tag}>", xml)
    return m.group(1) if m else ""

def extract_attr(attr, xml):
    m = re.search(f'{attr}="([^"]+)"', xml)
    return m.group(1) if m else ""

# Interroger chaque enceinte
for ip in devices:
    print(f"\n🔧 Test API sur {ip}...")

    # Attendre que l’API soit prête
    ready = False
    for _ in range(6):
        try:
            r = requests.get(f"http://{ip}:8090/now_playing", timeout=1)
            if r.status_code == 200:
                ready = True
                break
        except:
            pass
        time.sleep(0.2)

    if not ready:
        print("   ⚠️ API non prête après 6 tentatives")
        continue

    # Appel /info
    try:
        xml = requests.get(f"http://{ip}:8090/info", timeout=2).text
    except:
        print("   ⚠️ Impossible d'obtenir /info")
        continue

    # Extraction
    DEVICEID = extract_attr("deviceID", xml)
    NAME = extract("name", xml)
    TYPE = extract("type", xml)
    COMPTE = extract("margeAccountUUID", xml)

    print(f"   Nom       : {NAME}")
    print(f"   Modèle    : {TYPE}")
    print(f"   DeviceID  : {DEVICEID}")
    print(f"   Compte    : {COMPTE}")

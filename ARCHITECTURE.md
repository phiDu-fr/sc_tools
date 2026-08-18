🏗️ Architecture Technique & Spécifications (sc_tools)

Ce document décrit en détail l'architecture logicielle, le flux de données, les protocoles réseau et l'intégration matérielle du projet **sc_tools**.

---

## 1. Vue d'Ensemble du Système

L'application repose sur une architecture hybride **Flask / Eventlet (Socket.IO)** côté backend et **HTML5 / ES6 Vanilla** côté frontend.

```text
  ┌─────────────────────────────────────────────────────────┐
  │                 Interface Client (Web)                  │
  │     (Desktop Browser, Smartphone, Tablette - Port 80)    │
  └───────────▲─────────────────────────────────▲───────────┘
              │ WebSocket / Socket.IO           │ HTTP REST
              ▼                                 ▼
  ┌─────────────────────────────────────────────────────────┐
  │                    Serveur Flask / App                  │
  │  ┌───────────────────────────────────────────────────┐  │
  │  │ Shared State (speakers, server_queues, scheduler)  │  │
  │  └───────────────────────────────────────────────────┘  │
  │                                                         │
  │  [Blueprints Flask]                                     │
  │  ├── soundtouch_bp  <--->  Bose HTTP REST API (8090)     │
  │  ├── dlna_bp        <--->  UPnP/SSDP & Proxy Stream     │
  │  ├── alarm_bp       <--->  APScheduler Cron Jobs        │
  │  ├── podcast_bp     <--->  iTunes API & Local Storage   │
  │  └── rf_dwl_bp      <--->  Radio France GraphQL API     │
  └───────────▲─────────────────────────────────▲───────────┘
              │                                 │
     WS (8080)│                                 │ HTTP Stream / XML
              ▼                                 ▼
┌───────────────────────────┐     ┌───────────────────────────┐
│ Enceintes Bose SoundTouch │     │ Serveurs DLNA / NAS Local │
│ (ST-10, ST-20, SA-5, ...) │     │  (Synology, Plex, etc.)   │
└───────────────────────────┘     └───────────────────────────┘

```

---

## 2. Modules Backend Flask

### 2.1 Point d'Entrée (`app/app.py`)

* Initialise l'application Flask et le serveur Socket.IO (`socketio.init_app(app)`).
* Charge les données de configuration et de persistance JSON.
* Lance les tâches de fond :
* `parse_device_info()` : Analyse du sous-réseau et découverte des enceintes Bose.
* `check_stereo_groups()` : Détection des appariements stéréo SoundTouch 10.
* `scheduler.start()` : Démarrage de l'horloge des alarmes.
* `bose_ws_manager.start_listening(ip)` : Démarrage des threads d'écoute WebSocket native pour chaque enceinte.



### 2.2 Client WebSocket Native Bose (`app/bose_websocket.py`)

Chaque enceinte Bose SoundTouch intègre un serveur WebSocket interne sur le port **8080**.

* **Connexion WebSocket** : `ws://<IP_ENCEINTE>:8080/`
* **En-tête Spécifique** : `Sec-WebSocket-Protocol: gabbo`
* **Mécanisme d'Écoute** :
1. Connexion au démarrage dans un thread `daemon`.
2. Envoi initial d'une requête HTTP pour récupérer l'état (`/nowPlaying`, `/volume`, `/getZone`, `/powerManagement`).
3. Réception passive de tous les événements XML poussés par l'enceinte lors des changements d'état (changement de volume, piste suivante, modification de batterie, état de mise en veille).
4. Parsing de l'arbre XML (`xml.etree.ElementTree`).
5. Mise à jour de la structure globale `speakers[ip]`.
6. Émission d'un événement Socket.IO `bose_update` à tous les clients Web connectés.



### 2.3 Hack "Orion Station" & Proxy Audio (`app/dlna.py` & `app/podcasts.py`)

Les enceintes Bose SoundTouch verrouillent la lecture de flux réseau personnalisés si l'URL n'est pas issue d'un service officiellement partenaire (TuneIn, Spotify).
Pour contourner cette restriction, **sc_tools** exploite l'émulateur du service **Bose Orion Adapter** (`svc-bmx-adapter-orion`).

#### Fonctionnement du Payload Orion :

1. Construction d'une structure de données JSON :
```json
{
    "name": "Nom de la Piste / Radio",
    "imageUrl": "http://<IP_LOCAL>/logo.png",
    "streamUrl": "http://<IP_LOCAL>/api/dlna/stream?url=..."
}

```


2. Encodage du JSON en Base64 (`b64`).
3. Génération d'une URL cible au format Orion :
`http://<IP_LOCAL>:17091/core02/svc-bmx-adapter-orion/prod/orion/station?data=<B64_DATA>`
4. Envoi de l'ordre à l'enceinte Bose via le point d'accès HTTP XML `/select` :
```xml
<?xml version="1.0" encoding="UTF-8"?>
<ContentItem source="LOCAL_INTERNET_RADIO" type="stationurl" location="<ORION_URL>">
    <itemName>Nom de la Station</itemName>
</ContentItem>

```



### 2.4 Gestionnaire DLNA / UPnP

* **SSDP Discovery** : Envoi d'une requête UDP Multicast sur `239.255.255.250:1900` avec le Target Search `urn:schemas-upnp-org:device:MediaServer:1`.
* **Proxy de Streaming (`/api/dlna/stream`)** : Lecture en chunking HTTP (`requests.get(..., stream=True)`) pour ré-émettre le contenu multimédia du NAS vers l'enceinte Bose avec gestion des en-têtes de sous-requête `Range` (nécessaire pour la recherche temporelle dans un morceau).
* **Moteur de File d'Attente (`server_queues`)** : Suivi de l'index de lecture sur l'enceinte. Lors de la réception du signal de fin de piste via WebSocket (`STOP_STATE` ou `INVALID_SOURCE`), un thread déclenche automatiquement la piste suivante (`play_next_in_queue`).

### 2.5 Téléchargeur Radio France (`app/radiofrance_downloader/`)

* **Client GraphQL** : Requêtes vers `https://openapi.radiofrance.fr/v1/graphql` avec l'en-tête de sécurité `x-token`.
* **Récupération Paginée** : Paginator par curseurs (`after`) pour extraire l'exhaustivité des émissions (`shows`) et épisodes (`diffusionsOfShowByUrl`).
* **Exécution Asynchrone** : Téléchargement délégué aux tâches de fond FastAPI/Starlette (`BackgroundTasks`) avec gestion des exceptions pour éviter le blocage du thread Web principal.

---

## 3. Modèle de Données & Persistance

Les données utilisateur sont stockées dans le dossier local `data/` sous forme de fichiers JSON :

### 3.1 `alarms.json`

```json
[
    {
        "ip": "192.168.1.50",
        "hour": 7,
        "minute": 30,
        "days": "1,2,3,4,5",
        "preset": "PRESET_1"
    }
]

```

### 3.2 Structure de l'État en Mémoire (`shared.speakers`)

```python
speakers = {
    "192.168.1.50": {
        "deviceID": "000C8A112233",
        "name": "Cuisine",
        "type": "SoundTouch 10",
        "state": "ON",
        "volume": 25,
        "source": "LOCAL_INTERNET_RADIO",
        "track": "France Inter",
        "artist": "Le 7/10",
        "album": "",
        "cover": "http://...",
        "is_stereo_master": False,
        "is_stereo_slave": False,
        "battery_capable": False,
        "running_on_battery": False,
        "battery_percent": 0
    }
}

```

---

## 4. Architecture Réseau & Ports Utilisés

| Port | Protocole | Service / Rôle |
| --- | --- | --- |
| **80** | HTTP / WS | Serveur Flask & Socket.IO (Interface Web principale) |
| **8090** | HTTP | API REST XML Native des enceintes Bose SoundTouch |
| **8080** | WebSocket | Notifications push XML en temps réel des enceintes Bose |
| **1900** | UDP Multicast | SSDP Discovery UPnP / DLNA |
| **17091** | HTTP | SoundCork / Orion Bridge Local |
| """ |  |  |


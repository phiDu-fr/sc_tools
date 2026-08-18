# 📖 Documentation des API REST (sc_tools)

Ce document détaille l'ensemble des points d'entrée (endpoints) de l'API REST exposée par l'application **sc_tools**.

---

## Sommaire
1. [Contrôle des Enceintes Bose (`soundtouch_bp`)](#1-contrôle-des-enceintes-bose)
2. [Gestion DLNA & UPnP (`dlna_bp`)](#2-gestion-dlna--upnp)
3. [Podcasts & Fichiers (`podcast_bp`)](#3-podcasts--fichiers)
4. [Alarmes & Réveils (`alarm_bp`)](#4-alarmes--réveils)
5. [Radio France Downloader (`rf_dwl_bp`)](#5-radio-france-downloader)
6. [Outils & Administration (`tools_bp`)](#6-outils--administration)

---

## 1. Contrôle des Enceintes Bose

### GET `/api/speakers`
Retourne la liste et l'état détaillé en temps réel de toutes les enceintes Bose détectées sur le réseau.

* **Méthode** : `GET`
* **Réponse exemple (200 OK)** :
```json
{
  "192.168.1.50": {
    "artist": "France Inter",
    "battery_capable": false,
    "deviceID": "000C8A112233",
    "name": "Salon",
    "playStatus": "PLAY_STATE",
    "source": "LOCAL_INTERNET_RADIO",
    "state": "ON",
    "track": "Le 7/10",
    "type": "SoundTouch 20",
    "volume": 20
  }
}

```

---

### POST `/api/volume`

Ajuste le volume sonore d'une ou plusieurs enceintes.

* **Méthode** : `POST`
* **Corps de la requête (JSON)** :

```json
{
  "ips": ["192.168.1.50"],
  "volume": 30
}

```

* **Réponse exemple (200 OK)** : `{"status": "success"}`

---

### POST `/api/key`

Simule l'appui sur une touche de la télécommande physique Bose.

* **Méthode** : `POST`
* **Corps de la requête (JSON)** :

```json
{
  "ip": "192.168.1.50",
  "key": "PRESET_1"
}

```

* **Touches valides** : `POWER`, `MUTE`, `VOLUME_UP`, `VOLUME_DOWN`, `PRESET_1` à `PRESET_6`, `PLAY`, `PAUSE`, `STOP`, `NEXT_TRACK`, `PREV_TRACK`, `AUX_INPUT`.

---

### POST `/api/zone/master`

Crée un groupe Multi-room en définissant une enceinte Master et des enceintes Slaves.

* **Méthode** : `POST`
* **Corps de la requête (JSON)** :

```json
{
  "master_ip": "192.168.1.50",
  "slaves_ips": ["192.168.1.51"]
}

```

---

## 2. Gestion DLNA & UPnP

### GET `/api/dlna/servers`

Recherche et liste les serveurs multimédia DLNA actifs sur le réseau via SSDP.

* **Méthode** : `GET`
* **Réponse exemple (200 OK)** :

```json
[
  {
    "name": "Synology DiskStation",
    "udn": "uuid:12345678-1234-1234-1234-123456789abc"
  }
]

```

---

### GET `/api/dlna/browse`

Parcourt le contenu d'un dossier DLNA spécifique.

* **Méthode** : `GET`
* **Paramètres URL** :
* `udn` : UDN du serveur DLNA.
* `id` : ID de l'objet/dossier à parcourir (défaut : `"0"` pour la racine).



---

### POST `/api/dlna/search`

Effectue une recherche de fichiers audio sur le serveur DLNA.

* **Méthode** : `POST`
* **Corps de la requête (JSON)** :

```json
{
  "udn": "uuid:12345678-1234-1234-1234-123456789abc",
  "query": "Daft Punk",
  "type": "all"
}

```

---

### GET `/api/dlna/stream`

Proxy de streaming audio pour relayer le fichier multimédia du serveur DLNA vers l'enceinte Bose.

* **Méthode** : `GET`
* **Paramètres URL** :
* `url` : URL directe du fichier sur le serveur DLNA.



---

### POST `/api/queue/play`

Définit et lance une nouvelle file d'attente de lecture sur les enceintes ciblées.

* **Méthode** : `POST`
* **Corps de la requête (JSON)** :

```json
{
  "ips": ["192.168.1.50"],
  "tracks": [
    {
      "title": "Track 1",
      "artist": "Artist A",
      "album": "Album X",
      "url": "[http://192.168.1.100:50001/music/1.mp3](http://192.168.1.100:50001/music/1.mp3)",
      "cover": "[http://192.168.1.100:50001/cover/1.jpg](http://192.168.1.100:50001/cover/1.jpg)"
    }
  ],
  "index": 0
}

```

---

## 3. Podcasts & Fichiers

### GET `/api/podcasts/search`

Recherche des épisodes de podcasts via l'API iTunes / Apple Podcasts.

* **Méthode** : `GET`
* **Paramètres URL** :
* `q` : Terme de recherche.
* `country` : Code pays (par défaut : `"fr"`).



---

### POST `/api/play_podcast`

Déclenche la lecture d'un podcast externe sur les enceintes cibles.

* **Méthode** : `POST`
* **Corps de la requête (JSON)** :

```json
{
  "ips": ["192.168.1.50"],
  "name": "Affaires Sensibles",
  "url": "[https://podcasts.radiofrance.fr/](https://podcasts.radiofrance.fr/)..."
}

```

---

### POST `/api/upload_play`

Téléverse un fichier audio local (MP3, AAC) et le diffuse immédiatement sur les enceintes sélectionnées.

* **Méthode** : `POST` (`multipart/form-data`)
* **Champs** :
* `file` : Fichier binaire audio.
* `ips` : Tableau JSON sérialisé d'IPs d'enceintes (ex: `["192.168.1.50"]`).



---

## 4. Alarmes & Réveils

### GET `/api/alarms`

Récupère la liste de toutes les alarmes programmées.

* **Méthode** : `GET`
* **Réponse exemple (200 OK)** :

```json
[
  {
    "ip": "192.168.1.50",
    "hour": 7,
    "minute": 0,
    "days": "1,2,3,4,5",
    "preset": "PRESET_1"
  }
]

```

---

### POST `/api/alarms`

Ajoute une nouvelle alarme programmée.

* **Méthode** : `POST`
* **Corps de la requête (JSON)** :

```json
{
  "ip": "192.168.1.50",
  "hour": 7,
  "minute": 15,
  "days": "1,2,3,4,5",
  "preset": "PRESET_1"
}

```

---

### DELETE `/api/alarms`

Supprime une alarme par son index dans la liste.

* **Méthode** : `DELETE`
* **Paramètres URL** :
* `index` : Index numérique (ex: `0`).



---

## 5. Radio France Downloader

### GET `/api/rf/shows`

Recherche une émission de radio sur la plateforme Radio France.

* **Méthode** : `GET`
* **Paramètres URL** :
* `query` : Mots-clés.
* `station` : Code station (optionnel, ex: `FRANCEINTER`, `FRANCECULTURE`).



---

### POST `/api/rf/download`

Planifie le téléchargement des $N$ derniers épisodes d'une émission en arrière-plan.

* **Méthode** : `POST`
* **Paramètres URL** :
* `show_url` : URL de l'émission Radio France.
* `latest_n` : Nombre d'épisodes à télécharger (défaut : 1).



---

### GET `/api/rf/downloads`

Liste l'ensemble des podcasts Radio France déjà téléchargés localement sur le disque.

* **Méthode** : `GET`

---

## 6. Outils & Administration

### GET `/api/tools/network_info`

Retourne la configuration réseau du serveur hôte (IP, sous-réseau, adresses MAC).

* **Méthode** : `GET`

---

### POST `/api/tools/rescan`

Relance un balayage complet du réseau local pour redécouvrir les enceintes Bose et les serveurs DLNA.

* **Méthode** : `POST`

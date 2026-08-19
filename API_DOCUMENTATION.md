# 📖 Documentation des API REST (sc_tools)

Ce document détaille l'ensemble des points d'entrée (endpoints) de l'API REST exposée par l'application **sc_tools**.


---

## Contrôle des Enceintes Bose

Voici la documentation de l'architecture et du rôle de chaque API du projet SC_TOOLS, structurée par modules (Blueprints Flask) pour garantir la séparation des responsabilités.
### 1. Module principal "SoundTouch" (Gestion matérielle et contrôle)
Ce module s'occupe de la communication avec les enceintes Bose, de la récupération d'état, et de la simulation des touches.
* **`GET /api/data`** : Retourne toutes les données globales, incluant l'état de toutes les enceintes découvertes, les presets, et la liste des webradios enregistrées. Cette route initie également un téléchargement en tâche de fond (lazy healing) pour les logos manquants.
* **`POST /api/poll`** : Force le rafraîchissement manuel de l'état d'une enceinte spécifique (via requête HTTP) et relance l'écoute de son flux WebSocket.
* **`POST /api/create_zone`** : Crée une zone de lecture multiroom synchronisée en définissant une enceinte "maître" et des enceintes "membres".
* **`POST /api/create_stereo`** : Jumelle 2 enceintes ST10 en stéréo.
* **`POST /api/play_preset`** : Joue un preset configuré (1 à 6) sur les enceintes ciblées en envoyant une commande XML native.

### 2. Module "Alarmes" (Gestion des réveils)
Gère la planification et le déclenchement musical programmé.
* **`GET /api/alarms`** : Lit et retourne la liste des alarmes configurées depuis un fichier JSON.
* **`POST /api/alarms`** : Crée une nouvelle alarme, l'enregistre, et la synchronise en mémoire avec le planificateur `APScheduler`.
* **`DELETE /api/alarms`** : Supprime une alarme spécifique de la base de données via son index et met à jour le planificateur.

### 3. Module "DLNA" (Le contournement de l'erreur 1614 et proxy)
Ce blueprint s'occupe de la navigation dans la bibliothèque musicale et du routage audio avancé.
* **`GET /api/dlna/servers`** : Lance une détection SSDP sur le réseau local pour découvrir les serveurs DLNA/UPnP disponibles.
* **`GET /api/dlna/browse` & `POST /api/dlna/search**` : Permettent de lister le contenu d'un dossier DLNA ou de lancer une requête de recherche native (titre, artiste, album) sur le serveur UPnP local.
* **`/api/dlna/stream`** : Il s'agit du proxy audio. Il aspire les flux externes et les redistribue pour contourner les limitations de l'enceinte.
* **`POST /api/queue/play`**, **`POST /api/queue/control`**, **`GET /api/queue/status`** : Ces routes gèrent un lecteur musical virtuel (file d'attente locale). Elles gèrent la piste en cours, l'index, le mode aléatoire et la répétition lorsque l'audio passe par le proxy.
* **`GET /api/upnp/servers`**, **`POST /api/upnp/navigate`**, **`POST /api/upnp/search`** : Des requêtes similaires aux routes DLNA, mais communiquant de manière directe avec le NAS ou via l'API native `listMediaServers` de Bose.
* **`POST /api/upnp/play`** : Implémente le "Smart Skipper". Cette API déclenche la lecture UPNP d'un dossier entier pour éviter un crash Bose (Erreur 1614), puis simule programmatiquement plusieurs appuis sur "Suivant" pour atteindre la piste voulue et garantir une lecture Gapless.

### 4. Module "Podcasts" (Intégration locale et Apple)
Permet de rechercher et de lire des diffusions asynchrones.
* **`GET /api/podcasts/search`** : Interroge l'API Apple iTunes Podcasts pour trouver des émissions.
* **`POST /api/play_podcast`** : Télécharge un podcast depuis l'URL fournie vers un fichier local temporaire (`podcast.mp3`) et initie sa lecture via l'URL proxy.
* **`GET /api/local_rf_downloads`** : Liste tous les podcasts de Radio France déjà téléchargés et stockés localement sur le Raspberry.
* **`POST /api/play_local_rf`** : Commence la lecture d'un fichier mp3 Radio France localement stocké via le Hack Orion.
* **`POST /api/delete_local_rf`** : Efface physiquement un fichier podcast local de l'espace de stockage.

### 5. Module "Radios" (Webradios & Métadonnées)
Gère l'accès aux stations externes et aux métadonnées.
* **`GET /api/radios/search`** : Effectue une recherche de webradios via l'API communautaire "Radio-Browser".
* **`POST /api/play_radio`** : Démarre la diffusion d'une radio spécifiée par son UUID "Radio-Browser" directement sur l'enceinte Bose.
* **`POST /api/radios/save`** : Sauvegarde la liste personnalisée des radios (favoris) dans un fichier pour persistance.
* **`GET /api/radios/rf_test`** : Interroge l'API GraphQL officielle de Radio France pour récupérer les métadonnées (titre et description) de l'émission diffusée en temps réel.

### 6. Module "Radio France Downloader" (Aspiration asynchrone)
Spécialisé dans le téléchargement natif de podcasts Radio France via leur API.
* **`GET /api/rf/config-check`** : Confirme que la clé de l'API Radio France est configurée et que le dossier d'enregistrement est accessible.
* **`GET /api/rf/shows`** : Cherche et retourne la liste des émissions disponibles chez Radio France à partir d'un mot-clé ou d'une station spécifique.
* **`POST /api/rf/download`** : Déclenche le téléchargement du (ou des) dernier(s) épisode(s) d'une émission ciblée. Le téléchargement s'exécute silencieusement en arrière-plan via un `Thread` Python pour ne pas bloquer l'application.
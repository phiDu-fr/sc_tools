
**Contexte du projet :**
Je développe une application web de contrôle pour enceintes Bose SoundTouch.

* **Backend :** Python (Flask) tournant dans un conteneur **Docker**.
* **Frontend :** HTML/CSS/JS (Vanilla) communiquant avec le backend via des appels API REST (`/api/data`).
* **Écosystème :** Le backend interroge les enceintes via leur API XML locale (port 8090) pour récupérer l'état (`nowPlaying`) et les présélections (`presets`).

**Le problème à résoudre :**
Lorsque l'enceinte lit une Web Radio (sources `LOCAL_INTERNET_RADIO` ou `RADIO_BROWSER`), l'API Bose ne renvoie souvent aucune pochette (`art`), ou l'API de Radio-Browser renvoie des images manquantes lorsqu'on l'interroge par UUID. Le frontend affiche donc des pochettes vides ou des icônes génériques.

**L'objectif :**
Je veux mettre en place un système de "Proxy de Logos" côté Backend. Le backend doit intercepter les radios en cours de lecture ou dans les présélections, chercher un logo de bonne qualité sur l'API publique de *Radio-Browser*, le télécharger localement dans le conteneur Docker, et renvoyer l'URL locale au frontend pour un affichage instantané.

**Contraintes techniques (Très important) :**

1. **Docker :** Le backend télécharge les images dans `/www/img/radios/` (dossier mappé dans le `docker-compose.yml`). Flask doit exposer ce dossier via une route `send_from_directory` pour que le navigateur puisse charger les images.
2. **Stabilité XML :** Dans la fonction qui lit le XML Bose (`update_speaker_state`), l'interception du logo ne doit **jamais** faire planter l'extraction des balises `<time>` (elapsed/total). Un bloc `try/except` strict est requis.
3. **Recherche agressive :** Si la radio vient de `RADIO_BROWSER`, chercher l'image par son UUID. Si ça échoue ou si c'est `LOCAL_INTERNET_RADIO`, chercher l'image en utilisant le nom propre de la radio (ex: "France Inter").
4. **Cache :** Ne pas requêter l'API externe en boucle. Maintenir un cache JSON local (`radio_logos_cache.json`).

---

**Plan d'implémentation attendu (Étape par Étape) :**

**Étape 1 : Le serveur Flask (Exposition des fichiers)**
Fournis-moi le code exact à ajouter dans mon fichier principal Flask pour exposer le dossier `/www/img/radios/` au frontend web.

**Étape 2 : Le Gestionnaire de Cache (`soundtouch_api.py`)**
Rédige la fonction `get_radio_logo(source, identifier, name)` qui va gérer le dictionnaire de cache en mémoire, la sauvegarde en fichier JSON, et le téléchargement des images (`.png` ou `.jpg`) depuis `radio-browser.info`. Inclus un fallback vers une image générique (`/www/img/generic-radio.jpg`).

**Étape 3 : L'Interception (Backend)**
Dans mon fichier `soundtouch_api.py`, montre-moi exactement comment injecter l'appel à `get_radio_logo` de manière sécurisée dans :

* La fonction `update_speaker_state()` (lors de la lecture d'une radio).
* La fonction `get_presets()` (attention : la valeur du dictionnaire pour un preset devra passer d'une simple `String` à un objet `{"name": "...", "source": "...", "image": "..."}`).

**Étape 4 : L'Affichage (Frontend JS)**
Dans mon fichier `app.js`, comment dois-je adapter ma fonction de rendu :

* Pour lire le nouvel objet JSON des présélections (pour éviter d'afficher `[object Object]`).
* Pour remplacer mes icônes FontAwesome (`<i class="fas fa-broadcast-tower"></i>`) par de véritables balises `<img src="...">` dans ma grille de favoris radio et mes résultats de recherche.

**Déroulement :** Je vais te fournir mes fichiers 
`soundtouch_api.py`, `radios.py`, `app.js`, et `radios.html` dans les messages suivants. Tu me guideras ensuite pas à pas en respectant ce cahier des charges. As-tu bien compris l'architecture et les contraintes ?
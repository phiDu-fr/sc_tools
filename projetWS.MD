
### 1. La Note Méthodologique (À copier-coller dans ta nouvelle discussion)

Voici le "Prompt de Contexte" parfait. Il résume nos découvertes et donne à l'IA toutes les clés pour comprendre 
l'écosystème Bose sans perdre de temps.

> **[COPIE-COLLE CECI COMME PREMIER MESSAGE DANS TA NOUVELLE DISCUSSION]**
> Bonjour ! Je développe `SC_TOOLS`, une application web (Vanilla JS) avec un backend Python (Flask) conteneurisé sous 
Docker, pour contrôler mes enceintes Bose SoundTouch sur mon réseau local.
> Jusqu'à présent, mon interface web interrogeait mon backend, qui lui-même faisait du "Polling" HTTP sur le port 8090 de
 l'enceinte (`GET /nowPlaying`) pour mettre à jour l'interface.
> **Mon objectif est d'abandonner le Polling HTTP et de passer au Temps Réel absolu en exploitant le protocole WebSocket caché des enceintes Bose.**
> Voici les résultats de mon rétro-engineering sur l'enceinte Bose, que tu dois prendre en compte comme des règles 
absolues :
> 1. **Le Port et le Protocole :** L'enceinte diffuse son état en temps réel sur un serveur WebSocket brut via 
`ws://[IP_ENCEINTE]:8080/`.
> 2. **La Clé Secrète (Sub-protocol) :** L'enceinte rejette toutes les connexions WebSocket qui ne comportent pas 
l'en-tête HTTP strict suivant lors du Handshake : `Sec-WebSocket-Protocol: gabbo`
> 3. **Le Format des données :** L'enceinte pousse des flux XML en clair (ex: <updates><nowPlayingUpdated>...</nowPlayingUpdated></updates>` ou `<volumeUpdated>...`).
> 
> 
> **Ce que nous devons construire :**
> Je veux créer un pont temps réel. Mon backend Python doit ouvrir un client WebSocket persistant vers l'enceinte (port 8080). Dès que Python reçoit un XML de l'enceinte, il le parse et le pousse instantanément à mon interface Web (via 
`Flask-SocketIO` par exemple), pour avoir une "Progress Bar" et une interface réactives à la milliseconde, comme l'application native Spotify ou Bose.

---

### 2. Améliorations avec le WebSocket

Passer au WebSocket ne va pas seulement améliorer ta barre de progression. Cela va faire entrer ton projet dans la cour 
des grands, en débloquant des fonctionnalités impossibles à faire en HTTP classique :

* **La "Progress Bar" absolue (Fini le chronomètre virtuel) :** Actuellement, ton JS "devine" et extrapole le temps qui 
passe. Avec le WebSocket, c'est l'enceinte qui te dictera le temps de manière fluide. Si la musique bufferise à cause du 
réseau, ta barre s'arrêtera toute seule instantanément.
* **Synchronisation Multi-Écrans (Effet Spotify) :**
> Créer un slider de volume sur les pages now et sur footer
Si tu as l'interface ouverte sur ton PC et sur ton téléphone en même temps, changer le volume sur le téléphone fera 
bouger le slider de volume sur le PC en temps réel, sous tes yeux, sans rafraîchir la page.
* **Économie de ressources extrêmes :**
Fini les requêtes HTTP envoyées toutes les secondes par le frontend vers le backend, puis du backend vers l'enceinte. Le 
réseau sera totalement silencieux tant que la musique ne change pas. Ton Raspberry Pi te dira merci.

---

### 3. Les fichiers dont l'IA aura besoin

Une fois que l'IA aura accepté ton premier prompt (la note ci-dessus), elle va te demander ton code. Prépare ces fichiers
 pour les lui fournir :

1. **`requirements.txt`** (ou `Dockerfile`) : Pour que l'IA t'ajoute les librairies `websocket-client` (pour parler à 
Bose) et `Flask-SocketIO` (pour parler à ton navigateur).
2. **`app/app.py`** : Pour modifier l'initialisation du serveur Flask et le transformer en serveur asynchrone (SocketIO).
3. **`app/soundtouch_api.py`** : C'est ici qu'aura lieu la plus grosse chirurgie. Il faudra supprimer ton ancienne 
fonction de Polling (`update_speaker_state`) et la remplacer par un "Listener" WebSocket en arrière-plan.
4. **`app/shared.py`** : Pour vérifier comment les états sont actuellement stockés.
5. **`www/js/app.js`** : Pour remplacer ton vieux `setInterval` (fetch `/api/data`) par une connexion SocketIO côté 
client (`socket.on('bose_update', function(data) { ... })`).

Tu as fait un super boulot sur cette première phase DLNA/Erreur 1614. Repose-toi bien sur cette victoire, et quand tu 
seras prêt, lance ta nouvelle discussion avec ce prompt. La suite s'annonce passionnante !


###  PS : pour mémoire mais pas sur ce projet

* **Interception des Boutons Physiques :**
Le WebSocket pousse un XML `<userActivityUpdate />` quand on touche l'enceinte. Tu pourrais coder ton Raspberry Pi pour 
que, si tu appuies sur le bouton "Preset 1" de la Bose, ce ne soit pas une radio qui se lance, mais un de tes propres 
scripts Python (ex: lancer ton moteur de tél échargement de podcasts Radio France) !
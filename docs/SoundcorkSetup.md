   Installation Soundcork body { font-family: Arial, sans-serif; max-width: 900px; margin: 20px auto; padding: 0 20px; line-height: 1.6; color: #333; } h1, h2, h3, h4 { color: #0056b3; } ul { margin-bottom: 15px; } /\* --- Nouveaux styles pour simplifier les blocs de code --- \*/ .code-container { position: relative; margin-bottom: 25px; } pre.code-block { background-color: #f4f4f9; border: 1px solid #ddd; border-radius: 8px; padding: 45px 15px 15px 15px; /\* Espace en haut pour le bouton \*/ font-family: 'Courier New', Courier, monospace; color: #333; overflow-x: auto; white-space: pre-wrap; /\* Permet le retour à la ligne auto \*/ margin: 0; } .controls { position: absolute; top: 8px; right: 8px; display: flex; align-items: center; } button.copy-btn { padding: 6px 12px; background-color: #007BFF; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 0.85em; transition: background-color 0.2s; } button.copy-btn:hover { background-color: #0056b3; } .msg-success { color: green; margin-right: 10px; font-size: 0.85em; font-weight: bold; opacity: 0; transition: opacity 0.3s; } .msg-success.show { opacity: 1; } .commande-inline { background-color: #eee; padding: 2px 6px; font-family: 'Courier New', Courier, monospace; border-radius: 4px; color: #d14; }

# Installer Soundcork et soundcork-stockholm-app et quelques outils sur un Raspberry (3B+ ou Zero 2 W mini)

_Pour pallier le shutdown Soundtouch du 6 mai 2026._

**Note :** Le Raspberry Zero 2 W mini fonctionne très bien **sans soundcork-stockholm-app**.

---

## Installation de base

#### Matériel :

-   Raspberry Zero 2 W minimum, Raspberry Pi 3B+ conseillé
-   Carte micro SD 16 Go minimum classe 10 ou SSD interface USB
-   Carte RJ45 dans le cas de branchement filaire
-   Câble micro USB pour alimentation électrique, à brancher sur port USB de la box/routeur ou sur alimentation officielle Raspberry

#### Logiciel :

-   Télécharger et installer sur PC [Raspberry Pi Imager](https://downloads.raspberrypi.com/imager/imager_latest.exe)
    -   Appareil : Raspberry Pi 3
    -   OS : Raspberry Pi OS (other)
        -   Raspberry Pi OS Lite (64 bits)
    -   Stockage : Carte SD 
    -   Nom d'hôte : vide
    -   Utilisateur : pi ; mot de passe : pi

Puis :

-   Installer sur PC Putty ou Kitty (mieux) [Lien KiTTY](https://www.fosshub.com/KiTTY.html?dwl=kitty_portable-0.76.1.13.exe)
-   Mettre à jour l'OS :

sudo apt update && sudo apt upgrade -y

### Installer des applis

-   Installer sc\_tools :

cd $HOME  
curl -o sc\_tools.latest.7z http://phd.dsmynas.net/sc\_tools/sc\_tools.latest.7z  
7z x sc\_tools.latest.7z -o$HOME/sc\_tools/  
rm sc\_tools.latest.7z  
find ./sc\_tools/ -type f -exec chmod 664 {} +  
find ./sc\_tools/ -type f -name "\*.sh" -exec chmod 775 {} +  
find ./sc\_tools/ -type d -exec chmod 775 {} +

-   Pour le Rapberry Pi zero 2W :

sudo  ~/sc\_tools/tools/swapRpiZero2.sh

-   Installation de docker :

curl -fsSL https://get.docker.com -o get-docker.sh  
sudo sh get-docker.sh  
sudo usermod -aG docker $USER  
newgrp docker  
sudo tee /etc/docker/daemon.json > /dev/null << 'EOF'  
{  
  "dns": \["8.8.8.8", "1.1.1.1"\]  
}  
EOF  
sudo systemctl restart docker

-   Paquets à installer :

sudo apt-get install $(cat ~/sc\_tools/docs/paquets\_a\_installer.txt) -y  
sudo apt-get autoremove --purge -y  
  
\# Arret du serveur web (pas utile)  
sudo systemctl stop nginx  
sudo systemctl disable nginx  
  
\# Arret du serveur multimedia (si pas de SSD USB connecté)  
sudo systemctl stop minidlna.service  
sudo systemctl disable minidlna.service

-   Alias :

if ! grep -q "alias ll='ls -la'" ~/.bashrc; then  
    echo "alias ll='ls -la'" >> ~/.bashrc  
fi  
source ./.bashrc

### Samba

sudo cp /etc/samba/smb.conf /etc/samba/smb.conf.bak 2>/dev/null || true  
sudo tee /etc/samba/smb.conf > /dev/null << 'EOF'  
\[global\]  
deadtime = 15  
disable netbios = Yes  
disable spoolss = Yes  
dns proxy = No  
load printers = No  
logging = file  
map to guest = Bad User  
max log size = 1000  
printcap name = /dev/null  
security = USER  
server min protocol = SMB2  
server role = standalone server  
smb ports = 445  
socket options = TCP\_NODELAY IPTOS\_LOWDELAY  
idmap config \* : backend = tdb  
posix locking = No  
printing = bsd  
strict locking = No  
use sendfile = Yes  
veto files = /.git/node\_modules/.cache/  
  
\[pi\]  
create mask = 0777  
directory mask = 0777  
force user = pi  
guest ok = Yes  
level2 oplocks = No  
oplocks = No  
path = /home/pi  
read only = No  
EOF

-   Utilisateur et démarrage samba :

(echo "pi"; echo "pi") | sudo smbpasswd -s -a pi  
sudo systemctl restart smbd

### Installer soundcork et soundcork-stockholm-app

-   Clonage des git :

cd $HOME && git clone https://github.com/deborahgu/soundcork.git  
git clone https://github.com/krahl/soundcork-stockholm-app.git

-   Configurations par défaut :

cd ~/sc\_tools/docs && find . -type f -name "\*.etalon" -exec cp --parents {} ~/ \\; && cd

-   Recherche journalière de mise à jour (ajouter la ligne dans crontab) :

( crontab -l ; echo "0 3 \* \* \* /home/pi/sc\_tools/update/updater.sh" ) | crontab -

-   Changer le nom du Raspberry en soundcork :

sudo raspi-config nonint do\_hostname soundcork

---

-   Arrêter wifi et BlueTooth :

echo "dtoverlay=disable-bt" | sudo tee -a /boot/firmware/config.txt  
echo "dtoverlay=disable-wifi" | sudo tee -a /boot/firmware/config.txt  
echo "Effectif au prochain démarrage"

-   Modifier les configurations avec les adresses ip locales :

~/sc\_tools/tools/change\_cfg.sh  
~/sc\_tools/tools/change\_ip.sh

---

## Enceintes

-   Il faut rooter au moins une enceinte :

-   Méthode logicielle [voir plus bas](#root)
-   Méthode matérielle :
    
    _Si possible, l'enceinte la plus utilisée.  
    Certaines machines ne sont pas rootables ainsi ex: Wireless Link adapter (WLA), ..._
    

-   C'est un état provisoire afin de récupérer le fichier Sources.xml
-   Brancher une clé USB à formater.  
    Cette clé ne doit contenir qu'un seul fichier vide 'remote\_services'.  
    Connecter la clé dans le port USB de l'enceinte au préalable.

~/sc\_tools/tools/create\_remote\_services.sh

-   Débranchez l'enceinte du secteur, attendez 2 mn, rebranchez, attendez 3 à 4mn.

**Elles doivent toutes être allumée et connectées au réseau (filaire ou wifi).**

-   Configuration des enceintes :
    -   Remplacer les serveurs Bose par soundcork local sur les enceintes
    -   Création de la base de données soundcork
    -   Vérification de la base de données soundcork  
        **Bien lire le compte rendu final**

~/sc\_tools/tools/change\_marge.sh  
~/sc\_tools/tools/create\_data.sh  
~/sc\_tools/tools/control\_data.sh

-   S'il y a plusieurs comptes, en choisir 1 (sous la forme 7654321 - soundcork y tient) :
    -   Remplacer sur les enceintes pour qu'elles aient le même compte
    -   Remplacer le compte propre à chaque site sur toutes les enceintes étrangères au compte choisi :

~/sc\_tools/tools/change\_accountId.sh

-   Relancer création et vérification :  
    jusqu'au message : **Toutes les enceintes utilisent le même margeAccountUUID**  
    ~/sc\_tools/tools/create\_data.sh  
    ~/sc\_tools/tools/control\_data.sh

### Quand tout est correct, un dossier /home/pi/soundcork/dataX est créé

-   Renommer :

mv ~/soundcork/dataX ~/soundcork/data

---

## Lancement des applis

#### Mise en route sans soundcork-stockholm-app

**Pour Raspberry Zero 2 W (pas assez de RAM)**

cd ~/soundcork  
docker compose up -d --build  # -d pour l'avoir en deamon  
docker compose stop           # pour garder de la puissance pour la suite  
  
cd ~/sc\_tools  
docker compose up -d --build   
  
cd ~/soundcork  
docker compose start

#### Mise en route avec soundcork-stockholm-app

cd ~/soundcork  
docker compose up -d --build  # -d pour l'avoir en deamon  
docker compose stop           # pour garder de la puissance pour la suite  
  
cd ~/sc\_tools  
docker compose up -d --build   
docker compose stop           # pour garder de la puissance pour la suite  
  
cd ~/soundcork-stockholm-app  
curl -o ~/soundcork-stockholm-app/stockholm\_zip/stockholm.zip http://phd.dsmynas.net/sc\_tools/stockholm.zip  
docker compose -f docker-compose.yml -f docker-compose.build.yml up --build -d   
  
cd ~/soundcork  
docker compose start  
cd ~/sc\_tools  
docker compose start  
~/sc\_tools/tools/docker\_menage.sh

---

## Utilisation

Maintenant tout est prêt le Raspberry doit tourner en permanence.

-   Sur un navigateur :
    -   Etat des enceintes : [http://soundcork:8000/admin](http://soundcork:8000/admin)
    -   MiniApp pour faire des manips simples : [http://soundcork:8000](http://soundcork:8000/)
    -   L'appli Bose SoundTouch complète : [http://soundcork:8088](http://soundcork:8088/)
    -   Télécommande globale : [http://soundcork](http://soundcork/)

**Conseil :** Utilisez [http://soundcork](http://soundcork/) il y a les liens vers les autres applis dans le menu "Administration".

---

## Conseils & Dépannage

-   **Sur la box ou routeur :**
    -   Dans DHCP, fixer en permanent l'adresse IP du Raspberry.
    -   Dans DNS, fixer le nom soundcork.

### En cas de déménagement ou changement de box routeur

-   Si le préfixe IP n'a pas bougé : Juste refaire la manip en mettant bien l'IP que possédait le Raspberry.
-   Si le préfixe IP a bougé :
    -   Remplacer les serveurs Bose : ~/sc\_tools/tools/change\_marge.sh
    -   Recréer DB : ~/sc\_tools/tools/create\_data.sh
    -   Vérifier DB : ~/sc\_tools/tools/control\_data.sh
    -   Adapter IP : ~/sc\_tools/change\_cfg.sh et ~/sc\_tools/change\_ip.sh

### Ajout d'une nouvelle enceinte

-   La rentrer dans l'ensemble
    -   Réinitialisation usine : voir documention ou Vol- et 1 (quand elle munie d'un panel)
    -   Connexion au réseau : voir documention (wifi ou filaire)
    -   Trouver l'IP de l'enceinte : ~/sc\_tools/tools/discoverST.sh
    -   Change le compte du site : ~/sc\_tools/tools/change\_accountId.sh
    -   Remplacer les serveurs Bose : ~/sc\_tools/tools/change\_marge.sh
    -   Intégrer à soundcork : [http:/soundcork:8000/admin](http://soundcork:8000/admin) sur navigateur, suivre les indications

---

# Sources et autres infos

### changer le serveur cloud

Sur une console Raspberry :

nc <192.168.1.Ip\_Enceinte> 17000  
sys configuration bmxRegistryUrl http://192.168.1.116:8000/bmx/registry/v1/services  
sys configuration bmxRegistryUrl http://192.168.1.116:8000/bmx/registry/v1/services  
sys configuration statsServerUrl http://192.168.1.116:8000  
sys configuration margeServerUrl http://192.168.1.116:8000/marge  
sys configuration swUpdateUrl http://192.168.1.116:8000/updates/soundtouch  
envswitch boseurls set http://192.168.1.116:8000/marge http://192.168.1.116:8000/updates/soundtouch  
getpdo CurrentSystemConfiguration

_Il faut taper la première commande 2 fois pour que l'enceinte écoute ;)_

-   Changer le AccountID (margeAccountUUID) :

nc <192.168.1.Ip\_Enceinte> 17000  
envswitch AccountId get  
envswitch AccountId set 5476586  
sys reboot

-   Rebooter à distance une enceinte rootée ou non :

echo "sys reboot" | nc 192.168.1.25 17000

### Rooter une enceinte, méthode logicielle :

-   1- Choisir une enceinte :

~/sc-tools/tools/discoverST -b

-   2- rooter l'enceinte choisie (ne fonctionne pas sur les portables génération 1) :

~/sc-tools/tools/rootST.sh ??  #suffixe de l'adresse IP (ex: 65)  
~/sc-tools/tools/rebootST.sh ??  # (ex: 65)

-   3- [Reprendre](#Cdata) la procédure :

## Installation de tailscale (vpn) :

Tailscale va créer un tunnel sécurisé direct entre votre smartphone et votre Raspberry Pi, sans que vous n'ayez à ouvrir le moindre port sur votre box.  
Voici comment mettre cela en place en quelques minutes.  

### Étape 1 : Créer un compte Tailscale

Avant de toucher aux appareils, allez sur le site officiel [tailscale.com](tailscale.com) depuis votre ordinateur et créez un compte gratuit (vous pouvez utiliser un compte Google, Microsoft, Apple ou GitHub pour vous connecter facilement).  

### Étape 2 : Installer Tailscale sur le Raspberry Pi

Retournez sur le terminal de votre Raspberry Pi (via SSH) et exécutez la commande d'installation officielle :  

curl -fsSL https://tailscale.com/install.sh | sh

Le script va détecter que vous êtes sur un système basé sur Debian/Raspbian et installer les bons paquets.  
  
Une fois l'installation terminée, démarrez le service avec cette commande :  

sudo tailscale up

  
Que va-t-il se passer ?  
Le terminal va afficher une longue URL (un lien web).  
1\. Copiez ce lien et collez-le dans le navigateur de votre PC.  
2\. Connectez-vous avec le compte Tailscale que vous venez de créer.  
3\. Cliquez sur "Connect" ou "Authorize".  
Votre Raspberry Pi est maintenant intégré à votre réseau privé virtuel !  

### Étape 3 : Récupérer l'adresse IP "magique"

Toujours sur le Raspberry Pi, tapez la commande suivante :  

tailscale ip -4

Cela va vous renvoyer une adresse IP (qui commence généralement par \`100.x.x.x\`). Notez précieusement cette adresse IP.  
Désormais, tant que Tailscale est actif, c'est cette adresse que vous utiliserez pour communiquer avec votre Raspberry Pi depuis n'importe où dans le monde, comme s'il était dans votre poche.  

### Étape 4 : Configurer le smartphone Android

1\. Prenez votre smartphone et allez sur le \*\*Google Play Store\*\*.  
2\. Cherchez et installez l'application \*\*Tailscale\*\*.  
3\. Ouvrez l'application et connectez-vous avec le \*\*même compte\*\* que celui utilisé à l'étape 1.  
4\. Vous verrez apparaître votre Raspberry Pi dans la liste des appareils de l'application.  
5\. Basculez l'interrupteur en haut à gauche pour activer Tailscale (Android vous demandera l'autorisation d'activer une connexion VPN, acceptez).  
  
Vous verrez alors une petite icône de clé (ou de bouclier) dans la barre de notifications de votre téléphone, indiquant que vous êtes connecté à votre réseau privé.  

### Étape 5 : Connecter votre application musicale en 4G

Maintenant que le lien est établi, il suffit de configurer votre application cliente (comme Symfonium ou DSub) :  
1\. Désactivez le Wi-Fi de votre téléphone pour être en 4G/5G.  
2\. Ouvrez votre application musicale et allez dans l'ajout de serveur (type Subsonic/Navidrome).  
3\. Dans le champ "Adresse du serveur" (ou URL), entrez : \`http://VOTRE\_IP\_TAILSCALE:4533\` (remplacez par l'adresse IP en \`100.x.x.x\` notée à l'étape 3).  
4\. Entrez vos identifiants Navidrome (créés lors du premier lancement de Navidrome).  
  
Et voilà ! Votre application va se connecter à votre Raspberry Pi de manière totalement sécurisée et chiffrée, que vous soyez dans le bus, au travail, ou à l'autre bout du monde.  
  
Petite astuce : Pensez à laisser l'application Tailscale tourner en arrière-plan sur votre téléphone (ou lancez-la simplement avant de vouloir écouter votre musique en extérieur).  
  
document.addEventListener('DOMContentLoaded', () => { // On sélectionne tous les blocs de code const codeBlocks = document.querySelectorAll('pre.code-block'); codeBlocks.forEach(pre => { // 1. On crée un conteneur autour du <pre> pour gérer le positionnement const wrapper = document.createElement('div'); wrapper.className = 'code-container'; pre.parentNode.insertBefore(wrapper, pre); wrapper.appendChild(pre); // 2. On crée l'interface du bouton (div > span + button) const controls = document.createElement('div'); controls.className = 'controls'; const msg = document.createElement('span'); msg.className = 'msg-success'; msg.textContent = 'Copié ✔'; const btn = document.createElement('button'); btn.className = 'copy-btn'; btn.textContent = 'Copier'; btn.type = 'button'; controls.appendChild(msg); controls.appendChild(btn); wrapper.appendChild(controls); // On ajoute l'UI en haut à droite // 3. Gestion de l'événement clic btn.addEventListener('click', () => { const codeToCopy = pre.textContent; // Récupère le texte brut du code const showSuccess = () => { msg.classList.add('show'); setTimeout(() => msg.classList.remove('show'), 2000); }; // API moderne pour la copie if (navigator.clipboard) { navigator.clipboard.writeText(codeToCopy).then(showSuccess).catch(err => { console.error('Erreur Clipboard API : ', err); }); } else { // Méthode de secours (fallback) pour les anciens navigateurs const textarea = document.createElement('textarea'); textarea.value = codeToCopy; document.body.appendChild(textarea); textarea.select(); try { if (document.execCommand('copy')) showSuccess(); } catch (err) { console.error('Erreur execCommand : ', err); } document.body.removeChild(textarea); } }); }); });
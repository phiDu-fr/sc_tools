C'est de loin la méthode la plus propre pour installer Navidrome, surtout sur un Raspberry Pi. Docker va encapsuler l'application avec toutes ses dépendances, ce qui évite de "salir" le système d'exploitation de base.

Voici la procédure complète pour déployer Navidrome via Docker Compose sur votre Pi 3 B+.

## 1. Prérequis : Installer Docker et Docker Compose

Si ce n'est pas déjà fait sur votre Raspberry Pi OS Lite, voici les commandes pour installer Docker et son outil de composition. Exécutez-les une par une dans le terminal (via SSH) :

```bash
# Met à jour le système
sudo apt update && sudo apt upgrade -y

# Télécharge et exécute le script d'installation officiel de Docker
curl -sSL https://get.docker.com | sh

# Ajoute votre utilisateur standard (souvent 'pi') au groupe Docker
# (Cela évite de devoir taper 'sudo' pour chaque commande Docker)
sudo usermod -aG docker $USER

# Installe Docker Compose
sudo apt install docker-compose -y

```

> **Important :** Après avoir ajouté votre utilisateur au groupe Docker, vous devez vous déconnecter du Raspberry Pi (tapez `exit`) puis vous reconnecter en SSH pour que les changements de permissions soient pris en compte.

## 2. Préparer l'environnement de Navidrome

Nous allons créer un dossier dédié pour ranger proprement les fichiers de configuration de Navidrome et sa base de données.

```bash
# Crée un dossier pour Navidrome dans le répertoire utilisateur
mkdir -p ~/navidrome/data

# Se place dans ce nouveau dossier
cd ~/navidrome

```

## 3. Le fichier Docker Compose

C'est le cœur de l'installation. Il indique à Docker exactement comment configurer et lancer Navidrome.

Créez le fichier `docker-compose.yml` (par exemple avec l'éditeur `nano` : `nano docker-compose.yml`) et collez la configuration suivante.

**Attention, vous devez modifier la ligne `"/chemin/vers/votre/musique:/music:ro"**` pour qu'elle pointe vers le dossier où se trouve votre musique sur le Raspberry Pi.

```yaml
version: "3"
services:
  navidrome:
    image: deluan/navidrome:latest
    container_name: navidrome
    user: 1000:1000 # Exécute le conteneur avec l'utilisateur standard
    ports:
      - "4533:4533" # Redirige le port 4533 vers l'extérieur
    restart: unless-stopped # Le serveur redémarrera tout seul, même après une coupure de courant
    environment:
      # Options basiques (optionnelles, Navidrome fonctionne très bien avec ses valeurs par défaut)
      ND_SCANSCHEDULE: 1h # Scanne la musique toutes les heures
      ND_LOGLEVEL: info  
      ND_SESSIONTIMEOUT: 24h
      ND_BASEURL: "" # À laisser vide sauf si vous utilisez un nom de domaine avec un proxy inverse
    volumes:
      - "./data:/data" # Stocke la base de données Navidrome dans le dossier qu'on a créé
      # /!\ MODIFIEZ LA LIGNE CI-DESSOUS /!\
      - "/chemin/vers/votre/musique:/music:ro" # Le ':ro' à la fin signifie 'Read Only' (Lecture seule)

```

> **Le paramètre `:ro` est crucial :** Il indique "Read Only". Cela garantit à 100% que Navidrome ne modifiera jamais, au grand jamais, vos fichiers musicaux originaux. Il se contentera de les lire pour construire sa base de données.

## 4. Lancer le serveur

Toujours dans le dossier `~/navidrome`, lancez cette simple commande :

```bash
docker-compose up -d

```

Le paramètre `-d` signifie "detached" : le serveur va se lancer en arrière-plan et vous rendra la main sur le terminal. Docker va télécharger l'image de Navidrome (cela prend quelques minutes la première fois) et démarrer le serveur.

## 5. Première connexion

Navidrome est maintenant actif !

1. Ouvrez un navigateur web sur un PC connecté au même réseau que le Raspberry Pi.
2. Tapez l'adresse IP de votre Raspberry Pi suivie du port 4533 (par exemple : `[http://192.168.1.50:4533](http://192.168.1.50:4533)`).
3. Le premier écran vous demandera de créer le compte Administrateur (nom d'utilisateur et mot de passe de votre choix).

Une fois connecté, Navidrome va commencer à scanner votre dossier musical. L'interface web vous permettra de voir l'avancement.


C'est la dernière étape, et c'est souvent la plus bluffante. Tailscale va créer un tunnel sécurisé direct entre votre smartphone et votre Raspberry Pi, sans que vous n'ayez à ouvrir le moindre port sur votre box SFR.

Voici comment mettre cela en place en quelques minutes.

## Étape 1 : Créer un compte Tailscale

Avant de toucher aux appareils, allez sur le site officiel **tailscale.com** depuis votre ordinateur et créez un compte gratuit (vous pouvez utiliser un compte Google, Microsoft, Apple ou GitHub pour vous connecter facilement).

## Étape 2 : Installer Tailscale sur le Raspberry Pi

Retournez sur le terminal de votre Raspberry Pi (via SSH) et exécutez la commande d'installation officielle :

```bash
curl -fsSL https://tailscale.com/install.sh | sh

```

*Le script va détecter que vous êtes sur un système basé sur Debian/Raspbian et installer les bons paquets.*

Une fois l'installation terminée, démarrez le service avec cette commande :

```bash
sudo tailscale up

```

**Que va-t-il se passer ?**
Le terminal va afficher une longue URL (un lien web).

1. Copiez ce lien et collez-le dans le navigateur de votre PC.
2. Connectez-vous avec le compte Tailscale que vous venez de créer.
3. Cliquez sur "Connect" ou "Authorize".
Votre Raspberry Pi est maintenant intégré à votre réseau privé virtuel !

## Étape 3 : Récupérer l'adresse IP "magique"

Toujours sur le Raspberry Pi, tapez la commande suivante :

```bash
tailscale ip -4

```

Cela va vous renvoyer une adresse IP (qui commence généralement par `100.x.x.x`). **Notez précieusement cette adresse IP**.
Désormais, tant que Tailscale est actif, c'est cette adresse que vous utiliserez pour communiquer avec votre Raspberry Pi depuis n'importe où dans le monde, comme s'il était dans votre poche.

## Étape 4 : Configurer le smartphone Android

1. Prenez votre smartphone et allez sur le **Google Play Store**.
2. Cherchez et installez l'application **Tailscale**.
3. Ouvrez l'application et connectez-vous avec le **même compte** que celui utilisé à l'étape 1.
4. Vous verrez apparaître votre Raspberry Pi dans la liste des appareils de l'application.
5. Basculez l'interrupteur en haut à gauche pour activer Tailscale (Android vous demandera l'autorisation d'activer une connexion VPN, acceptez).

Vous verrez alors une petite icône de clé (ou de bouclier) dans la barre de notifications de votre téléphone, indiquant que vous êtes connecté à votre réseau privé.

## Étape 5 : Connecter votre application musicale en 4G

Maintenant que le lien est établi, il suffit de configurer votre application cliente (comme Symfonium ou DSub) :

1. Désactivez le Wi-Fi de votre téléphone pour être en **4G/5G**.
2. Ouvrez votre application musicale et allez dans l'ajout de serveur (type Subsonic/Navidrome).
3. Dans le champ "Adresse du serveur" (ou URL), entrez : `http://VOTRE_IP_TAILSCALE:4533` (remplacez par l'adresse IP en `100.x.x.x` notée à l'étape 3).
4. Entrez vos identifiants Navidrome (créés lors du premier lancement de Navidrome).

Et voilà ! Votre application va se connecter à votre Raspberry Pi de manière totalement sécurisée et chiffrée, que vous soyez dans le bus, au travail, ou à l'autre bout du monde.

*Petite astuce : Pensez à laisser l'application Tailscale tourner en arrière-plan sur votre téléphone (ou lancez-la simplement avant de vouloir écouter votre musique en extérieur).*
#!/bin/bash
# Fichier : /home/pi/sc_tools/tools/sauve.sh

# Définition stricte du PATH pour cron
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo "⏳ Démarrage de la sauvegarde..."
DEST_DIR="$HOME/.sauve"
ARCHIVE_NAME="sauve$(date +%Y%m%d-%H%M).7z"
LATEST_FILE="sc_tools.latest.7z"

# 1. Création du dossier si inexistant
mkdir -p "$DEST_DIR"

# 2. Nettoyage et préparation
rm -f "$DEST_DIR/$LATEST_FILE"
apt-mark showmanual > "$HOME/sc_tools/docs/paquets_a_installer.txt"

# 3. Sauvegarde sc_tools
cd "$HOME/sc_tools" || { echo "❌ Erreur : Impossible d'accéder à $HOME/sc_tools"; exit 1; }
7z a -t7z -mx=9 "$DEST_DIR/$ARCHIVE_NAME" $(find . -maxdepth 1 -type f) app/ www/ data/ docs/ tools/ update/ '-xr!*.7z' '-xr!*.zip' '-xr!*.mp3' '-xr!core.*' '-xr!__pycache__/'

# 3b. Sauvegarde paramètres sc_tools
cd "$HOME/sc_tools" || { echo "❌ Erreur : Impossible d'accéder à $HOME/sc_tools"; exit 1; }
7z a -t7z -mx=9 "$DEST_DIR/param$(date +%Y%m%d-%H%M).7z" @.save 

# 4. Sauvegarde sc_music
cd "$HOME" || { echo "❌ Erreur : Impossible d'accéder à $HOME"; exit 1; }
7z a -t7z -mx=9 "$DEST_DIR/$ARCHIVE_NAME" $(find . -maxdepth 1 -type f) sc_music/ '-xr!*.jpg' '-xr!*.7z' '-xr!*.zip' '-xr!*.mp3' '-xr!*.db' '-xr!core.*' '-xr!__pycache__/'

# 5. Copie et envoi
cp "$DEST_DIR/$ARCHIVE_NAME" "$DEST_DIR/$LATEST_FILE"

echo "📡 Envoi vers le NAS..."
smbclient //192.168.1.150/web -A "$HOME/.smbcredentials" -c "lcd $DEST_DIR ; cd sc_tools ; put $LATEST_FILE"
smbclient //192.168.1.150/web -A "$HOME/.smbcredentials" -c "lcd $HOME/sc_tools/docs ; cd sc_tools ; put SoundcorkSetup.html index.html"

echo "✅ Sauvegarde terminée avec succès !"

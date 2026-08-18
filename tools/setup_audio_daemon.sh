#!/bin/bash
# Fichier : setup_audio_daemon.sh
# Description : Configure et force le démarrage du serveur audio en mode headless (sans IHM) pour le Raspberry Pi.
# Exécution : Lancer en tant qu'utilisateur standard (NON ROOT), sans sudo.

if [ "$EUID" -eq 0 ]; then
  echo "[ERREUR] Ne lance pas ce script avec sudo ou en root. Utilise ton utilisateur standard (ex: pi ou ton user de dev)."
  exit 1
fi

USER_UID=$(id -u)
export XDG_RUNTIME_DIR="/run/user/$USER_UID"

echo "[INFO] Activation du mode 'Linger' pour l'utilisateur $USER..."
# Le mode linger permet aux services de l'utilisateur de démarrer au boot 
# et de rester actifs même après la déconnexion SSH.
sudo loginctl enable-linger "$USER"

echo "[INFO] Détection et configuration du serveur audio..."

if command -v pipewire >/dev/null; then
    echo "[INFO] Système basé sur PipeWire détecté."
    # Démarrage et activation au boot des services PipeWire
    systemctl --user enable pipewire pipewire-pulse
    systemctl --user start pipewire pipewire-pulse
elif command -v pulseaudio >/dev/null; then
    echo "[INFO] Système basé sur PulseAudio détecté."
    # Démarrage et activation au boot de PulseAudio
    systemctl --user enable pulseaudio
    systemctl --user start pulseaudio
else
    echo "[ERREUR] Ni PulseAudio ni PipeWire ne sont installés sur le système."
    exit 1
fi

echo "[INFO] Redémarrage de la pile Bluetooth au niveau système..."
sudo systemctl restart bluetooth

echo "[INFO] Attente de l'initialisation des sockets audio..."
sleep 3

echo "=================================================="
echo "[INFO] Test de la connexion au serveur audio :"
if pactl list short sinks > /dev/null 2>&1; then
    echo "[SUCCÈS] Le serveur audio répond."
    pactl list short sinks
else
    echo "[ERREUR] Toujours impossible de joindre le serveur. Vérifie les logs via : journalctl --user -xe"
fi
echo "=================================================="

echo "[NOTE] Pour tes scripts futurs (ex: dans cron ou systemd système), n'oublie pas d'ajouter :"
echo 'export XDG_RUNTIME_DIR="/run/user/'$USER_UID'"'
#!/bin/bash
# Fichier : bt_force_pair.sh
# Description : Purge une enceinte du cache BlueZ et force un nouvel appairage complet.
# Utile pour résoudre les erreurs "br-connection-page-timeout".

MAC_ADDRESS="70:99:1C:AF:FB:5F"
SINK_NAME="bluez_sink.${MAC_ADDRESS//:/_}.a2dp_sink"

echo "[INFO] Suppression de l'appareil $MAC_ADDRESS du cache BlueZ..."
bluetoothctl remove "$MAC_ADDRESS" > /dev/null 2>&1
sleep 1

echo "[INFO] Redémarrage du service Bluetooth pour garantir un cache propre..."
sudo systemctl restart bluetooth
sleep 2

echo "[ACTION REQUISE] Assure-toi que l'enceinte est en mode APPAIRAGE (LED clignotante)."
echo "Appuie sur Entrée quand c'est prêt..."
read -r

echo "[INFO] Lancement du processus d'association..."

# Utilisation d'un sous-shell pour envoyer les commandes avec des temporisations
# Les temporisations sont cruciales pour laisser le baseband négocier les clés
(
echo "power on"
sleep 1
echo "agent on"
sleep 1
echo "default-agent"
sleep 1
echo "scan on"
sleep 4
echo "scan off"
sleep 1
echo "pair $MAC_ADDRESS"
sleep 4
echo "trust $MAC_ADDRESS"
sleep 1
echo "connect $MAC_ADDRESS"
sleep 4
echo "quit"
) | bluetoothctl

echo "[INFO] Vérification de la connexion audio..."
sleep 3

if pactl list short sinks | grep -q "$SINK_NAME"; then
    echo "[SUCCÈS] Appairage réussi. Enceinte connectée et prête."
    pactl set-default-sink "$SINK_NAME"
else
    echo "[ERREUR] Échec de la connexion. Vérifie dmesg ou journalctl -u bluetooth."
fi
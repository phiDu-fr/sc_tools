#!/bin/bash

echo "=== Configuration Wi-Fi Bose SoundTouch ==="

# 1. Saisie des informations
read -p "Adresse IP de l'enceinte [192.0.2.1] : " IP
IP=${IP:-192.0.2.1} # Valeur par défaut si l'utilisateur appuie juste sur Entrée

read -p "Nom du réseau Wi-Fi (SSID) : " SSID
read -p "Clé Wi-Fi (Mot de passe) : " WIFI_KEY

# Vérification basique des saisies
if [ -z "$SSID" ] || [ -z "$WIFI_KEY" ]; then
    echo "Erreur : Le SSID et la clé Wi-Fi sont obligatoires."
    exit 1
fi

echo -e "\nConfiguration de l'enceinte $IP pour le réseau '$SSID'..."

# 2. Envoi du profil Wi-Fi
echo "[1/2] Envoi des identifiants Wi-Fi..."
curl -s -X POST "http://$IP:8090/addWirelessProfile" \
     -H "Content-Type: text/xml" \
     -d @- <<EOF
<AddWirelessProfile timeout="30">
   <profile ssid="$SSID" password="$WIFI_KEY" securityType="wpa_or_wpa2" />
</AddWirelessProfile>
EOF

# Vérification du succès de la commande curl
if [ $? -ne 0 ]; then
    echo -e "\nErreur : Impossible de contacter l'enceinte sur $IP."
    exit 1
fi

# Petite pause pour laisser l'enceinte digérer la première requête
sleep 2

# 3. Sortie du mode configuration
echo -e "\n[2/2] Envoi de la commande de sortie du mode configuration..."
curl -s -X POST "http://$IP:8090/setup" \
     -H "Content-Type: text/xml" \
     -d @- <<EOF
<setupState state="SETUP_WIFI_LEAVE" />
EOF

echo -e "\n\nTerminé ! L'enceinte devrait maintenant redémarrer, quitter le mode point d'accès, et se connecter à votre réseau classique."
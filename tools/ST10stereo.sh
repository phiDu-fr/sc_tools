#!/bin/bash

# créé un groupe stéréo de 2 enceintes Soundtouch 10. Le ST-10 est le seul produit SoundTouch qui prend en charge les groupes de paires stéréo.
# /mnt/nv/BoseApp-Persistence/1/GroupService.xml
# https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/wiki/SoundTouch-WebServices-API#group---add-stereo-pair
# Autres commandes :
# http://192.168.1.161:8090/getGroup
# http://192.168.1.161:8090/removeGroup
# http://192.168.1.161:8090/updateGroup

if [ "$#" -ne 3 ]; then
    echo "Usage : $0 <IP_GAUCHE> <IP_DROITE> <NOM_PAIRE>"
    exit 1
fi

IP_LEFT="$1"
IP_RIGHT="$2"
PAIR_NAME="$3"

# Fonction récupération deviceID
get_device_id() {
    local ip="$1"
    curl -s "http://${ip}:8090/info" | grep -oP 'deviceID="\K[^"]+'
}

echo "Récupération des deviceID..."

DEVICE_LEFT=$(get_device_id "$IP_LEFT")
DEVICE_RIGHT=$(get_device_id "$IP_RIGHT")

if [ -z "$DEVICE_LEFT" ]; then
    echo "Erreur : impossible de récupérer le deviceID de $IP_LEFT"
    exit 1
fi

if [ -z "$DEVICE_RIGHT" ]; then
    echo "Erreur : impossible de récupérer le deviceID de $IP_RIGHT"
    exit 1
fi

echo "LEFT  : $DEVICE_LEFT"
echo "RIGHT : $DEVICE_RIGHT"

# ID groupe 5NNNNNNN
GROUP_ID="5$(date +%s | tail -c7)"

# Fichier XML
OUTPUT_FILE="group_${PAIR_NAME}.xml"

echo "Génération du fichier XML..."

cat > "$OUTPUT_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<group id="$GROUP_ID">
   <name>${PAIR_NAME}</name>
   <masterDeviceId>${DEVICE_LEFT}</masterDeviceId>
   <roles>
       <groupRole>
           <deviceId>${DEVICE_LEFT}</deviceId>
           <role>LEFT</role>
           <ipAddress>${IP_LEFT}</ipAddress>
       </groupRole>
       <groupRole>
           <deviceId>${DEVICE_RIGHT}</deviceId>
           <role>RIGHT</role>
           <ipAddress>${IP_RIGHT}</ipAddress>
       </groupRole>
   </roles>
   <senderIPAddress>${IP_LEFT}</senderIPAddress>
   <status>GROUP_OK</status>
</group>
EOF

echo "Fichier généré : $OUTPUT_FILE"
echo

# Fonction pour poster le fichier et afficher la réponse
post_group() {
    local ip="$1"
    echo "Envoi vers http://${ip}:8090/addGroup"
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/xml" --data-binary "@${OUTPUT_FILE}" "http://${ip}:8090/addGroup")
    # Séparer corps et code HTTP
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    echo "HTTP code: $HTTP_CODE"
    echo "Réponse serveur :"
    echo "-----------------------------------"
    echo "$BODY"
    echo "-----------------------------------"
    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        echo "Envoi vers $ip réussi."
    else
        echo "Attention : envoi vers $ip a retourné le code $HTTP_CODE."
    fi
    echo
}

# Poster vers LEFT
post_group "$IP_LEFT"

# Poster vers RIGHT si différente de LEFT
if [ "$IP_RIGHT" != "$IP_LEFT" ]; then
    post_group "$IP_RIGHT"
else
    echo "IP_RIGHT identique à IP_LEFT, envoi unique effectué."
fi

echo "Attente de 10 secondes avant reboot..."
sleep 10

send_reboot() {
    local ip="$1"
    echo
    echo "Connexion à ${ip}:17000"
    {
        echo "sys reboot"
        sleep 1
        echo "quit"
    } | nc "$ip" 17000
    echo "Commande reboot envoyée à $ip"
}

# Reboot LEFT
send_reboot "$IP_LEFT"

# Reboot RIGHT si différente
if [ "$IP_RIGHT" != "$IP_LEFT" ]; then
    send_reboot "$IP_RIGHT"
fi

echo
echo "Terminé."

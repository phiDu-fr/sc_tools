#!/bin/bash

#curl -X POST "http://192.168.1.65:8090/key" -H "Content-Type: application/xml" -d '<key state="press" sender="Gabbo">PRESET_2</key>'

# Vérification du nombre d'arguments
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <suffixe_ip> <key_name> <key_state>"
    echo "Exemples d'état : press, release, both"
    echo "Exemple d'utilisation : $0 15 PRESET_2 release"
    exit 1
fi

# Récupération des paramètres
IP_SUFFIX=$1
KEY_NAME=$2
KEY_STATE=$3

# Configuration réseau (à adapter selon ton sous-réseau)
SUBNET=$(hostname -I | cut -d' ' -f1 | cut -d. -f1-3)
IP="${SUBNET}.${IP_SUFFIX}"
PORT="8090"

echo "Envoi à l'enceinte : ${IP} | Touche : ${KEY_NAME} | État : ${KEY_STATE}"

# Fonction pour envoyer la requête XML via curl
send_request() {
    local state=$1
    local xml_data="<key state=\"${state}\" sender=\"Gabbo\">${KEY_NAME}</key>"
    
    # -s : mode silencieux, -m 2 : timeout de 2 secondes
    curl -s -m 2 -X POST \
         -H "Content-Type: application/xml" \
         -d "${xml_data}" \
         "http://${IP}:${PORT}/key"
}

# Logique d'envoi ("press", "release" ou "both")
if [[ "$KEY_STATE" == "press" || "$KEY_STATE" == "both" ]]; then
    send_request "press"
fi

if [[ "$KEY_STATE" == "release" || "$KEY_STATE" == "both" ]]; then
    send_request "release"
fi

# Note : Le rafraîchissement (update_speaker_state) n'est pas inclus ici
# car il dépend d'une fonction interne à ton serveur Python.
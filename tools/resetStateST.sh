#!/bin/bash
# ==============================================================================
# Nom du script : st_reset_state.sh
# Description   : Réinitialise l'état de lecture d'une ou plusieurs enceintes 
#                 Bose SoundTouch en simulant l'appui sur la touche STOP via l'API.
#                 Intègre la découverte mDNS (avahi) et le ciblage par suffixe IP.
# Prérequis     : curl, avahi-utils
# ==============================================================================

if [ $# -lt 1 ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch | All>"
    echo "   Exemple ciblé : $0 65"
    echo "   Exemple masse : $0 all"
    exit 1
fi

# Détection automatique du réseau local (ex: 192.168.1)
NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)
ST_PORT="8090"
TIMEOUT="5"

# --- Fonction de réinitialisation de l'état (STOP) ---
reset_soundtouch_state() {
    local ST_IP=$1
    echo " ⚙️  Envoi de la commande STOP à l'enceinte ($ST_IP)..."
    
    # 1. Envoi de l'état "press"
    local HTTP_CODE_PRESS=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT \
        -X POST -H "Content-Type: text/xml" \
        -d '<key state="press" sender="Gabbo">STOP</key>' \
        "http://${ST_IP}:${ST_PORT}/key")

    if [ "$HTTP_CODE_PRESS" -ne 200 ] && [ "$HTTP_CODE_PRESS" -ne 202 ]; then
        echo "   ❌ Échec lors de la pression 'press' (Code HTTP: $HTTP_CODE_PRESS)"
        return 1
    fi

    sleep 0.5

    # 2. Envoi de l'état "release"
    local HTTP_CODE_RELEASE=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT \
        -X POST -H "Content-Type: text/xml" \
        -d '<key state="release" sender="Gabbo">STOP</key>' \
        "http://${ST_IP}:${ST_PORT}/key")

    if [ "$HTTP_CODE_RELEASE" -ne 200 ] && [ "$HTTP_CODE_RELEASE" -ne 202 ]; then
        echo "   ❌ Échec lors du relâchement 'release' (Code HTTP: $HTTP_CODE_RELEASE)"
        return 1
    fi

    echo "   ✅ État de lecture réinitialisé avec succès."
    echo "---------------------------------------------------"
}

# --- Logique Principale ---

if [[ "${1,,}" == "all" ]]; then
    echo "🔎 Détection SoundTouch via Zeroconf (mDNS) + API..."
    echo

    # Vérifier si avahi-browse est installé
    if ! command -v avahi-browse >/dev/null 2>&1; then
        echo "❌ avahi-browse n'est pas installé."
        echo "   Installe-le avec : sudo apt install avahi-utils"
        exit 1
    fi

    # Scan du service _soundtouch._tcp
    avahi-browse -rt _soundtouch._tcp 2>/dev/null | while read -r line; do
        # Détection d'une ligne contenant l'adresse
        if echo "$line" | grep -q "address ="; then
            
            # Extraction robuste de l'IP sans sed
            IP=$(echo "$line" | cut -d'[' -f2 | cut -d']' -f1)

            echo "➡️  Appareil détecté via mDNS : $IP"
            reset_soundtouch_state "$IP"
        fi
    done

else
    # Ciblage par suffixe IP
    IP="${NET}.$1"
    echo "🔎 Vérification de l'enceinte sur $IP..."
    
    # Test de réponse de l'API REST sur le port 8090
    if curl -s --connect-timeout 0.3 "http://$IP:8090/name" >/dev/null; then
        echo "➡️  SoundTouch détecté : $IP"
        reset_soundtouch_state "$IP"
    else
        echo "❌ SoundTouch non détectée à l'adresse : $IP"
    fi
fi
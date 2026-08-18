#!/usr/bin/env bash

# Mise à jour des presets depuis le fichier Presets.xml de soundcork

# Vérification du nombre d'arguments minimum
if [ -z "$1" ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch> | all"
    echo "   Exemple : $0 65"
    exit 1
fi

DOSSIER_DATA="/home/pi/soundcork/data"
FICHIER_XML=$(find "$DOSSIER_DATA" -type f -name "Presets.xml" | head -n 1)

if [ -z "$FICHIER_XML" ]; then
    echo "❌ Erreur : Aucun fichier 'Presets.xml' trouvé dans $DOSSIER_DATA ou ses sous-dossiers."
    exit 1
fi

echo "✅ Fichier source trouvé : $FICHIER_XML"

# Chargement complet du fichier dans une variable
XML_CONTENT=$(cat "$FICHIER_XML")

# --- LECTURE ET AFFICHAGE DU TABLEAU ---
echo -e "\n📋 Prévisualisation des presets à installer :"
echo "------------------------------------------------"
printf "| %-12s | %-30s |\n" "Num Preset" "Nom"
echo "------------------------------------------------"

for i in {1..6}; do
    # Découpe 100% native Bash (imparable)
    REST="${XML_CONTENT#*<preset id=\"$i\"}"
    
    # Si la chaîne a changé, c'est que la balise a été trouvée
    if [ "$REST" != "$XML_CONTENT" ]; then
        # On reconstitue le début et on coupe tout ce qui dépasse </preset>
        PRESET_DATA="<preset id=\"$i\"${REST}"
        PRESET_DATA="${PRESET_DATA%%</preset>*}</preset>"
        
        # Extraction précise du nom
        ITEM_NAME="${PRESET_DATA#*<itemName>}"
        ITEM_NAME="${ITEM_NAME%%</itemName>*}"
        
        # Nettoyage CDATA si présent
        ITEM_NAME=$(echo "$ITEM_NAME" | sed 's/<!\[CDATA\[//g; s/\]\]>//g')
        
        # S'il n'y a pas de balise itemName, ITEM_NAME contiendra tout le bloc
        if [ "$ITEM_NAME" = "$PRESET_DATA" ] || [ -z "$ITEM_NAME" ]; then
            ITEM_NAME="(Source sans nom)"
        fi
        
        printf "| %-12s | %-30s |\n" "Preset $i" "${ITEM_NAME:0:30}"
    fi
done
echo "------------------------------------------------"
echo

# --- DEMANDE DE CONFIRMATION ---
read -p "Voulez-vous lancer la mise à jour ? (O/n) : " confirm
if [[ ! "$confirm" =~ ^[Oo]$ ]] && [[ "$confirm" != "" ]]; then
    echo "❌ Opération annulée."
    exit 0
fi
echo


# --- FONCTION : DÉCOUPAGE ET ENVOI ---
send_presets_to_ip() {
    local IP=$1
    local XML_FILE=$2
    local CONTENT=$(cat "$XML_FILE")

    echo "➡️  Mise à jour de l'enceinte : $IP"

    for i in {1..6}; do
        local REST="${CONTENT#*<preset id=\"$i\"}"
        
        if [ "$REST" != "$CONTENT" ]; then
            local PRESET_DATA="<preset id=\"$i\"${REST}"
            PRESET_DATA="${PRESET_DATA%%</preset>*}</preset>"
            
            # Suppression d'éventuels espaces invisibles et retours à la ligne
            local PRESET_MIN=$(echo "$PRESET_DATA" | tr -d '\n\r\t')
            
            # Ajout de l'en-tête XML officiel exigé par les parseurs stricts
            local PAYLOAD="<?xml version=\"1.0\" encoding=\"UTF-8\" ?>${PRESET_MIN}"
            
            local TAILLE=$(echo -n "$PAYLOAD" | wc -c)

            echo -n "   - Envoi du preset $i ($TAILLE octets)... "

            # Envoi et capture de la réponse de l'enceinte
            REPONSE=$(curl -s -X POST \
                 -H "Content-Type: application/xml" \
                 -d "$PAYLOAD" \
                 "http://${IP}:8090/storePreset")
                 
            # Analyse de la réponse (L'enceinte renvoie <errors> si ça s'est mal passé)
            if echo "$REPONSE" | grep -iq "error"; then
                echo "❌ Échec (L'enceinte a rejeté le format)"
            else
                echo "✅ Succès"
            fi
                 
            sleep 0.5
        fi
    done
    
    # echo "sys reboot" | nc -w 1 $IP 17000
    echo "   → Mise à jour terminée pour $IP."
    echo "-----------------------------------"
}


# --- LOGIQUE PRINCIPALE ---
if [[ "${1,,}" == "all" ]]; then
    echo "🔎 Détection SoundTouch via Zeroconf + API..."
    echo

    if ! command -v avahi-browse >/dev/null 2>&1; then
        echo "❌ avahi-browse n'est pas installé."
        echo "   Installe-le avec : sudo apt install avahi-utils"
        exit 1
    fi

    avahi-browse -rt _soundtouch._tcp 2>/dev/null | while read -r line; do
        if echo "$line" | grep -q "address ="; then
            IP_ENCEINTE=$(echo "$line" | cut -d'[' -f2 | cut -d']' -f1)
            send_presets_to_ip "$IP_ENCEINTE" "$FICHIER_XML"
        fi
    done

else
    NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)
    IP_ENCEINTE="${NET}.$1"
    
    if curl -s --connect-timeout 0.3 "http://$IP_ENCEINTE:8090/name" >/dev/null; then
        send_presets_to_ip "$IP_ENCEINTE" "$FICHIER_XML"
    else
        echo "❌ SoundTouch non détectée à l'adresse : $IP_ENCEINTE"
    fi
fi
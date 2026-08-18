#!/usr/bin/env bash

# Vérifier les presets d'une enceinte

# Vérification du nombre d'arguments minimum
if [ -z "$1" ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch>"
    echo "   Exemple : $0 65"
    exit 1
fi

NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)
IP_ENCEINTE="${NET}.$1"

# Récupération du contenu XML directement depuis l'enceinte (-s pour silencieux)
XML_CONTENT=$(curl -s "http://$IP_ENCEINTE:8090/presets")

# Vérification si la récupération a réussi
if [ -z "$XML_CONTENT" ]; then
    echo "❌ Erreur : Impossible de récupérer les presets depuis http://$IP_ENCEINTE:8090/presets"
    exit 1
fi

echo "✅ Presets récupérés avec succès depuis l'enceinte ($IP_ENCEINTE)."

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
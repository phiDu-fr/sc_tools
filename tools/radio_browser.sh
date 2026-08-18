#!/usr/bin/env bash

# --- Configuration des Radios ---
declare -A RADIOS=(
    ["inter"]="0b80555f-eb5c-4fce-94d2-109eec7bee6b"
    ["fip"]="932eb148-e6f6-11e9-a96c-52543be04c81"
    ["info"]="31074f8a-e6f4-11e9-a96c-52543be04c81"
    ["rire"]="a70cdc64-9a33-4432-91a1-957beb5ac6e7"
    ["rtl"]="d69e38f7-f565-4217-b9a8-0075c5e32340"
    ["nostalgie"]="88496158-90c1-411f-9a3b-719397a8dcca"
    ["nova"]="963fb390-0601-11e8-ae97-52543be04c81"
)

# --- Configuration des Enceintes (Suffixe IP -> Nom) ---
declare -A ENCEINTES=(
    ["65"]="Cuisine30"
    ["100"]="CH20"
    ["25"]="ST300"
    ["195"]="St10g"
    ["64"]="Barre"
    ["118"]="Blanche"
    ["161"]="ST10D"
    ["131"]="Boitier"
)

CIBLE=$1
CHOIX_RADIO=${2:-"inter"} # Par défaut "inter" si non précisé

# --- Fonction d'aide ---
afficher_usage() {
    echo "❌ Usage: $0 <suffixe_ip|nom_enceinte> [nom_radio|random]"
    echo -e "\n📻 Radios dispos : ${!RADIOS[@]} (ou 'random')"
    echo -e "\n🔊 Enceintes dispos (IP ou Nom) :"
    for suff in "${!ENCEINTES[@]}"; do
        echo "  - $suff : ${ENCEINTES[$suff]}"
    done
    exit 1
}

if [[ -z "$CIBLE" ]]; then
    afficher_usage
fi

# --- Résolution de l'enceinte (Recherche par IP OU par Nom) ---
SUFFIXE=""
NOM_ENCEINTE=""

if [[ -n "${ENCEINTES[$CIBLE]}" ]]; then
    # L'utilisateur a entré directement l'IP (ex: 65)
    SUFFIXE=$CIBLE
    NOM_ENCEINTE=${ENCEINTES[$CIBLE]}
else
    # L'utilisateur a entré le nom (ex: cuisine30 ou cuisine), on cherche la clé
    for suff in "${!ENCEINTES[@]}"; do
        # Comparaison en minuscules pour être tolérant à la casse
        if [[ "${ENCEINTES[$suff],,}" == "${CIBLE,,}"* ]]; then
            SUFFIXE=$suff
            NOM_ENCEINTE=${ENCEINTES[$suff]}
            break
        fi
    done
fi

# Si aucun suffixe n'a été trouvé après recherche
if [[ -z "$SUFFIXE" ]]; then
    echo "⚠️ Enceinte '$CIBLE' inconnue."
    afficher_usage
fi

# --- Logique de sélection de la radio ---
if [[ "$CHOIX_RADIO" == "random" ]]; then
    KEYS=("${!RADIOS[@]}")
    CHOIX_RADIO=${KEYS[$RANDOM % ${#KEYS[@]}]}
fi

UUID=${RADIOS[$CHOIX_RADIO]}

if [[ -z "$UUID" ]]; then
    echo "⚠️ Radio '$CHOIX_RADIO' inconnue. Repli sur France Inter."
    UUID=${RADIOS["inter"]}
    CHOIX_RADIO="inter"
fi

# --- Préparation réseau et exécution ---
IP_PREFIX=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)
# Sécurité si hostname -I est capricieux (ex: docker/VLAN actifs)
: "${IP_PREFIX:=192.168.1}" 

URL="http://${IP_PREFIX}.${SUFFIXE}:8090/select"
DATA="<ContentItem source=\"RADIO_BROWSER\" type=\"stationurl\" location=\"/stations/byuuid/$UUID\"><itemName>${CHOIX_RADIO}</itemName></ContentItem>"

echo "📡 Envoi de [$CHOIX_RADIO] vers $NOM_ENCEINTE (${IP_PREFIX}.${SUFFIXE})..."

# Ajout de timeouts sur curl pour éviter que le script freeze si l'enceinte est éteinte
if curl -sSf --connect-timeout 3 --max-time 5 -d "$DATA" "$URL" > /dev/null; then
    echo "✅ Lancé avec succès sur $NOM_ENCEINTE !"
else
    echo "❌ Erreur : Impossible de joindre $NOM_ENCEINTE à l'adresse ${IP_PREFIX}.${SUFFIXE}."
fi

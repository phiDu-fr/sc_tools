#!/bin/bash
# ==============================================================================
# Nom du script : st_blank_preset.sh
# Description   : Récupère dynamiquement le contenu d'un preset SoundTouch via
#                 TAP (17000), le parse, et le réécrit en écrasant sa "location"
#                 à blanc ("") pour purger le cache de reprise (resume).
# Prérequis     : netcat (nc), awk
# ==============================================================================

if [ $# -lt 2 ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch> <Numero_Preset>"
    echo "   Exemple : $0 65 5"
    exit 1
fi

# Configuration réseau
NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)
ST_IP="${NET}.$1"
PRESET_NUM="$2"
PRESET_ID="P${PRESET_NUM}"
TAP_PORT="17000"

echo "🔎 Analyse de l'enceinte $ST_IP sur le port $TAP_PORT..."

# 1. Vérification de la disponibilité du port TAP
if ! nc -z -w 1 "$ST_IP" "$TAP_PORT" >/dev/null 2>&1; then
    echo "❌ Port $TAP_PORT injoignable sur $ST_IP."
    exit 1
fi

echo "📥 Récupération des presets en cours..."
# On envoie la commande et on stocke le retour brut (timeout 2s pour s'assurer d'avoir toute la sortie)
RAW_PRESETS=$(echo "ws GetPresets" | nc -w 2 "$ST_IP" "$TAP_PORT")

if [ -z "$RAW_PRESETS" ]; then
    echo "❌ Aucune donnée retournée par l'enceinte."
    exit 1
fi

echo "⚙️  Extraction des données pour le preset $PRESET_ID..."

# 2. Parsing via AWK
# Le script awk isole le bloc du preset demandé et extrait les valeurs entre guillemets
AWK_RESULT=$(echo "$RAW_PRESETS" | awk -v target="$PRESET_ID" '
    /^preset \{/ { in_block=1; id=""; src=""; acc=""; lbl=""; loc="" }
    in_block && /id:/ { id=$2 }
    in_block && id==target && /source:/ { src=$0; sub(/.*source:[ \t]*"/, "", src); sub(/"$/, "", src) }
    in_block && id==target && /location:/ { loc=$0; sub(/.*location:[ \t]*"/, "", loc); sub(/"$/, "", loc) }
    in_block && id==target && /sourceAccount:/ { acc=$0; sub(/.*sourceAccount:[ \t]*"/, "", acc); sub(/"$/, "", acc) }
    in_block && id==target && /text:/ { lbl=$0; sub(/.*text:[ \t]*"/, "", lbl); sub(/"$/, "", lbl) }
    /^}/ {
        if (in_block && id==target) {
            # On formate la sortie avec un délimiteur |
            printf "%s|%s|%s\n", src, acc, lbl
            exit
        }
        in_block=0
    }
')

# Séparation des variables extraites
IFS='|' read -r SRC ACC LBL <<< "$AWK_RESULT"

# 3. Vérification des données extraites
if [ -z "$SRC" ]; then
    echo "❌ Le preset $PRESET_ID est vide ou introuvable sur cette enceinte."
    exit 1
fi

echo "   - Source   : $SRC"
echo "   - Account  : $ACC"
echo "   - Label    : $LBL"
echo "   - Location : (sera forcée à BLANC)"
echo "---------------------------------------------------"

# 4. Forgeage de la nouvelle commande TAP
# Attention : si l'account est vide (ex: webradio), on doit le transmettre comme "" pour ne pas décaler les arguments
if [ -z "$ACC" ]; then
    ACC_ARG='""'
else
    ACC_ARG="$ACC"
fi

# On encadre le label avec des guillemets pour supporter les espaces, et on met "" pour la location
TAP_CMD="ws AddPreset $SRC \"\" \"$LBL\" $ACC_ARG $PRESET_NUM"

echo "📤 Envoi de la commande de réinitialisation :"
echo "   > $TAP_CMD"

# 5. Exécution de la réécriture
echo "$TAP_CMD" | nc -w 1 "$ST_IP" "$TAP_PORT"

sleep 0.5
echo "✅ Le preset $PRESET_NUM a été purgé de son ancienne location avec succès."
exit 0
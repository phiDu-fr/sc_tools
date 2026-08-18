#!/usr/bin/env bash

# Change la config de chaque enceinte en remplaçant les serveurs de Bose par le serveur qui héberge Soundcork
# Normalement cette adresse IP

SuffIP_Marge=$(hostname -I | awk '{print $1}' | awk -F. '{print $NF}')
# Vérification du nombre d'arguments minimum (au moins 2)
if [ $# -lt 1 ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch> [SuffIP_Marge] [Port]"
    echo "   SuffIP_Marge par défaut ce serveur : $SuffIP_Marge"
    echo "   Port par défaut 8000"
    echo "   Exemple : $0 99 253 8001"
	exit 1
fi

BASE_RESEAU=$(hostname -I | cut -d' ' -f1 | cut -d. -f1-3)
ipST="${BASE_RESEAU}.$1"
ipMarge="${BASE_RESEAU}.${2:-$SuffIP_Marge}"

# Port par défaut si non renseigné (ex: 8000) ou récupération du 3ème argument
port=${3:-8000}

echo "Configuration : ST=$ipST | Marge=$ipMarge | Port=$port"

# Définition des fichiers de log
LOG_AVANT="/tmp/avant${1}.log"
LOG_APRES="/tmp/apres${1}.log"

# Commandes NC
send_cmd() {
    printf '%s\n' "$1" | nc -w 2 $ipST 17000
}

send_cmd "getpdo CurrentSystemConfiguration" > "$LOG_AVANT"

send_cmd "sys configuration bmxRegistryUrl http://${ipMarge}:${port}/bmx/registry/v1/services" >/dev/null 2>&1
send_cmd "sys configuration bmxRegistryUrl http://${ipMarge}:${port}/bmx/registry/v1/services" >/dev/null 2>&1
send_cmd "sys configuration statsServerUrl http://${ipMarge}:${port}" >/dev/null 2>&1
send_cmd "envswitch boseurls set http://${ipMarge}:${port}/marge http://${ipMarge}:${port}/updates/soundtouch" >/dev/null 2>&1
# send_cmd "sys configuration margeServerUrl http://${ipMarge}:${port}/marge" >/dev/null 2>&1
# send_cmd "sys configuration swUpdateUrl http://${ipMarge}:${port}/updates/soundtouch" >/dev/null 2>&1
# send_cmd "envswitch boseurls set http://${ipMarge}:${port}/marge http://${ipMarge}:${port}/updates/soundtouch" >/dev/null 2>&1

send_cmd "getpdo CurrentSystemConfiguration" > "$LOG_APRES"

send_cmd "sys reboot" >/dev/null 2>&1

# ==============================================================================
# BLOC DE VÉRIFICATION ET COMPTE-RENDU (TABLEAU)
# ==============================================================================
echo -n "Vérification de la configuration... "

# Si les fichiers n'existent pas ou sont vides, on s'arrête
if [ ! -s "$LOG_AVANT" ] || [ ! -s "$LOG_APRES" ]; then
    echo "ÉCHEC (Fichier de log vide ou introuvable)"
    exit 1
fi

# Fonction interne pour extraire proprement la valeur textuelle du log non-XML
get_val() {
    local key="$1"
    local file="$2"
    # Cherche la clé, prend la ligne suivante, isole ce qui est entre guillemets
    grep -A 1 "${key}" "$file" | grep "text:" | cut -d'"' -f2
}

# Extraction des valeurs AVANT
av_marge=$(get_val "margeServerUrl" "$LOG_AVANT")
av_stats=$(get_val "statsServerUrl" "$LOG_AVANT")
av_update=$(get_val "swUpdateUrl" "$LOG_AVANT")
av_bmx=$(get_val "bmxRegistryUrl" "$LOG_AVANT")

# Extraction des valeurs APRÈS
val_marge=$(get_val "margeServerUrl" "$LOG_APRES")
val_stats=$(get_val "statsServerUrl" "$LOG_APRES")
val_update=$(get_val "swUpdateUrl" "$LOG_APRES")
val_bmx=$(get_val "bmxRegistryUrl" "$LOG_APRES")

# Les valeurs attendues théoriques
attendu_marge="http://${ipMarge}:${port}/marge"
attendu_stats="http://${ipMarge}:${port}"
attendu_update="http://${ipMarge}:${port}/updates/soundtouch"
attendu_bmx="http://${ipMarge}:${port}/bmx/registry/v1/services"

# Comparaison des résultats pour le statut global
if [ "$val_marge" = "$attendu_marge" ] && \
   [ "$val_stats" = "$attendu_stats" ] && \
   [ "$val_update" = "$attendu_update" ] && \
   [ "$val_bmx" = "$attendu_bmx" ]; then
    GLOBAL_STATUS="OK"
else
    GLOBAL_STATUS="ÉCHEC (Valeurs non conformes)"
fi

echo "$GLOBAL_STATUS"
echo ""

# Affichage du tableau formaté
printf "| %-17s | %-50s | %-50s |\n" "Variables" "Avant" "Après"
printf "|-%-17s-|-%-50s-|-%-50s-|\n" "-----------------" "--------------------------------------------------" "--------------------------------------------------"
printf "| %-17s | %-50s | %-50s |\n" "margeServerUrl" "${av_marge:-Vide}" "$val_marge"
printf "| %-17s | %-50s | %-50s |\n" "statsServerUrl" "${av_stats:-Vide}" "$val_stats"
printf "| %-17s | %-50s | %-50s |\n" "swUpdateUrl" "${av_update:-Vide}" "$val_update"
printf "| %-17s | %-50s | %-50s |\n" "bmxRegistryUrl" "${av_bmx:-Vide}" "$val_bmx"

echo ""

if [ "$GLOBAL_STATUS" != "OK" ]; then
    exit 1
fi
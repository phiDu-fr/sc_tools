#!/usr/bin/env bash

# Changement de l'accountId sous la forme 1234567

# Vérification du nombre d'arguments minimum (au moins 2)
if [ $# -lt 2 ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch> <AccountId>"
    echo "   Exemple : $0 65 7654321"
    exit 1
fi

BASE_RESEAU=$(hostname -I | cut -d' ' -f1 | cut -d. -f1-3)
ipST="${BASE_RESEAU}.$1"
Id="$2" # Correction ici : $Id n'était pas défini correctement avant

echo "Configuration : ST=$ipST | AccountId=$Id" # Correction : Guillemet fermante ajoutée

# Définition des fichiers de log
LOG_AVANT="/tmp/avant${1}.log"
LOG_APRES="/tmp/apres${1}.log"

# Commandes NC
echo "envswitch AccountId get" | timeout 2 nc "$ipST" 17000 > "$LOG_AVANT"

echo "envswitch AccountId set $Id" | timeout 2 nc "${ipST}" 17000 >/dev/null 2>&1

echo "envswitch AccountId get" | timeout 2 nc "$ipST" 17000 > "$LOG_APRES"

echo "sys reboot" | timeout 1 nc "$ipST" 17000 >/dev/null 2>&1

# ==============================================================================
# BLOC DE VÉRIFICATION ET COMPTE-RENDU (TABLEAU)
# ==============================================================================
echo -n "Vérification de la configuration... "

# Si les fichiers n'existent pas ou sont vides, on s'arrête
if [ ! -s "$LOG_AVANT" ] || [ ! -s "$LOG_APRES" ]; then
    echo "ÉCHEC (Fichier de log vide ou introuvable)"
    exit 1
fi

# Fonction interne adaptée pour isoler la valeur après les deux-points (ex: "AccountId: 5476585")
get_val() {
    local file="$2"
    # Cherche la ligne EnvSwitch, isole ce qui est après les deux-points et nettoie les espaces
    grep "EnvSwitch AccountId:" "$file" | cut -d':' -f2 | tr -d '[:space:]'
}

# Extraction des valeurs
av_account=$(get_val "AccountId" "$LOG_AVANT")
val_account=$(get_val "AccountId" "$LOG_APRES")

# Comparaison avec l'Id attendu passé en paramètre
if [ "$val_account" = "$Id" ]; then
    GLOBAL_STATUS="OK"
else
    GLOBAL_STATUS="ÉCHEC (Valeur non conforme)"
fi

echo "$GLOBAL_STATUS"
echo ""

# Affichage du tableau formaté
printf "| %-17s | %-25s | %-25s |\n" "Variables" "Avant" "Après"
printf "|-%-17s-|-%-25s-|-%-25s-|\n" "-----------------" "-------------------------" "-------------------------"
printf "| %-17s | %-25s | %-25s |\n" "AccountId" "${av_account:-Vide}" "$val_account"

echo ""

if [ "$GLOBAL_STATUS" != "OK" ]; then
    exit 1
fi
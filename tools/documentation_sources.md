# Documentation des codes sources
Généré le \2026-\08-\18 \15:\33:\05

## Arborescence du projet

```text
.
├── blankPresetST.sh
├── change_accountId.sh
├── change_cfg.sh
├── change_ip.sh
├── change_marge.sh
├── change_speaker.sh
├── check_mp3.sh
├── chrono.sh
├── cmdST.sh
├── control_data.sh
├── cp_nas.sh
├── create_data.sh
├── create_remote_services.sh
├── discoverST.sh
├── docker_menage.sh
├── install
│   ├── install_chatgpt.sh
│   ├── install_copilot.sh
│   └── install.sh
├── lireMP3.sh
├── md_doc.sh
├── mesure_reboot.sh
├── presets_check.sh
├── presets_update.sh
├── py
│   ├── apple_logos.py
│   ├── bose_optimizer.py
│   ├── deezer_logos.py
│   ├── discoverST.py
│   ├── get_covers.py
│   ├── iTunes_logos.py
│   ├── lireMP3.py
│   ├── mp3AllInOne.py
│   ├── root_speaker.py
│   ├── update_radio_logo.py
│   └── ws_bose.py
├── radio_browser.sh
├── reboot_raspberry.sh
├── rebootST.sh
├── rebuild_minidlna.sh
├── removeCovers.sh
├── reset_bt.sh
├── resetStateST.sh
├── rootST.sh
├── sauve.sh
├── scanLan.sh
├── send_key.sh
├── setup_audio_daemon.sh
├── sources_update.sh
├── ST10stereo.sh
├── swapRpiZero2.sh
├── wifi_discover.sh
└── wifi_setup.sh

3 directories, 51 files
```
<br>

---

## Fichiers sources

### `blankPresetST.sh`

```bash
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
```
<br>

### `change_accountId.sh`

```bash
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
```
<br>

### `change_cfg.sh`

```bash
#!/usr/bin/env bash
# ------------------------------------------------------------
#  Mise à jour sécurisée des fichiers de configuration Docker
#  (docker‑compose.yml, Dockerfile, requirements.txt)
#  pour les projets :
#      • /home/pi/soundcork
#      • /home/pi/soundcork-stockholm-app
#
#  Fonctionnalités
#  • Vérifie l’existence des fichiers avant toute opération
#  • Crée des sauvegardes horodatées (au lieu d’un simple .bak)
#  • Utilise des copies atomiques (tmp → destination)
#  • Journalise chaque étape dans $LOGFILE
#  • S’arrête immédiatement en cas d’erreur (set -e)
# ------------------------------------------------------------

set -euo pipefail               # Arrêt sur erreur, variables non définies, pipelines sécurisés
IFS=$'\n\t'                     # Gestion sûre des espaces dans les noms de fichiers

echo "  Mise à jour sécurisée des fichiers de configuration Docker"
echo "  (docker‑compose.yml, Dockerfile, requirements.txt)"
echo "  pour les projets :"
echo "      • /home/pi/soundcork"
echo "      • /home/pi/soundcork-stockholm-app"
echo
echo  "  Fonctionnalités"
echo  "     • Vérifie l’existence des fichiers avant toute opération"
echo  "     • Crée des sauvegardes horodatées (au lieu d’un simple .bak)"
echo  "     • Utilise des copies atomiques (tmp → destination)"
echo  "     • Journalise chaque étape dans LOGFILE"
echo  "    • S’arrête immédiatement en cas d’erreur (set -e)"
# --- DEMANDE DE CONFIRMATION ---
echo  
read -p "Voulez-vous lancer la mise à jour ? (O/n) : " confirm
if [[ ! "$confirm" =~ ^[Oo]$ ]] && [[ "$confirm" != "" ]]; then
    echo "❌ Opération annulée."
    exit 0
fi
echo



# ------------------------------------------------------------------
# Variables globales
# ------------------------------------------------------------------
LOGFILE="/home/pi/update_templates_$(date +%Y%m%d_%H%M%S).log"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Fonction d’affichage + log
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"
}

# Fonction de sauvegarde (avec horodatage)
backup_file() {
    local src=$1
    local dst="${src}.bak_${TIMESTAMP}"
    if [[ -e "$src" ]]; then
        cp -a "$src" "$dst"
        log "Sauvegarde de $src → $dst"
    else
        log "⚠️  $src n’existe pas, aucune sauvegarde créée"
    fi
}

# Fonction de remplacement atomique
replace_with_template() {
    local target=$1
    local template="${target}.etalon"

    if [[ -f "$template" ]]; then
		# Copie vers un fichier temporaire puis déplacement atomique
		local tmp="${target}.tmp_${TIMESTAMP}"
		cp -a "$template" "$tmp"
		mv -f "$tmp" "$target"
		log "Remplacement de $target par $template"
    else    
		log "❌  Modèle manquant : $template"
        # exit 1
    fi

}

# ------------------------------------------------------------------
# Traitement d’un répertoire de projet
# ------------------------------------------------------------------
process_project() {
    local proj_dir=$1
    log "=== Traitement du projet : $proj_dir ==="

    pushd "$proj_dir" > /dev/null

    # Liste des fichiers à gérer
    local files=(
        "docker-compose.yml"
        "Dockerfile"
        "requirements.txt"
        ".env"
		"config/backend-config.json"
    )

    for f in "${files[@]}"; do
        backup_file "$f"
        replace_with_template "$f"
    done

    popd > /dev/null
    log "=== Fin du projet $proj_dir ==="
}

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
log "=== DÉBUT du script ==="
log "Log complet → $LOGFILE"

# Tableau des projets à mettre à jour
PROJECTS=(
    "/home/pi/soundcork"
    "/home/pi/soundcork-stockholm-app"
)

for p in "${PROJECTS[@]}"; do
    if [[ -d "$p" ]]; then
        process_project "$p"
    else
        log "⚠️  Répertoire introuvable : $p"
    fi
done

log "=== SCRIPT TERMINÉ ==="

```
<br>

### `change_ip.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail               # Arrêt sur erreur, variables non définies, pipelines sécurisés
IFS=$'\n\t'                     # Gestion sûre des espaces dans les noms de fichiers

# IP locale
LOCAL_IP=$(hostname -I|awk '{print $1}')
echo "IP locale : $LOCAL_IP"
cd /home/pi

# fichiers à traiter
files=(
./soundcork/docker-compose.yml
./soundcork-stockholm-app/docker-compose.yml
./soundcork-stockholm-app/.env
)

#./soundcork/soundcork/.env.private:base_url
#./soundcork-stockholm-app/.env

for entry in "${files[@]}"; do
  file="${entry%%:*}"
  [[ -f "$file" ]]||{ echo "⚠️  $file absent ; skip"; continue; }
  echo -e "\n---\nFichier : $file"
  # read -rp "Remplacer l'IP dans ce fichier ? [o/N] " ans
  # [[ "$ans" =~ ^[oO]$ ]]||continue
  cp "$file" "${file}.bak"
  sed -i "s/{@margeIP@}/${LOCAL_IP}/g" "$file"
  #sed -i -E "s/[0-9]{1,3}(\.[0-9]{1,3}){3}/${LOCAL_IP}/g" "$file"
done

```
<br>

### `change_marge.sh`

```bash
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
```
<br>

### `change_speaker.sh`

```bash
#!/bin/bash

# Chemins de configuration
PYTHON_FILE="/home/pi/sc_tools/tools/py/virtual_soundtouch.py"
SERVICE_NAME="virtual_soundtouch.service"

echo "=========================================="
echo "   REMPLACEMENT DE L'ENCEINTE BLUETOOTH   "
echo "=========================================="

# Demander la nouvelle adresse MAC
read -p "Entrez l'adresse MAC de la nouvelle enceinte (ex: 11:22:33:44:55:66) : " NEW_MAC

# Vérification du format de l'adresse MAC
if [[ ! "$NEW_MAC" =~ ^([a-fA-F0-9]{2}:){5}[a-fA-F0-9]{2}$ ]]; then
    echo "❌ Erreur : Format d'adresse MAC invalide."
    exit 1
fi

# Convertir en majuscules pour être propre
NEW_MAC=$(echo "$NEW_MAC" | tr 'a-z' 'A-Z')

echo "Mise à jour du fichier Python..."
# Commande SED pour trouver et remplacer l'ancienne adresse MAC par la nouvelle
sed -i -E "s/JBL_MAC_ADDRESS = \"([A-Fa-f0-9:]+)\"/JBL_MAC_ADDRESS = \"$NEW_MAC\"/" $PYTHON_FILE

echo "Redémarrage de l'émulateur..."
sudo systemctl restart $SERVICE_NAME

echo "✅ Terminé ! Le système enverra désormais l'audio vers $NEW_MAC."



```
<br>

### `check_mp3.sh`

```bash
#!/bin/bash

# 1. Création du fichier de log horodaté dans le dossier actuel
LOG_FILE="$(pwd)/mp3_maintenance_$(date +%Y%m%d_%H%M%S).log"
echo "=== Début de la session : $(date) ===" > "$LOG_FILE"

# Fonction simplifiée pour afficher à l'écran ET écrire dans le log
log_msg() {
    echo "$1"
    echo "[$(date +'%H:%M:%S')] $1" >> "$LOG_FILE"
}

echo "Le journal d'activité sera sauvegardé ici : $LOG_FILE"
echo ""

# 2. Demander le dossier à scanner
read -p "Entrez le chemin absolu du dossier contenant vos MP3 : " TARGET_DIR

if [ ! -d "$TARGET_DIR" ]; then
    log_msg "Erreur : Le dossier '$TARGET_DIR' n'existe pas. Arrêt."
    exit 1
fi

log_msg "Dossier cible défini sur : $TARGET_DIR"

# 3. Fonction pour vérifier et installer les dépendances
check_dependency() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "L'outil '$1' n'est pas installé."
        read -p "Voulez-vous installer '$1' via APT ? (o/n) : " INSTALL
        if [[ "$INSTALL" =~ ^[oO]$ ]]; then
            sudo apt update && sudo apt install -y "$1"
            log_msg "Installation de $1 réussie."
        else
            log_msg "Le script a besoin de '$1' pour continuer. Arrêt."
            exit 1
        fi
    fi
}

echo ""
echo "Vérification des outils nécessaires..."
check_dependency mp3val
check_dependency mp3gain

# 4. Menu des options
echo ""
echo "=== BOÎTE À OUTILS MP3 ==="
echo "1) Réparer uniquement (mp3val - avec création de sauvegardes .bak)"
echo "2) Normaliser uniquement (mp3gain - piste par piste, avec anti-saturation)"
echo "3) Traitement complet (Réparer PUIS Normaliser)"
read -p "Choisissez une option (1, 2 ou 3) : " OPTION

echo ""
log_msg "Option choisie : $OPTION"
log_msg "Lancement du traitement..."

# L'utilisation de '2>&1 | tee -a' permet de voir la progression à l'écran 
# TOUT EN écrivant le résultat dans le fichier log.

case $OPTION in
    1)
        log_msg "--- Étape : Réparation ---"
        find "$TARGET_DIR" -type f -iname "*.mp3" -exec mp3val -f {} + 2>&1 | tee -a "$LOG_FILE"
        log_msg "Réparation terminée."
        ;;
    2)
        log_msg "--- Étape : Normalisation ---"
        find "$TARGET_DIR" -type f -iname "*.mp3" -exec mp3gain -r -k {} + 2>&1 | tee -a "$LOG_FILE"
        log_msg "Normalisation terminée."
        ;;
    3)
        log_msg "--- Étape 1/2 : Réparation ---"
        find "$TARGET_DIR" -type f -iname "*.mp3" -exec mp3val -f {} + 2>&1 | tee -a "$LOG_FILE"
        
        log_msg "--- Étape 2/2 : Normalisation ---"
        find "$TARGET_DIR" -type f -iname "*.mp3" -exec mp3gain -r -k {} + 2>&1 | tee -a "$LOG_FILE"
        
        log_msg "Traitement complet terminé."
        ;;
    *)
        log_msg "Option invalide. Arrêt du script."
        exit 1
        ;;
esac

# 5. Nettoyage optionnel des sauvegardes
if [[ "$OPTION" == "1" || "$OPTION" == "3" ]]; then
    echo ""
    read -p "Voulez-vous SUPPRIMER définitivement les sauvegardes corrompues (.bak) ? (o/n) : " CLEAN
    if [[ "$CLEAN" =~ ^[oO]$ ]]; then
        find "$TARGET_DIR" -type f -name "*.bak" -delete
        log_msg "Nettoyage : Fichiers .bak supprimés."
    else
        log_msg "Nettoyage : Fichiers .bak conservés."
    fi
fi

log_msg "=== Fin de la session ==="
echo ""
echo "Vous pouvez consulter le rapport complet en tapant : cat $LOG_FILE"

```
<br>

### `chrono.sh`

```bash
#!/bin/bash

# Vérification qu'au moins un argument (le script cible) est fourni
if [ $# -eq 0 ]; then
    echo "❌ Erreur : Aucun script spécifié."
    echo "💡 Utilisation : $0 <commande_ou_script> [param1] [param2] ..."
    exit 1
fi

echo "🚀 Lancement de : $@"
echo "-----------------------------------"

# 1. Enregistrement du temps de début (secondes.nanosecondes)
START_TIME=$(date +%s.%N)

# 2. Exécution du script cible avec TOUS ses paramètres ("$@")
# Les guillemets sont obligatoires pour préserver les espaces dans les arguments
"$@"

# 3. Sauvegarde du code de retour du script exécuté (succès=0, erreur>0)
EXIT_CODE=$?

# 4. Enregistrement du temps de fin
END_TIME=$(date +%s.%N)

echo "-----------------------------------"

# 5. Calcul de la différence avec awk (plus standard et évite d'installer 'bc')
DURATION=$(awk "BEGIN {printf \"%.3f\", $END_TIME - $START_TIME}")

# Affichage du résultat
echo "⏱️  Durée d'exécution : $DURATION secondes."

# 6. On quitte en renvoyant le code d'erreur exact du script d'origine
exit $EXIT_CODE
```
<br>

### `cmdST.sh`

```bash
#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch | All> <cmd>"
    echo "   Exemple : $0 65 info"
    exit 1
fi

cmd="/$2"

# Détection automatique du réseau local (ex: 192.168.1)
NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)

echo "🔎 Détection SoundTouch via Zeroconf + API..."
echo

# Vérifier si avahi-browse est installé
if ! command -v avahi-browse >/dev/null 2>&1; then
	echo "❌ avahi-browse n'est pas installé."
	echo "   Installe-le avec : sudo apt install avahi-utils"
	exit 1
fi

echo '<speakers>'
if [[ "${1,,}" == "all" ]]; then

	avahi-browse -rt _soundtouch._tcp 2>/dev/null | while read -r line; do

		# Détection d'une ligne contenant l'adresse
		if echo "$line" | grep -q "address ="; then
			
			# Extraction robuste de l'IP sans sed
			IP=$(echo "$line" | cut -d'[' -f2 | cut -d']' -f1)

			echo "<speaker IP='${IP}'>"
				curl -s "http://${IP}:8090${cmd}"
			echo '</speaker>'
		fi

	done

else
	IP="${NET}.$1"
		if curl -s --connect-timeout 0.3 http://$IP:8090/name >/dev/null; then
			echo "<speaker IP='$IP'>"
				curl -s http://${IP}:8090${cmd}
			echo '</speaker>'
		else
			echo "<speaker IP='$IP'/>"
		fi
fi
echo '</speakers>'
echo ""
echo ""

# echo "Redémarrage de la machine locale…"
# sudo reboot -n

```
<br>

### `control_data.sh`

```bash
#!/bin/bash

# Construit un fichier Soundtouch.ini contenant constituant les données de la base Soundcork
# Aucune utilité pour soundcork mais rend les données lisibles

# Fait un compte rendu final pour s'assurer que toutes les enceintes soient bien sur le même compte
 
BASE_DIR="/home/pi/soundcork/dataX"
INI_FILE="$BASE_DIR/Soundtouch.ini"

TMP_INI="/tmp/Soundtouch.ini.tmp"

declare -A UUID_COUNT
declare -A UUID_NAMES

if [ ! -d "$BASE_DIR" ]; then
    echo "Le répertoire $BASE_DIR n'existe pas ou n'est pas le bon"
    echo "Lancez au préalable create_data.sh ou vérifiez si $BASE_DIR est aussi dans create_data"
    exit 1
fi

echo "Analyse des DeviceInfo.xml..."

# Initialisation du fichier INI
echo "[Compte]" > "$TMP_INI"
echo "margeAccountUUID=" >> "$TMP_INI"

while read xmlfile
do

compte=$(xmlstarlet sel -t -v "//margeAccountUUID" "$xmlfile" 2>/dev/null | tr -d '\r\n\t ')
nom=$(xmlstarlet sel -t -v "//name" "$xmlfile" 2>/dev/null | tr -d '\r')
dev_id=$(xmlstarlet sel -t -v "//info/@deviceID" "$xmlfile" 2>/dev/null | tr -d '\r')
type=$(xmlstarlet sel -t -v "//type" "$xmlfile" 2>/dev/null | tr -d '\r')
marge_url=$(xmlstarlet sel -t -v "//margeURL" "$xmlfile" 2>/dev/null | tr -d '\r')

# Extraction de la première IP pour éviter les sauts de lignes
ip_xml=$(xmlstarlet sel -t -v "(//ipAddress)[1]" "$xmlfile" 2>/dev/null | tr -d '\r')

if [ -z "$dev_id" ]; then
    continue
fi

echo "Trouvé : $nom"
echo "DeviceID : $dev_id"
echo "UUID : $compte"
echo "IP : $ip_xml"
echo

# Comptage UUID
if [ -z "${UUID_COUNT[$compte]}" ]; then
    UUID_COUNT[$compte]=1
    UUID_NAMES[$compte]="$nom"
else
    UUID_COUNT[$compte]=$(( ${UUID_COUNT[$compte]} + 1 ))
    UUID_NAMES[$compte]="${UUID_NAMES[$compte]}, $nom"
fi

# Ajout section INI
echo "" >> "$TMP_INI"
echo "[$dev_id]" >> "$TMP_INI"
echo "nom=$nom" >> "$TMP_INI"
echo "ip=$ip_xml" >> "$TMP_INI"
echo "type=$type" >> "$TMP_INI"
echo "margeAccountUUID=$compte" >> "$TMP_INI"
echo "margeURL=$marge_url" >> "$TMP_INI"

done < <(find "$BASE_DIR" -type f -name "DeviceInfo.xml")

echo
echo "=============================="
echo "COMPTE RENDU"
echo "=============================="

UUID_TOTAL=0

for uuid in "${!UUID_COUNT[@]}"
do
UUID_TOTAL=$((UUID_TOTAL + 1))
done

if [ "$UUID_TOTAL" -eq 1 ]; then

for uuid in "${!UUID_COUNT[@]}"
do
    echo "Toutes les enceintes utilisent le même margeAccountUUID"
    echo
    echo "UUID : $uuid"

    sed -i "s|^margeAccountUUID=$|margeAccountUUID=$uuid|" "$TMP_INI"
done

else

echo "Plusieurs margeAccountUUID détectés"
echo

sed -i "s|^margeAccountUUID=$|margeAccountUUID=error|" "$TMP_INI"

for uuid in "${!UUID_COUNT[@]}"
do
    echo "UUID : $uuid"
    echo "Nombre : ${UUID_COUNT[$uuid]}"
    echo "Enceintes : ${UUID_NAMES[$uuid]}"
    echo
done

fi

mv "$TMP_INI" "$INI_FILE"

echo "INI mis à jour : $INI_FILE"

```
<br>

### `cp_nas.sh`

```bash
#!/bin/bash

nas="192.168.1.150"
usr="phd"
pwd=""
file="sc_tools.lasted.7z"

smbclient //$nas/web -U $usr%$pwd -c 'lcd  /media/ssd/.sauve; cd sc_tools ; put $file'
```
<br>

### `create_data.sh`

```bash
#!/usr/bin/env bash

# Créé l'arborescence propre à Soundtouch en scannant tout le réseau local
# et télécharge les fichiers XML associés à chaque enceinte, conforme à Soundcork

BASE_DIR="/home/pi/soundcork/dataX"
TIMEOUT=1

if [ -d "$BASE_DIR" ]; then
    rm -rf "$BASE_DIR"
fi

# ---------- 1. Détection automatique du réseau ----------
LOCAL_IP=$(hostname -I | awk '{print $1}')
[[ -z "$LOCAL_IP" ]] && exit 1

IP_RACINE=$(echo "$LOCAL_IP" | cut -d. -f1-3)
BASE_RESEAU="${IP_RACINE}."

mkdir -p "$BASE_DIR"

# ---------- 2. Fonction de traitement ----------
process_device() {

    local suffixe=$1
    local ip="${BASE_RESEAU}${suffixe}"
    local temp_xml="${BASE_DIR}/DeviceInfo_${suffixe}.xml"

    # ---------- Téléchargement du XML ----------
    if curl -sSf \
        --connect-timeout "$TIMEOUT" \
        --max-time 3 \
        "http://${ip}:8090/info" \
        -o "$temp_xml" 2>/dev/null; then

        # ---------- Extraction XML ----------
        local nom
        local compte
        local dev_id
        local ip_xml

        nom=$(xmlstarlet sel -t -v "//name" "$temp_xml" 2>/dev/null | tr -d '\r')
        compte=$(xmlstarlet sel -t -v "//margeAccountUUID" "$temp_xml" 2>/dev/null | tr -d '\r')
        dev_id=$(xmlstarlet sel -t -v "//info/@deviceID" "$temp_xml" 2>/dev/null | tr -d '\r')
        ip_xml=$(xmlstarlet sel -t -v "(//ipAddress)[1]" "$temp_xml" 2>/dev/null | tr -d '\r')

        : "${compte:=inconnu}"
        : "${nom:=enceinte_${suffixe}}"
        : "${ip_xml:=$ip}" # Valeur de secours si le XML est vide

        # ---------- Vérification ----------
        if [[ -n "$dev_id" ]]; then

            echo "🟢 TROUVÉ : $ip_xml ($nom)"

            local target_dir="$BASE_DIR/$compte/devices/$dev_id"

            mkdir -p "$target_dir"

            # Déplacement du fichier d'info principal
            mv "$temp_xml" "$target_dir/DeviceInfo.xml"

            # Fichier témoin avec le nom de l'enceinte
            touch "$target_dir/$nom"

            # ---------- Téléchargements secondaires ----------
            for xml_type in presets recents; do

                curl -sSf \
                    --connect-timeout "$TIMEOUT" \
                    "http://${ip_xml}:8090/${xml_type}" \
                    -o "$BASE_DIR/$compte/${xml_type^}.xml" \
                    2>/dev/null

            done
			
			if nc -z -w 2 ${ip_xml} "22" > /dev/null 2>&1; then
				ssh-keyscan -H ${ip_xml} >> ~/.ssh/known_hosts
				SOURCES="$BASE_DIR/$compte/Sources.xml"
				ssh  root@${ip_xml} cat /mnt/nv/BoseApp-Persistence/1/Sources.xml > $SOURCES
			
			BLOCK='<sourceItem source="RADIO_BROWSER" status="READY" isLocal="false" multiroomallowed="true"/>'

				# Vérifie si RADIO_BROWSER existe déjà
				if ! grep -q 'type="RADIO_BROWSER"' "$SOURCES"; then
					# Insère le bloc avant </sources>
					sed -i "/<\/sources>/i\\
				$BLOCK
				" "$SOURCES"

					echo "Bloc RADIO_BROWSER ajouté."
				else
					echo "Bloc RADIO_BROWSER déjà présent."
				fi
			fi
        else
            rm -f "$temp_xml"
        fi
    fi
}

# ---------- 3. Exécution ----------
echo "🔎 Scan en cours sur le réseau ${BASE_RESEAU}0/24..."

for s in {1..254}; do

    process_device "$s" &

    # Limitation des processus simultanés
    if (( s % 64 == 0 )); then
        wait
    fi

done

wait
# ---------- 4. fichier Sources.xml ----------
if ! find "$BASE_DIR" -type f -name "Sources.xml" -print -quit >/dev/null 2>&1; then
    cat <<'EOF' >"$SOURCES"
<?xml version='1.0' encoding='UTF-8'?>
<sources>
    <source id="100001" displayName="AUX IN" secret="" secretType="">
        <sourceKey type="AUX" account="AUX" />
        <createdOn />
        <updatedOn />
    </source>
    <source id="100002" displayName="" secret="" secretType="token">
        <sourceKey type="INTERNET_RADIO" account="" />
        <createdOn />
        <updatedOn />
    </source>
    <source id="100003" displayName="" secret="" secretType="">
        <sourceKey type="RADIO_BROWSER" account="" />
        <createdOn />
        <updatedOn />
    </source>
</sources>
EOF
fi

echo "🏁 Scan et création de l'arborescence terminés sur $BASE_DIR."

```
<br>

### `create_remote_services.sh`

```bash
#!/bin/bash

# Couleurs pour la clarté visuelle dans le terminal web
VERT='\033[0;32m'
ROUGE='\033[0;31m'
BLEU='\033[0;34m'
JAUNE='\033[1;33m'
NEUTRE='\033[0m'

# (Note : On retire la vérification root, car dans Docker, l'utilisateur est déjà root)

echo -e "${BLEU}🔍 Recherche d'une clé USB amovible en cours...${NEUTRE}"

# 1. Détection automatique : on cherche la première partition (type="part") sur un disque amovible (rm="1")
TARGET_DEV=$(lsblk -l -p -n -o NAME,RM,TYPE | awk '$2=="1" && $3=="part" {print $1}' | head -n 1)

if [ -z "$TARGET_DEV" ]; then
  echo -e "${ROUGE}❌ Aucune clé USB détectée. Branchez-en une et réessayez.${NEUTRE}"
  sleep 8
  exit 1
fi

# 2. Récupération des informations
DEV_SIZE=$(lsblk -n -o SIZE "$TARGET_DEV")
PARENT_DEV=$(lsblk -n -o PKNAME "$TARGET_DEV")
DEV_MODEL=$(lsblk -n -o MODEL "/dev/$PARENT_DEV" | xargs)

echo -e "${VERT}✅ Clé trouvée : $TARGET_DEV${NEUTRE}"
echo -e "   Modèle  : ${DEV_MODEL:-Inconnu}"
echo -e "   Taille  : $DEV_SIZE"

# Vérifie si elle est déjà montée quelque part
MOUNT_STATE=$(lsblk -n -o MOUNTPOINT "$TARGET_DEV")
if [ -n "$MOUNT_STATE" ]; then
    echo -e "   Statut  : Actuellement montée sur $MOUNT_STATE"
else
    echo -e "   Statut  : Non montée (Prête)"
fi
echo "---------------------------------------------------"

# 3. Sécurité : Demande de confirmation
echo -e "${JAUNE}⚠️  ATTENTION : Le périphérique $TARGET_DEV va être ENTIÈREMENT FORMATÉ en FAT32.${NEUTRE}"
read -p "Confirmez-vous que c'est bien la bonne clé ? (o/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Oo]$ ]]; then
    echo -e "${ROUGE}❌ Opération annulée par l'utilisateur.${NEUTRE}"
    sleep 8
    exit 1
fi

MOUNT_POINT="/mnt/usb_temp_setup"

# 4. Démontage forcé par sécurité
echo -e "${BLEU}➡️  Démontage de la clé (Gestion de l'isolation Docker)...${NEUTRE}"
# 1. Démontage dans la bulle du conteneur
umount -f "$TARGET_DEV" 2>/dev/null
# 2. Astuce magique : On utilise Docker pour forcer le Raspberry Pi (l'hôte) à relâcher la clé !
docker run --rm --privileged --pid=host python:3.12-slim nsenter -t 1 -m umount -f "$TARGET_DEV" 2>/dev/null
sleep 2 

# 5. L'astuce Ultime : Exécuter toute la séquence matérielle directement sur le Raspberry Pi hôte
echo -e "${BLEU}➡️  Formatage, montage et création du fichier (Exécution sur l'hôte)...${NEUTRE}"

# On utilise le socket Docker pour ordonner au Raspberry Pi de tout faire d'une traite !
docker run --rm --privileged --pid=host python:3.12-slim nsenter -t 1 -m bash -c "
    mkfs.vfat -F 32 -I $TARGET_DEV > /dev/null && \
    mkdir -p $MOUNT_POINT && \
    mount -t vfat $TARGET_DEV $MOUNT_POINT && \
    touch $MOUNT_POINT/remote_services && \
    sync && \
    umount $MOUNT_POINT && \
    rmdir $MOUNT_POINT
"

if [ $? -ne 0 ]; then
    echo -e "${ROUGE}❌ Erreur critique lors de l'opération sur l'hôte.${NEUTRE}"
    echo "L'hôte n'a pas pu formater ou écrire sur la clé."
    sleep 8
    exit 1
fi

echo -e "${VERT}🎉 Opération terminée avec succès ! Vous pouvez retirer la clé.${NEUTRE}"
echo -e "Cette clé contient un seul fichier 'remote_services' à placer dans le port d'une enceinte."
echo -e "Débranchez l'enceinte du secteur, attendez 2 mn, rebranchez, attendez 3 à 4mn. Elle sera accessible via ssh root@{adresseIP}."

sleep 4
exit 0
```
<br>

### `discoverST.sh`

```bash
#!/bin/bash

# ==========================================
# PARAMÉTRAGES
# ==========================================
SUBNET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)
STATIC_IPS=""

# Création d'un fichier temporaire pour stocker les IPs trouvées (gère le compteur et évite les doublons)
TMP_FILE=$(mktemp)
trap "rm -f $TMP_FILE" EXIT

# ==========================================
# FONCTION COMMUNE : EXTRACTION ET AFFICHAGE
# ==========================================
extract_and_print() {
    local IP=$1
    local XML=$2

    if [ -n "$XML" ]; then
        local NAME=$(echo "$XML" | grep -oPm1 "(?<=<name>)[^<]+")
        
        if [ -n "$NAME" ]; then
            # --- GESTION DES DOUBLONS ---
            # Si l'IP est déjà dans le fichier temporaire, on ignore (utile pour le mode -b)
            if grep -q "^${IP}$" "$TMP_FILE" 2>/dev/null; then
                return
            fi
            
            # On enregistre l'IP dans le fichier temporaire
            echo "$IP" >> "$TMP_FILE"

            # --- EXTRACTION ---
            local TYPE=$(echo "$XML" | grep -oPm1 "(?<=<type>)[^<]+")
            local DEVICEID=$(echo "$XML" | grep -oP 'deviceID="\K[^"]+')
            local COMPTE=$(echo "$XML" | grep -oPm1 "(?<=<margeAccountUUID>)[^<]+")
            local MARGE=$(echo "$XML" | grep -oPm1 "(?<=<margeURL>)[^<]+")
            
            [ -z "$COMPTE" ] && COMPTE="Non renseigné"

            # Un seul bloc 'echo -e' pour éviter l'entrelacement
            echo -e "➡️  IP       : $IP\n   Nom      : $NAME\n   Modèle   : $TYPE\n   DeviceID : $DEVICEID\n   Compte   : $COMPTE\n   Marge    : $MARGE\n-----------------------------------"
        fi
    fi
}

# ==========================================
# MÉTHODE 1 : SCAN BRUTE FORCE
# ==========================================
scan_brute_force() {
    echo "🔎 Scan brute force du réseau ${SUBNET}.1 à 254..."
    echo "⏳ Patientez environ 2 secondes..."
    echo "-----------------------------------"

    check_device_brute() {
        local IP=$1
        local XML=$(curl -s --connect-timeout 1 --max-time 1.5 "http://$IP:8090/info")
        extract_and_print "$IP" "$XML"
    }

    for i in {1..254}; do
        check_device_brute "${SUBNET}.${i}" &
    done

    wait
}

# ==========================================
# MÉTHODE 2 : ZEROCONF / mDNS + STATIQUE
# ==========================================
scan_mdns() {
    echo "🔎 Détection SoundTouch (Hybride : Zeroconf + IPs statiques)..."
    echo "-----------------------------------"

    if command -v avahi-browse >/dev/null 2>&1; then
        MDNS_IPS=$(avahi-browse -rtp _soundtouch._tcp 2>/dev/null | grep "^=" | grep ";IPv4;" | cut -d';' -f8)
    else
        echo "⚠️ avahi-browse non installé. On utilise uniquement les IPs statiques."
        MDNS_IPS=""
    fi

    ALL_IPS=$(echo -e "${MDNS_IPS}\n${STATIC_IPS}" | sort -u | grep -v '^$')

    for IP in $ALL_IPS; do
        # On vérifie ici aussi pour ne pas faire de curl inutile si on vient du mode -b
        if grep -q "^${IP}$" "$TMP_FILE" 2>/dev/null; then
            continue
        fi

        # --- Attente et récupération de /info en une seule étape ---
        local XML=""
        for i in {1..4}; do
            XML=$(curl -s --connect-timeout 2 --max-time 3 "http://$IP:8090/info")
            if [ -n "$XML" ]; then
                break # Le XML a été récupéré, on sort de la boucle
            fi
            sleep 0.5
        done

        if [ -z "$XML" ]; then
            echo -e "➡️  IP       : $IP\n   ⚠️ API indisponible (pas de réponse sur /info)\n-----------------------------------"
            continue
        fi

        extract_and_print "$IP" "$XML"
    done
}

# ==========================================
# POINT D'ENTRÉE DU SCRIPT (GESTION DES PARAMÈTRES)
# ==========================================
echo "DEBUG : L'argument reçu est : '$1'"
case "$1" in
    "-f")
        scan_brute_force
        ;;
    "-b")
        scan_mdns
        echo ""
        scan_brute_force
        ;;
    "-m"|*)
        scan_mdns
        ;;
esac

# ==========================================
# COMPTEUR FINAL
# ==========================================
TOTAL_FOUND=$(wc -l < "$TMP_FILE")

echo "✅ Scan terminé ! $TOTAL_FOUND appareil(s) SoundTouch trouvé(s)."
```
<br>

### `docker_menage.sh`

```bash
#!/bin/bash

# Couleurs pour rendre la console jolie
VERT='\033[0;32m'
BLEU='\033[0;34m'
NEUTRE='\033[0m'

echo -e "${BLEU}📊 [1/5] État de l'espace Docker avant nettoyage :${NEUTRE}"
docker system df
df /home/pi

echo -e "\n${BLEU}🧹 [2/5] Nettoyage du cache de build (BuildKit)...${NEUTRE}"
docker builder prune -a -f

echo -e "\n${BLEU}🗑️ [3/5] Suppression des images non utilisées...${NEUTRE}"
docker image prune -a -f

echo -e "\n${BLEU}🗑️ [4/5] Suppression des conteneurs arrêtés et images fantômes...${NEUTRE}"
# Le flag -f évite la demande de confirmation (y/N)
docker system prune -f

echo -e "\n${VERT}✨ [5/5] Nettoyage terminé ! Nouvel état de l'espace :${NEUTRE}"
docker system df
df /home/pi

```
<br>

### `install/install_chatgpt.sh`

```bash
#!/bin/bash

set -e

echo "=================================="
echo " Installation Soundcork"
echo "=================================="

# Vérification utilisateur
if [ "$USER" != "pi" ]; then
    echo "Le script doit être exécuté avec l'utilisateur pi"
    exit 1
fi

echo "[1/12] Mise à jour système"

sudo apt update
sudo apt upgrade -y

echo "[2/12] Installation des outils de base"

sudo apt install -y \
    p7zip-full \
    curl \
    git \
    samba \
    cron

echo "[3/12] Installation sc_tools"

curl -o ~/sc_tools.lasted.7z \
http://phd.dsmynas.net/sc_tools/sc_tools.lasted.7z

7z x ~/sc_tools.lasted.7z -o$HOME

rm ~/sc_tools.lasted.7z

find ~/sc_tools/ -type f -exec chmod 666 {} +
find ~/sc_tools/ -type f -name "*.sh" -exec chmod 775 {} +
find ~/sc_tools/ -type d -exec chmod 777 {} +

echo "[4/12] Activation cron Soundcork"

sudo ln -sf \
/home/pi/sc_tools/data/soundcork_cron \
/etc/cron.d/soundcork_cron

echo "[5/12] Installation Docker"

curl -fsSL https://get.docker.com -o get-docker.sh

sudo sh get-docker.sh

sudo usermod -aG docker pi

echo "[6/12] Installation des paquets complémentaires"

if [ -f ~/sc_tools/docs/paquets_a_installer.txt ]; then
    sudo apt-get install \
        $(cat ~/sc_tools/docs/paquets_a_installer.txt) \
        -y
fi

sudo apt autoremove --purge -y

echo "[7/12] Désactivation services inutiles"

sudo systemctl stop nginx 2>/dev/null || true
sudo systemctl disable nginx 2>/dev/null || true

sudo systemctl stop minidlna.service 2>/dev/null || true
sudo systemctl disable minidlna.service 2>/dev/null || true

echo "[8/12] Alias bash"

grep -q "alias ll=" ~/.bashrc || \
echo "alias ll='ls -la'" >> ~/.bashrc

echo "[9/12] Configuration Samba"

sudo tee /etc/samba/smb.conf > /dev/null <<'EOF'
[global]
       deadtime = 15
       disable netbios = Yes
       disable spoolss = Yes
       dns proxy = No
       load printers = No
       logging = file
       map to guest = Bad User
       max log size = 1000
       printcap name = /dev/null
       security = USER
       server min protocol = SMB2
       server role = standalone server
       smb ports = 445
       socket options = TCP_NODELAY IPTOS_LOWDELAY
       idmap config * : backend = tdb
       posix locking = No
       printing = bsd
       strict locking = No
       use sendfile = Yes
       veto files = /.git/node_modules/.cache/

[pi]
       create mask = 0777
       directory mask = 0777
       force user = pi
       guest ok = Yes
       level2 oplocks = No
       oplocks = No
       path = /home/pi
       read only = No
EOF

(
echo "pi"
echo "pi"
) | sudo smbpasswd -a -s pi

echo "[10/12] Installation Soundcork"

cd ~

if [ ! -d ~/soundcork ]; then
    git clone https://github.com/deborahgu/soundcork.git
fi

if [ ! -d ~/soundcork-stockholm-app ]; then
    git clone https://github.com/krahl/soundcork-stockholm-app.git
fi

echo "[11/12] Copie des fichiers étalon"

cd ~/sc_tools/docs

find . -type f -name "*.etalon" \
-exec cp --parents {} ~/ \;

echo "[12/12] Configuration SSH"

mkdir -p ~/.ssh

grep -q "192.168.1.*" ~/.ssh/config 2>/dev/null || cat >> ~/.ssh/config <<'EOF'

Host 192.168.1.*
    HostKeyAlgorithms +ssh-rsa
    PubkeyAcceptedKeyTypes +ssh-rsa
EOF

echo "Ajout de la recherche quotidienne des mises à jour"

(crontab -l 2>/dev/null
 echo "0 3 * * * /home/pi/sc_tools/update/update.sh") | sort -u | crontab -

echo
echo "=================================="
echo " Installation terminée"
echo "=================================="
echo
echo "Actions manuelles restantes :"
echo
echo "1) sudo raspi-config"
echo "   -> hostname = soundcork"
echo
echo "2) ~/sc_tools/tools/change_cfg.sh"
echo "3) ~/sc_tools/tools/change_ip.sh"
echo "4) ~/sc_tools/tools/create_data.sh"
echo "5) ~/sc_tools/tools/control_data.sh"
echo
echo "Si plusieurs comptes Soundcork :"
echo "6) ~/sc_tools/tools/change_accountId.sh"
echo
echo "Puis :"
echo "7) ~/sc_tools/tools/create_data.sh"
echo "8) ~/sc_tools/tools/control_data.sh"
echo
echo "9) mv ~/soundcork/dataX ~/soundcork/data"
echo
echo "10) ~/sc_tools/tools/change_marge.sh"
echo
echo "Redémarrage conseillé."
```
<br>

### `install/install_copilot.sh`

```bash
#!/usr/bin/env bash
# soundcork_install.sh
# Usage: sudo bash soundcork_install.sh
# Run as user pi (script will drop to pi where needed)
set -euo pipefail
IFS=$'\n\t'

### CONFIGURABLES
SCTOOLS_URL="http://phd.dsmynas.net/sc_tools/sc_tools.lasted.7z"
STOCKHOLM_ZIP_URL="http://phd.dsmynas.net/sc_tools/stockholm.zip"
INSTALL_STOCKHOLM_APP=false   # true pour installer soundcork-stockholm-app (ne pas sur Zero 2 W si RAM limitée)
PI_USER="pi"
SMB_PASSWORD="pi"
SSH_HOST_PATTERN="192.168.1.*"
CRON_UPDATE="0 3 * * * /home/pi/sc_tools/update/update.sh"

### FUNCTIONS
info(){ echo -e "\e[1;34m[INFO]\e[0m $*"; }
warn(){ echo -e "\e[1;33m[WARN]\e[0m $*"; }
err(){ echo -e "\e[1;31m[ERROR]\e[0m $*"; exit 1; }

### CHECKS
if [ "$(id -u)" -ne 0 ]; then
  err "Ce script doit être lancé avec sudo. Ex: sudo bash $0"
fi

if [ "$SUDO_USER" = "" ]; then
  err "Lancer depuis un compte utilisateur via sudo (ex: sudo bash $0)."
fi

if [ "$SUDO_USER" != "$PI_USER" ]; then
  warn "Le script suppose l'utilisateur principal '$PI_USER'. Continuer quand même."
fi

### Mise à jour OS
info "Mise à jour du système"
apt update && apt upgrade -y

### Installation sc_tools
info "Téléchargement et installation de sc_tools"
run_as_pi() { su - "$PI_USER" -c "$*"; }

run_as_pi "mkdir -p \$HOME"
run_as_pi "curl -o \$HOME/sc_tools.lasted.7z ${SCTOOLS_URL} || true"
run_as_pi "if [ -f \$HOME/sc_tools.lasted.7z ]; then 7z x \$HOME/sc_tools.lasted.7z -o\$HOME && rm \$HOME/sc_tools.lasted.7z; else echo 'Impossible de télécharger sc_tools'; fi"
run_as_pi "if [ -d \$HOME/sc_tools ]; then find \$HOME/sc_tools/ -type f -exec chmod 666 {} +; find \$HOME/sc_tools/ -type f -name \"*.sh\" -exec chmod 775 {} +; find \$HOME/sc_tools/ -type d -exec chmod 777 {} +; fi"

### Cron pour réveil
info "Création du lien cron pour soundcork_cron si présent"
if [ -f /home/pi/sc_tools/data/soundcork_cron ]; then
  ln -sf /home/pi/sc_tools/data/soundcork_cron /etc/cron.d/soundcork_cron
else
  warn "/home/pi/sc_tools/data/soundcork_cron introuvable, ignorer."
fi

### Installation Docker
info "Installation de Docker"
curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
sh /tmp/get-docker.sh
usermod -aG docker "$PI_USER"
# newgrp docker ne fonctionne pas dans script non interactif; informer l'utilisateur
info "Ajout de $PI_USER au groupe docker. Vous devrez vous reconnecter pour appliquer."

### Installation paquets listés
if run_as_pi "[ -f \$HOME/sc_tools/docs/paquets_a_installer.txt ]"; then
  info "Installation des paquets listés dans sc_tools/docs/paquets_a_installer.txt"
  apt-get install -y $(run_as_pi "cat \$HOME/sc_tools/docs/paquets_a_installer.txt") || warn "Installation de paquets partiellement échouée"
else
  warn "Fichier paquets_a_installer.txt introuvable, passe."
fi
apt-get autoremove --purge -y

### Stop services non nécessaires
info "Désactivation nginx et minidlna si présents"
systemctl stop nginx 2>/dev/null || true
systemctl disable nginx 2>/dev/null || true
systemctl stop minidlna.service 2>/dev/null || true
systemctl disable minidlna.service 2>/dev/null || true

### Alias dans .bashrc
info "Ajout d'alias dans /home/pi/.bashrc"
run_as_pi "grep -qxF \"alias ll='ls -la'\" ~/.bashrc || echo \"alias ll='ls -la'\" >> ~/.bashrc"

### Samba configuration
info "Configuration Samba"
SMB_CONF="/etc/samba/smb.conf"
cat > /tmp/smb.conf.new <<'EOF'
[global]
    deadtime = 15
    disable netbios = Yes
    disable spoolss = Yes
    dns proxy = No
    load printers = No
    logging = file
    map to guest = Bad User
    max log size = 1000
    printcap name = /dev/null
    security = USER
    server min protocol = SMB2
    server role = standalone server
    smb ports = 445
    socket options = TCP_NODELAY IPTOS_LOWDELAY
    idmap config * : backend = tdb
    posix locking = No
    printing = bsd
    strict locking = No
    use sendfile = Yes
    veto files = /.git/node_modules/.cache/

[pi]
    create mask = 0777
    directory mask = 0777
    force user = pi
    guest ok = Yes
    level2 oplocks = No
    oplocks = No
    path = /home/pi
    read only = No
EOF

mv /tmp/smb.conf.new "$SMB_CONF"
chmod 644 "$SMB_CONF"
info "Création de l'utilisateur Samba 'pi' avec mot de passe par défaut"
(echo "$SMB_PASSWORD"; echo "$SMB_PASSWORD") | smbpasswd -s -a "$PI_USER" || warn "smbpasswd a échoué"

### Reboot demandé
info "Redémarrage du Raspberry Pi pour appliquer certains changements"
echo "Le Raspberry va redémarrer maintenant. Après le reboot, relancer ce script avec l'argument --post-reboot pour continuer."
read -p "Appuyer sur Entrée pour redémarrer maintenant ou Ctrl-C pour annuler..." || true
reboot now

# Le script s'arrête ici car le système redémarre. La suite doit être lancée après reboot avec --post-reboot.

```
<br>

### `install/install.sh`

```bash
#!/bin/bash
set -e

echo "========================================================="
echo "        INSTALLATION AUTOMATISÉE DE SOUNDCORK            "
echo "========================================================="

# 1. QUESTION INITIALE (Pour éviter de bloquer plus tard)
read -p "Voulez-vous installer soundcork-stockholm-app ? (o/n) : " install_stockholm
if [[ "$install_stockholm" =~ ^[oO] ]]; then
    RUN_STOCKHOLM=true
    echo "[->] soundcork-stockholm-app sera installée à la fin."
else
    RUN_STOCKHOLM=false
    echo "[->] soundcork-stockholm-app sera ignorée."
fi

read -p "Voulez-vous couper le wifi ? (o/n) : " uninstall_wifi
if [[ "$uninstall_wifi" =~ ^[oO] ]]; then
	if ! grep -q "dtoverlay=disable-wifi" "$CONFIG_FILE"; then
		echo "dtoverlay=disable-wifi" | sudo tee -a "$CONFIG_FILE" > /dev/null
	fi
fi

echo "---------------------------------------------------------"
echo "[+] Mise à jour de l'OS (Apt update & upgrade)..."
sudo apt update && sudo apt upgrade -y

echo "[+] Installation des paquets de base..."
sudo apt-get install -y p7zip-full curl git smbclient

echo "[+] Téléchargement et extraction de sc_tools..."
curl -o ~/sc_tools.lasted.7z http://phd.dsmynas.net/sc_tools/sc_tools.lasted.7z
7z x ~/sc_tools.lasted.7z -o $HOME
rm ~/sc_tools.lasted.7z

echo "[+] Application des droits sur sc_tools..."
find ~/sc_tools/ -type f -exec chmod 666 {} +
find ~/sc_tools/ -type f -name "*.sh" -exec chmod 775 {} +
find ~/sc_tools/ -type d -exec chmod 777 {} +

echo "[+] Création du lien symbolique pour le réveil..."
sudo ln -sf /home/pi/sc_tools/data/soundcork_cron /etc/cron.d/soundcork_cron

echo "[+] Installation de Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

echo "[+] Installation des paquets additionnels..."
sudo apt-get install $(cat ~/sc_tools/docs/paquets_a_installer.txt) -y
sudo apt-get autoremove --purge -y

echo "[+] Arrêt et désactivation des services inutiles (Nginx, MiniDLNA)..."
sudo systemctl stop nginx 2>/dev/null || true
sudo systemctl disable nginx 2>/dev/null || true
sudo systemctl stop minidlna.service 2>/dev/null || true
sudo systemctl disable minidlna.service 2>/dev/null || true

echo "[+] Configuration des alias..."
cp ~/sc_tools/docs/aliases.txt ~/.bash_aliases
source ~/.bashrc

echo "[+] Configuration de Samba..."
sudo cp /etc/samba/smb.conf /etc/samba/smb.conf.bak 2>/dev/null || true
sudo tee /etc/samba/smb.conf > /dev/null << 'EOF'
[global]
deadtime = 15
disable netbios = Yes
disable spoolss = Yes
dns proxy = No
load printers = No
logging = file
map to guest = Bad User
max log size = 1000
printcap name = /dev/null
security = USER
server min protocol = SMB2
server role = standalone server
smb ports = 445
socket options = TCP_NODELAY IPTOS_LOWDELAY
idmap config * : backend = tdb
posix locking = No
printing = bsd
strict locking = No
use sendfile = Yes
veto files = /.git/node_modules/.cache/

[pi]
create mask = 0777
directory mask = 0777
force user = pi
guest ok = Yes
level2 oplocks = No
oplocks = No
path = /home/pi
read only = No
EOF

echo "[+] Ajout de l'utilisateur Samba (mot de passe 'pi')..."
(echo "pi"; echo "pi") | sudo smbpasswd -s -a pi

echo "[+] Clonage des dépôts Git (Soundcork)..."
cd ~
[ -d "soundcork" ] || git clone https://github.com/deborahgu/soundcork.git
[ -d "soundcork-stockholm-app" ] || git clone https://github.com/krahl/soundcork-stockholm-app.git

echo "[+] Copie des fichiers étalons..."
cd ~/sc_tools/docs && find . -type f -name "*.etalon" -exec cp --parents {} ~/ \; && cd ~

echo "[+] Configuration SSH pour les enceintes..."
BASE_RESEAU=$(hostname -I | cut -d' ' -f1 | cut -d. -f1-3)
mkdir -p ~/.ssh
if ! grep -q "host $BASE_RESEAU.\*" ~/.ssh/config 2>/dev/null; then
    echo "host $BASE_RESEAU.*" >> ~/.ssh/config
    echo "HostKeyAlgorithms +ssh-rsa" >> ~/.ssh/config
    echo "PubkeyAcceptedKeyTypes +ssh-rsa" >> ~/.ssh/config
fi

echo "[+] Configuration de la tâche Cron journalière..."
if ! crontab -l 2>/dev/null | grep -q "update.sh"; then
    ( crontab -l 2>/dev/null ; echo "0 3 * * * /home/pi/sc_tools/update/update.sh" ) | crontab -
fi

echo "[+] Planification du changement de nom de machine en 'soundcork'..."
sudo raspi-config nonint do_hostname soundcork

echo "[+] Planification de la désactivation Wi-Fi et Bluetooth..."
CONFIG_FILE="/boot/config.txt"
[ -f "/boot/firmware/config.txt" ] && CONFIG_FILE="/boot/firmware/config.txt"

if ! grep -q "dtoverlay=disable-bt" "$CONFIG_FILE"; then
    echo "dtoverlay=disable-bt" | sudo tee -a "$CONFIG_FILE" > /dev/null
fi
sudo systemctl disable hciuart 2>/dev/null || true

echo "---------------------------------------------------------"
echo "▶ ÉTAPES INTERACTIFS DE CONFIGURATION SOUNDCORK"
echo "---------------------------------------------------------"
bash ~/sc_tools/tools/change_cfg.sh
bash ~/sc_tools/tools/change_ip.sh
bash ~/sc_tools/tools/create_data.sh
bash ~/sc_tools/tools/control_data.sh

echo " "
echo "👉 GESTION DES COMPTES (Si plusieurs comptes sous la forme 7654321)"
echo "Si vous devez modifier le compte propre à chaque enceinte, ouvrez un autre terminal et faites :"
echo "  /home/pi/sc_tools/tools/change_accountId.sh"
echo "  Puis relancez manuellement create_data.sh et control_data.sh"
echo " "
read -p "Appuyez sur ENTRÉE quand la configuration de vos comptes est prête..."

if [ -d ~/soundcork/dataX ]; then
    mv ~/soundcork/dataX ~/soundcork/data
    echo "[+] Dossier dataX renommé en data."
else
    echo "[!] Dossier ~/soundcork/dataX non trouvé (déjà renommé ou absent). Étape ignorée."
fi

echo " "
echo "👉 ENCEINTES ROOTÉES"
echo "Assurez-vous que toutes vos enceintes sont branchées sur le réseau."
echo "Vous devez faire un premier 'ssh root@AdresseIpEnceinte' (et valider 'yes') pour CHACUNE d'elles."
echo " "
read -p "Appuyez sur ENTRÉE une fois que vous avez validé la clé SSH sur toutes vos enceintes..."

echo "[+] Application de change_marge.sh..."
bash ~/sc_tools/tools/change_marge.sh

echo "---------------------------------------------------------"
echo "[+] Lancement des applications Docker..."
echo "---------------------------------------------------------"

# Utilisation de 'sg docker' pour exécuter les commandes avec les privilèges docker sans reboot immédiat
sg docker -c "
    cd ~/soundcork
    docker compose up -d --build
    docker compose stop

    cd ~/sc_tools
    docker compose up -d --build

    cd ~/soundcork
    docker compose start
"

if [ "$RUN_STOCKHOLM" = true ]; then
    echo "[+] Déploiement de soundcork-stockholm-app..."
    sg docker -c "
        cd ~/soundcork && docker compose stop
        cd ~/sc_tools && docker compose stop

        cd ~/soundcork-stockholm-app
        mkdir -p ~/soundcork-stockholm-app/stockholm_zip
        curl -o ~/soundcork-stockholm-app/stockholm_zip/stockholm.zip http://phd.dsmynas.net/sc_tools/stockholm.zip
        docker compose -f docker-compose.yml -f docker-compose.build.yml up --build -d

        cd ~/soundcork && docker compose start
        cd ~/sc_tools && docker compose start
    "
else
    echo "[~] Saut de l'étape soundcork-stockholm-app (choix initial 'non')."
fi

echo "[+] Nettoyage de Docker..."
bash ~/sc_tools/tools/docker_menage.sh

echo "========================================================="
echo " INSTALLATION SANS ERREUR !                              "
echo " Le système va redémarrer dans 10 secondes pour appliquer  "
echo " les configurations réseaux, hostname, wifi et bluetooth. "
echo "========================================================="
sleep 10
sudo reboot -n
```
<br>

### `lireMP3.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

# Usage:
# ./lireMP3.sh SOUNDTOUCH_IP MEDIA_SERVER_IP MP3_PATH [TITLE]
# Exemple:
# ./lireMP3.sh 192.168.1.65 192.168.1.116 /local_podcast/podcast.mp3 'front populaire'

soundtouch_ip="${1:-}"
media_server_ip="${2:-}"
mp3_path="${3:-}"
title="${4:-Podcast}"
port="8000"

if [[ -z "$soundtouch_ip" || -z "$media_server_ip" || -z "$mp3_path" ]]; then
  echo "Usage: $0 SOUNDTOUCH_IP MEDIA_SERVER_IP MP3_PATH [TITLE]"
  exit 1
fi

# Construire l'URL du mp3
mp3_url="http://${media_server_ip}${mp3_path}"

# Construire le JSON compact. ATTENTION: si title ou mp3_url contiennent des guillemets ou caractères spéciaux,
# il faut les échapper correctement. Ce script suppose des valeurs simples.
json_data="{\"name\":\"${title}\",\"imageUrl\":\"\",\"streamUrl\":\"${mp3_url}\"}"

# Encoder en base64 sans saut de ligne
b64=$(printf '%s' "$json_data" | base64 | tr -d '\n')

# Construire l'URL orion (même structure que dans le script Python)
orion_url="http://${media_server_ip}:${port}/core02/svc-bmx-adapter-orion/prod/orion/station?data=${b64}"

# Construire le XML
xml="<ContentItem source=\"LOCAL_INTERNET_RADIO\" type=\"stationurl\" location=\"${orion_url}\"><itemName>${title}</itemName></ContentItem>"
echo $xml

# Envoyer la requête POST au SoundTouch
curl -s -X POST "http://${soundtouch_ip}:8090/select" \
  -H "Content-Type: text/xml" \
  --data "$xml"

# Retourner le code de sortie de curl
exit $?

```
<br>

### `mesure_reboot.sh`

```bash
#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch"
    echo "   Exemple : $0 65"
    exit 1
fi

# Détection automatique du réseau local (ex: 192.168.1)
NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)

IP="${NET}.$1"
PORT_APP="17000"     # Remplacez par le port de votre application

echo "Déclenchement du redémarrage sur $IP..."
START_TIME=$(date +%s)

# Envoi de la commande de reboot
echo "sys reboot" | nc -w 1 "$IP" "$PORT_APP"

echo "Attente de l'arrêt de la machine..."
# On boucle tant que le port répond (la machine n'est pas encore éteinte)
while nc -z -w 1 "$IP" "$PORT_APP" 2>/dev/null; do
    sleep 1
done
echo "Machine hors ligne."

echo "Attente du redémarrage (le port doit de nouveau répondre)..."
# On boucle tant que le port NE répond PAS (la machine est en cours de boot)
while ! nc -z -w 1 "$IP" "$PORT_APP" 2>/dev/null; do
    sleep 1
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "Succès ! La machine et l'application ont mis $DURATION secondes pour redémarrer."

```
<br>

### `presets_check.sh`

```bash
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
```
<br>

### `presets_update.sh`

```bash
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
```
<br>

### `py/apple_logos.py`

```python
import requests
import os
import urllib.parse
import sys

# Vérification des arguments
if len(sys.argv) < 2:
    print("Usage : python radio_logos.py <nom_de_la_radio>")
    sys.exit(1)

radio_name = sys.argv[1]

# Configuration du cache local
LOGOS_DIR = '/home/pi/tmp'
os.makedirs(LOGOS_DIR, exist_ok=True)

def fetch_itunes_radio_logo(radio_name, target_size=600):
    """
    Cherche une station de radio ou sa chaîne officielle sur l'API iTunes
    et télécharge son artwork officiel en haute résolution.
    """
    if not radio_name:
        return None

    # Nom de fichier propre pour le cache
    safe_name = "".join([c for c in radio_name if c.isalnum()]).lower()
    file_name = f"{safe_name}.jpg"
    local_file_path = os.path.join(LOGOS_DIR, file_name)
    frontend_path = f"/img/radios/{file_name}"

    # 1. Gestion du Cache local
    if os.path.exists(local_file_path):
        print(f"[Cache] Logo déjà présent localement : {local_file_path}")
        return frontend_path

    # 2. Requête sur l'API iTunes
    print(f"[API] Recherche de '{radio_name}' sur iTunes...")
    search_query = urllib.parse.quote(radio_name)
    
    # On cherche dans les catégories "podcast" et "radioStation" combinées pour maximiser le résultat
    url = f"https://itunes.apple.com/search?term={search_query}&media=podcast&limit=5&country=fr"

    try:
        response = requests.get(url, timeout=4)
        response.raise_for_status()
        data = response.json()

        if data.get('resultCount', 0) > 0:
            # On cherche le résultat le plus pertinent
            # Idéalement une chaîne qui correspond bien au nom de la radio
            results = data['results']
            
            # On prend le premier résultat de la liste
            best_match = results[0]
            
            # iTunes fournit des clés comme 'artworkUrl100' ou 'artworkUrl600'
            image_url = best_match.get('artworkUrl600') or best_match.get('artworkUrl100')

            if image_url:
                # Astuce iTunes : On peut modifier dynamiquement la taille dans l'URL pour avoir la résolution exacte voulue
                # Exemple : .../100x100bb.jpg devient .../600x600bb.jpg
                image_url = image_url.replace("100x100", f"{target_size}x{target_size}")
                image_url = image_url.replace("600x600", f"{target_size}x{target_size}")

                print(f"[Match] Trouvé : '{best_match.get('collectionName', radio_name)}'")
                print(f"[Téléchargement] Récupération de l'image haute déf : {image_url}")
                
                # 3. Téléchargement de l'image
                img_response = requests.get(image_url, timeout=5)
                img_response.raise_for_status()
                
                with open(local_file_path, 'wb') as handler:
                    handler.write(img_response.content)
                
                print(f"[Succès] Logo sauvegardé dans : {local_file_path}")
                return frontend_path
        else:
            print("[Erreur] Aucun résultat sur l'API iTunes.")

    except requests.exceptions.RequestException as e:
        print(f"[Erreur Réseau] Impossible de joindre l'API : {e}")
    except Exception as e:
        print(f"[Erreur] Problème inattendu : {e}")

    return None

if __name__ == "__main__":
    # On cible une taille de 600x600 pixels (parfait pour le web, pas trop lourd pour le Raspberry)
    chemin_frontend = fetch_itunes_radio_logo(radio_name, target_size=600)
    print("\n--- Résultat Final ---")
    if chemin_frontend:
        print(f"Chemin pour le Frontend : {chemin_frontend}")
    else:
        print("Échec du téléchargement.")
```
<br>

### `py/bose_optimizer.py`

```python
import os
import subprocess
import shutil
from pathlib import Path

# Configuration des chemins
SRC_DIR = Path("/home/pi/sc_tools/Music/mp3")
DEST_DIR = Path("/media/Music/mp3")

# Extensions élargies
AUDIO_EXTS = {'.mp3', '.flac', '.wav', '.m4a', '.wma', '.aac', '.aiff', '.alac', '.ogg', '.ape'}

def process_library():
    if not SRC_DIR.exists():
        print(f"Erreur : Le dossier source {SRC_DIR} n'existe pas.")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print("Démarrage de l'analyse récursive avec os.walk...")

    # os.walk force la descente dans chaque sous-dossier, à n'importe quelle profondeur
    for root, dirs, files in os.walk(SRC_DIR, followlinks=True):
        root_path = Path(root)

        # Affiche le dossier actuellement inspecté (très utile pour voir s'il descend bien dans 'disque1')
        dossier_actuel = root_path.relative_to(SRC_DIR) if root_path != SRC_DIR else 'Racine'
        print(f"\n📂 SCAN DU DOSSIER : {dossier_actuel}")

        for file_name in files:
            item = root_path / file_name
            rel_path = item.relative_to(SRC_DIR)
            dest_file = DEST_DIR / rel_path

            # Création immédiate de l'arborescence côté destination
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # 1. Gestion des pochettes
            if item.name.lower() in ['cover.jpg', 'folder.jpg']:
                if not dest_file.exists():
                    shutil.copy2(item, dest_file)
                    print(f"  🖼️  [COPIE IMAGE] {file_name}")
                continue

            # 2. Gestion audio
            if item.suffix.lower() in AUDIO_EXTS:
                dest_audio = dest_file.with_suffix('.mp3')

                # C'est ici que le script précédent était trop silencieux
                if dest_audio.exists():
                    print(f"  ⏭️  [DÉJÀ PRÉSENT] {file_name} (Sauté)")
                    continue

                print(f"  🎵 [TRANSCODAGE] {file_name}")

                # La commande magique FFmpeg optimisée pour Bose SoundTouch avec suppression du blanc final
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', str(item),
                    '-af', 'silenceremove=stop_periods=1:stop_duration=2.0:stop_threshold=-50dB',
                    '-c:a', 'libmp3lame',
                    '-b:a', '320k',
                    '-ar', '44100',
                    '-ac', '2',
                    '-id3v2_version', '3',
                    '-map_metadata', '0',
                    '-map', '0:a',
                    '-map', '0:v?',
                    '-c:v', 'copy',
                    str(dest_audio)
                ]

                try:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"  ❌ [ERREUR] Impossible de convertir {file_name}")

if __name__ == "__main__":
    process_library()
    print("\n✅ Traitement terminé à 100% !")



```
<br>

### `py/deezer_logos.py`

```python
import requests
import os
import urllib.parse
import sys

# Vérification des arguments
if len(sys.argv) < 2:
    print("Usage : python deezer_logos.py <nom_de_la_radio>")
    sys.exit(1)

# Récupération du paramètre
radio_name = sys.argv[1]

# Définition du chemin de stockage
LOGOS_DIR = '/home/pi/tmp'
# LOGOS_DIR = '/app/www/img/radios' # Dossier physique (quand intégré au projet)

# S'assurer que le dossier existe au démarrage
os.makedirs(LOGOS_DIR, exist_ok=True)

def fetch_deezer_radio_logo(radio_name, size="picture_medium"):
    """
    Cherche le logo d'une radio via les chaînes de Podcasts de Deezer.
    :param size: 'picture_small', 'picture_medium', 'picture_big', 'picture_xl'
    """
    if not radio_name:
        return None

    # Création d'un nom de fichier "propre" (sans espaces ni caractères spéciaux)
    safe_name = "".join([c for c in radio_name if c.isalnum()]).lower()
    file_name = f"{safe_name}.jpg"
    local_file_path = os.path.join(LOGOS_DIR, file_name)
    frontend_path = f"/img/radios/{file_name}"

    # 1. MISE EN CACHE
    if os.path.exists(local_file_path):
        print(f"[Info] Le logo existe déjà en cache : {local_file_path}")
        return frontend_path

    # 2. RECHERCHE SUR L'API DEEZER (Endpoint Podcast !)
    print(f"[Info] Recherche de '{radio_name}' sur l'API Deezer (Podcasts)...")
    search_query = urllib.parse.quote(radio_name)
    
    # C'est ici que résidait le secret : on cherche dans les podcasts
    url = f"https://api.deezer.com/search/podcast?q={search_query}"

    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        data = response.json()

        if data.get('data') and len(data['data']) > 0:
            # On prend le premier résultat
            podcast_data = data['data'][0]
            image_url = podcast_data.get(size)

            if image_url:
                print(f"[Info] Logo trouvé (via {podcast_data.get('title')}) ! Téléchargement depuis {image_url}...")
                
                # 3. TÉLÉCHARGEMENT ET SAUVEGARDE
                img_data = requests.get(image_url, timeout=5).content
                with open(local_file_path, 'wb') as handler:
                    handler.write(img_data)
                
                print(f"[Succès] Logo sauvegardé physiquement dans : {local_file_path}")
                return frontend_path
            else:
                print("[Erreur] La radio a été trouvée, mais Deezer ne fournit pas de logo.")
        else:
            print("[Erreur] Radio introuvable sur Deezer (aucun podcast associé).")

    except requests.exceptions.RequestException as e:
        print(f"[Deezer API] Erreur réseau pour {radio_name}: {e}")
    except Exception as e:
        print(f"[Deezer API] Erreur inattendue pour {radio_name}: {e}")

    return None

# L'exécution du script en ligne de commande
if __name__ == "__main__":
    # N'hésite pas à tester avec "picture_xl" pour une meilleure qualité sur ton interface web !
    chemin_frontend = fetch_deezer_radio_logo(radio_name, size="picture_xl")
    
    print("\n--- Résultat Final ---")
    if chemin_frontend:
        print(f"Chemin à renvoyer au Frontend : {chemin_frontend}")
    else:
        print("Échec de l'opération.")
```
<br>

### `py/discoverST.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from zeroconf import Zeroconf, ServiceBrowser
import requests
import time
import re

print("🔎 Détection SoundTouch via Zeroconf + API...\n")

devices = []

class SoundTouchListener:
    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info and info.addresses:
            ip = ".".join(map(str, info.addresses[0]))
            devices.append(ip)
            print(f"➡️  Appareil détecté via mDNS : {ip}")

    def remove_service(self, zeroconf, type, name):
        pass  # pas nécessaire pour ton usage

    def update_service(self, zeroconf, type, name):
        pass  # requis pour éviter le FutureWarning

# Lancer Zeroconf
zeroconf = Zeroconf()
listener = SoundTouchListener()
browser = ServiceBrowser(zeroconf, "_soundtouch._tcp.local.", listener)

# Attendre la découverte
time.sleep(2)
zeroconf.close()

if not devices:
    print("❌ Aucune SoundTouch trouvée via Zeroconf")
    exit(1)

# Fonction d'extraction XML
def extract(tag, xml):
    m = re.search(f"<{tag}>(.*?)</{tag}>", xml)
    return m.group(1) if m else ""

def extract_attr(attr, xml):
    m = re.search(f'{attr}="([^"]+)"', xml)
    return m.group(1) if m else ""

# Interroger chaque enceinte
for ip in devices:
    print(f"\n🔧 Test API sur {ip}...")

    # Attendre que l’API soit prête
    ready = False
    for _ in range(6):
        try:
            r = requests.get(f"http://{ip}:8090/now_playing", timeout=1)
            if r.status_code == 200:
                ready = True
                break
        except:
            pass
        time.sleep(0.2)

    if not ready:
        print("   ⚠️ API non prête après 6 tentatives")
        continue

    # Appel /info
    try:
        xml = requests.get(f"http://{ip}:8090/info", timeout=2).text
    except:
        print("   ⚠️ Impossible d'obtenir /info")
        continue

    # Extraction
    DEVICEID = extract_attr("deviceID", xml)
    NAME = extract("name", xml)
    TYPE = extract("type", xml)
    COMPTE = extract("margeAccountUUID", xml)

    print(f"   Nom       : {NAME}")
    print(f"   Modèle    : {TYPE}")
    print(f"   DeviceID  : {DEVICEID}")
    print(f"   Compte    : {COMPTE}")

```
<br>

### `py/get_covers.py`

```python
import os
import re
import requests
import musicbrainzngs
from datetime import datetime
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3

# --- CONFIGURATION PRINCIPALE ---
MUSIC_DIR = "/home/pi/sc_tools/Music/mp3"
COVER_NAME = "Cover.jpg"
LOG_FILE = "/home/pi/sc_tools/Music/missing_covers.log"

# --- CONFIGURATION MUSICBRAINZ ---
musicbrainzngs.set_useragent("RaspberryPi_CoverFetcher", "2.1", "ton.email@exemple.com")
# -----------------------------

def clean_for_api(text):
    """Nettoie les parenthèses, crochets et caractères gênants pour les API."""
    if not text:
        return ""
    # 1. Enlever tout ce qui est entre () ou [] (ex: "(Live 73)", "[Deluxe Edition]")
    text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
    # 2. Remplacer les tirets et underscores par des espaces
    text = text.replace('_', ' ').replace('-', ' ')
    # 3. Enlever les apostrophes qui cassent parfois les recherches (ex: Somethin's)
    text = text.replace("'", "").replace("’", "")
    # 4. Supprimer les espaces en double
    return ' '.join(text.split()).strip()

def clean_artist_for_deezer(artist):
    """Ne garde que le premier artiste (Deezer ne trouve rien s'il y a des '&' ou des virgules)."""
    if not artist:
        return ""
    # Coupe la chaîne au premier séparateur trouvé (ignorer la casse pour and/et/feat/vs)
    artist = re.split(r'(?i)\s+&\s+|\s+and\s+|\s+et\s+|,\s*|\s+feat\.?\s+|\s+ft\.?\s+|\s+vs\.?\s+', artist)[0]
    return clean_for_api(artist)

def fetch_fallback_cover_deezer(artist, save_path):
    """Cherche l'artiste sur Deezer et télécharge sa photo (Format moyen/léger)."""
    search_url = "https://api.deezer.com/search/artist"
    params = {'q': artist, 'limit': 1}
    headers = {'User-Agent': 'RaspberryPi_CoverFetcher/2.1'}

    try:
        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('data'):
                img_url = data['data'][0].get('picture_medium')
                if img_url:
                    img_response = requests.get(img_url, headers=headers, timeout=10)
                    if img_response.status_code == 200:
                        with open(save_path, 'wb') as f:
                            f.write(img_response.content)
                        if os.getuid() == 0: 
                            try: os.chown(save_path, 1025, 100)
                            except Exception: pass
                        return True, "Succès (Deezer - Image moyenne)"
                    else:
                        return False, "Erreur lors du téléchargement de l'image Deezer"
                return False, "Artiste trouvé mais aucune photo disponible sur Deezer"
            return False, "Artiste introuvable sur Deezer"
        return False, f"Erreur API Deezer ({response.status_code})"
    except Exception as e:
        return False, f"Erreur Deezer : {e}"

def fetch_cover_art_musicbrainz(artist, album, save_path):
    """Cherche l'album sur MusicBrainz et télécharge la pochette allégée (500px)."""
    try:
        result = musicbrainzngs.search_releases(artist=artist, release=album, limit=1)
        if not result['release-list']:
            return False, "Album introuvable"

        release_id = result['release-list'][0]['id']
        
        caa_url_500 = f"http://coverartarchive.org/release/{release_id}/front-500"
        caa_url_raw = f"http://coverartarchive.org/release/{release_id}/front"

        response = requests.get(caa_url_500, allow_redirects=True, timeout=10)
        
        if response.status_code != 200:
            response = requests.get(caa_url_raw, allow_redirects=True, timeout=10)

        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            if os.getuid() == 0: 
                try: os.chown(save_path, 1025, 100)
                except Exception: pass
            return True, "Succès (MusicBrainz)"
        else:
            return False, f"Pas de pochette sur Cover Art Archive (HTTP {response.status_code})"
    except Exception as e:
        return False, f"Erreur MusicBrainz : {e}"

def get_album_info(folder_path):
    """Extrait l'artiste et l'album via les tags ID3."""
    for file in os.listdir(folder_path):
        if file.lower().endswith('.mp3'):
            try:
                audio = MP3(os.path.join(folder_path, file), ID3=EasyID3)
                artist = audio.get('artist', [''])[0]
                album = audio.get('album', [''])[0]
                if artist and album:
                    return artist, album
            except Exception:
                pass 
    return None, None

def get_info_from_path(folder_path, base_dir):
    """Extrait l'artiste et l'album via le nom des dossiers en prenant les deux DERNIERS dossiers."""
    rel_path = os.path.relpath(folder_path, base_dir)
    parts = rel_path.split(os.sep)
    if len(parts) >= 2:
        # On prend l'avant-dernier (-2) et le dernier (-1) pour gérer les dossiers profonds comme "Compil/Jazz/Artiste/Album"
        return parts[-2], parts[-1]
    return None, None

def main():
    if not os.path.exists(MUSIC_DIR):
        print(f"Erreur : Le dossier {MUSIC_DIR} n'existe pas.")
        return

    print(f"Début du scan dans {MUSIC_DIR}...")
    
    with open(LOG_FILE, 'a', encoding='utf-8') as log_f:
        log_f.write(f"\n{'='*40}\n--- Scan lancé le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n{'='*40}\n")

        for root, dirs, files in os.walk(MUSIC_DIR):
            dirs[:] = [d for d in dirs if d != '@eaDir']

            cover_path = os.path.join(root, COVER_NAME)
            has_mp3 = any(f.lower().endswith('.mp3') for f in files)

            if has_mp3 and not os.path.exists(cover_path):
                print(f"\n--- Dossier : {root}")
                artist, album = get_album_info(root)

                if not artist or not album:
                    artist, album = get_info_from_path(root, MUSIC_DIR)

                if not artist:
                    print("  -> ❌ Impossible d'identifier l'artiste (Dossier ignoré).")
                    continue
                
                print(f"  Dossier/Tag original : Artiste='{artist}' | Album='{album}'")
                
                # --- NETTOYAGE DES CHAÎNES POUR LES API ---
                search_artist_mb = clean_for_api(artist)
                search_album_mb = clean_for_api(album)
                search_artist_dz = clean_artist_for_deezer(artist)
                
                # PLAN A
                print(f"  [Plan A] Recherche pochette MusicBrainz ('{search_album_mb}')...")
                success, reason = fetch_cover_art_musicbrainz(search_artist_mb, search_album_mb, cover_path)
                
                if success:
                    print(f"  -> ✅ Pochette téléchargée avec succès !")
                else:
                    print(f"  -> ⚠️ Échec Plan A ({reason})")
                    
                    # PLAN B (DEEZER)
                    print(f"  [Plan B] Recherche photo de '{search_artist_dz}' sur Deezer...")
                    success_dz, reason_dz = fetch_fallback_cover_deezer(search_artist_dz, cover_path)
                    
                    if success_dz:
                        print(f"  -> ✅ Photo artiste téléchargée et nommée Cover.jpg !")
                    else:
                        print(f"  -> ❌ Échec Plan B ({reason_dz})")
                        log_f.write(f"[SANS POCHETTE] {root} | MB: {reason} | DZ: {reason_dz}\n")

        log_f.write("--- Fin du scan ---\n")
    print(f"\nScan terminé ! Consulte {LOG_FILE} pour les détails.")

if __name__ == "__main__":
    main()
```
<br>

### `py/iTunes_logos.py`

```python
import requests
import os
import urllib.parse
import sys
import re

if len(sys.argv) < 2:
    print("Usage : python radio_logos.py <nom_de_la_radio>")
    sys.exit(1)

radio_name = sys.argv[1]
LOGOS_DIR = '/home/pi/tmp'
os.makedirs(LOGOS_DIR, exist_ok=True)

NAVIGATOR_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def clean_wikimedia_url(url):
    """
    Si l'URL vient de Wikimedia et demande une taille de miniature problématique,
    on la nettoie pour demander une taille standard ou l'image originale.
    """
    if "upload.wikimedia.org" in url and "/thumb/" in url:
        # Option la plus sûre : on descend à une taille standard de 500px souvent acceptée
        url_modifiee = re.sub(r'/\d+px-', '/500px-', url)
        return url_modifiee
    return url

def get_radio_browser_logo(radio_name):
    """ Tente de récupérer le logo sur les serveurs mondiaux de Radio-Browser """
    print(f"[Radio-Browser] Recherche de '{radio_name}'...")
    try:
        search_query = urllib.parse.quote(radio_name)
        url = f"https://de1.api.radio-browser.info/json/stations/byname/{search_query}"
        
        response = requests.get(url, headers=NAVIGATOR_HEADERS, timeout=4)
        if response.status_code == 200:
            data = response.json()
            valid_stations = [s for s in data if s.get('favicon') and s['favicon'].startswith('http')]
            if valid_stations:
                valid_stations.sort(key=lambda x: x.get('clickcount', 0), reverse=True)
                return valid_stations[0]['favicon']
    except Exception as e:
        print(f"[Radio-Browser] Erreur : {e}")
    return None

def get_itunes_clean_logo(radio_name):
    """ Fallback iTunes si Radio-Browser fait chou blanc """
    print(f"[iTunes Fallback] Recherche de '{radio_name}'...")
    try:
        search_query = urllib.parse.quote(radio_name)
        url = f"https://itunes.apple.com/search?term={search_query}&limit=10&country=fr"
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            if results:
                for item in results:
                    collection = item.get('collectionName', '').lower()
                    track = item.get('trackName', '').lower()
                    
                    if radio_name.lower() in collection or radio_name.lower() in track:
                        img_url = item.get('artworkUrl100') or item.get('artworkUrl600')
                        if img_url:
                            return img_url.replace("100x100", "600x600")
                
                return results[0].get('artworkUrl600') or results[0].get('artworkUrl100')
    except Exception as e:
        print(f"[iTunes Fallback] Erreur : {e}")
    return None

def fetch_live_radio_logo(radio_name):
    """ Centralise le téléchargement du logo de la station """
    if not radio_name:
        return None

    safe_name = "".join([c for c in radio_name if c.isalnum()]).lower()
    file_name = f"{safe_name}.jpg"
    local_file_path = os.path.join(LOGOS_DIR, file_name)
    frontend_path = f"/img/radios/{file_name}"

    if os.path.exists(local_file_path):
        print(f"[Cache] Logo déjà présent localement : {local_file_path}")
        return frontend_path

    # Étape 1 : Radio-Browser
    image_url = get_radio_browser_logo(radio_name)

    # Étape 2 : Fallback iTunes
    if not image_url:
        print("[Info] Logo non trouvé sur Radio-Browser, bascule sur iTunes...")
        image_url = get_itunes_clean_logo(radio_name)

    # Étape 3 : Téléchargement final avec nettoyage d'URL
    if image_url:
        # Nettoyage spécifique pour Wikimedia
        image_url = clean_wikimedia_url(image_url)
        
        try:
            print(f"[Téléchargement] Récupération de l'image : {image_url}")
            img_response = requests.get(image_url, headers=NAVIGATOR_HEADERS, timeout=5)
            img_response.raise_for_status()
            
            with open(local_file_path, 'wb') as handler:
                handler.write(img_response.content)
            
            print(f"[Succès] Logo de la station enregistré dans : {local_file_path}")
            return frontend_path
        except Exception as e:
            print(f"[Erreur] Échec du téléchargement physique de l'image : {e}")
    else:
        print(f"[Échec] Impossible de trouver un logo pour '{radio_name}'")

    return None

if __name__ == "__main__":
    chemin_frontend = fetch_live_radio_logo(radio_name)
    print("\n--- Résultat Final ---")
    if chemin_frontend:
        print(f"Chemin pour ton Frontend : {chemin_frontend}")
    else:
        print("Opération avortée.")
```
<br>

### `py/lireMP3.py`

```python
def play_mp3(soundtouch_ip, media_server_ip, mp3_path, title="Podcast"):
    import json
    import base64
    import requests

    mp3_url = f"http://{media_server_ip}{mp3_path}"

    data = {
        "name": title,
        "imageUrl": "",
        "streamUrl": mp3_url
    }

    b64 = base64.b64encode(
        json.dumps(data, separators=(',', ':')).encode()
    ).decode()

    orion_url = (
        f"http://{media_server_ip}:8000"
        f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={b64}"
    )

    def play_mp3(soundtouch_ip, media_server_ip, mp3_path, title="Podcast"):
    import json
    import base64
    import requests

    mp3_url = f"http://{media_server_ip}{mp3_path}"

    data = {
        "name": title,
        "imageUrl": "",
        "streamUrl": mp3_url
    }

    b64 = base64.b64encode(
        json.dumps(data, separators=(',', ':')).encode()
    ).decode()

    orion_url = (
        f"http://{media_server_ip}:8000"
        f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={b64}"
    )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ContentItem source="LOCAL_INTERNET_RADIO"
             type="stationurl"
             location="{orion_url}">
    <itemName>{title}</itemName>
</ContentItem>"""

    return requests.post(
        f"http://{soundtouch_ip}:8090/select",
        data=xml.encode("utf-8"),
        headers={"Content-Type": "text/xml; charset=utf-8"}
    )

    return requests.post(
        f"http://{soundtouch_ip}:8090/select",
        data=xml,
        headers={"Content-Type": "text/xml"}
    )

# Exemple
play_mp3(
    soundtouch_ip="192.168.1.65",
    media_server_ip="192.168.1.116",
    mp3_path="/local_podcast/podcast.mp3",
    title="Mon Podcast"
)
```
<br>

### `py/mp3AllInOne.py`

```python
import os
import subprocess
from pathlib import Path

# Configuration des chemins (à adapter selon vos besoins)
#SRC_DIR = Path("/mnt/d1To/mp3")
#DEST_DIR = Path("/mnt/d1To/mp3clean")
SRC_DIR = Path("/mnt/nas/Music/Autres")
DEST_DIR = Path("/mnt/hdd/N_Autres")

# Extensions gérées
AUDIO_EXTS = {'.mp3', '.flac', '.wav', '.m4a', '.wma', '.aac', '.aiff', '.alac', '.ogg', '.ape'}

def process_library():
    if not SRC_DIR.exists():
        print(f"Erreur : Le dossier source {SRC_DIR} n'existe pas.")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print("Démarrage du traitement complet (réparation, ffmpeg, normalisation) sans les dossiers @eaDir...")

    # Analyse récursive des dossiers[cite: 1]
    for root, dirs, files in os.walk(SRC_DIR, followlinks=True):
        
        # ---------------------------------------------------------
        # EXCLUSION DES DOSSIERS SYNONLOGY (@eaDir)
        # ---------------------------------------------------------
        # Retirer '@eaDir' de la liste empêche os.walk de descendre dedans
        if '@eaDir' in dirs:
            dirs.remove('@eaDir')
            
        root_path = Path(root)
        dossier_actuel = root_path.relative_to(SRC_DIR) if root_path != SRC_DIR else 'Racine'
        
        print(f"\n📂 SCAN DU DOSSIER : {dossier_actuel}")

        for file_name in files:
            item = root_path / file_name
            rel_path = item.relative_to(SRC_DIR)
            dest_file = DEST_DIR / rel_path
            
            # Le fichier de destination sera toujours un .mp3[cite: 1]
            dest_audio = dest_file.with_suffix('.mp3')

            if item.suffix.lower() not in AUDIO_EXTS:
                continue

            if dest_audio.exists():
                print(f"  ⏭️  [DÉJÀ PRÉSENT] {file_name} (Sauté)")
                continue

            # Création immédiate de l'arborescence côté destination[cite: 1]
            dest_audio.parent.mkdir(parents=True, exist_ok=True)

            print(f"  ⚙️  [TRAITEMENT] {file_name}")

            # ---------------------------------------------------------
            # 1. RÉPARATION avec mp3val (uniquement sur les .mp3)
            # ---------------------------------------------------------
            if item.suffix.lower() == '.mp3':
                try:
                    # mp3val répare le fichier et crée un .bak[cite: 2]
                    subprocess.run(['mp3val', '-f', str(item)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    
                    # Nettoyage immédiat du fichier de sauvegarde .bak[cite: 2]
                    bak_file = item.with_suffix('.mp3.bak')
                    if bak_file.exists():
                        bak_file.unlink()
                except Exception:
                    print(f"      ⚠️ Échec mp3val sur {file_name}")

            # ---------------------------------------------------------
            # 2. TRANSCODAGE FFmpeg (Suppression silence + pochette)
            # ---------------------------------------------------------
            cmd = [
                'ffmpeg',
                '-y',
                '-i', str(item),
                '-af', 'silenceremove=stop_periods=1:stop_duration=2.0:stop_threshold=-50dB',
                '-c:a', 'libmp3lame',
                '-b:a', '320k',
                '-ar', '44100',
                '-ac', '2',
                '-id3v2_version', '3',
                '-map_metadata', '0',
                '-map', '0:a',  # Ne mappe que le flux audio[cite: 1]
                '-vn',          # INTERDIT LA VIDÉO/POCHETTE
                str(dest_audio)
            ]

            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
                
                # ---------------------------------------------------------
                # 3. NORMALISATION DU VOLUME avec mp3gain
                # ---------------------------------------------------------
                # mp3gain s'applique sur le fichier MP3 final pour éviter la saturation[cite: 2]
                subprocess.run(['mp3gain', '-r', '-k', str(dest_audio)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                
                print(f"  ✅  [SUCCÈS] {file_name}")
                
            except subprocess.CalledProcessError:
                print(f"  ❌  [ERREUR] Impossible de traiter {file_name}")

if __name__ == "__main__":
    process_library()
    print("\n✅ Traitement terminé à 100% !")

```
<br>

### `py/root_speaker.py`

```python
import socket
import time
import logging
from typing import List, Dict, Optional, Tuple

# Constantes d'injection et de pare-feu
REMOTE_SERVICES_INJECTION = ";touch /tmp/remote_services;/etc/init.d/sshd start"
FW_SCRIPT = "/etc/init.d/Firewalls/update_iptables"
BLOCK_17000_MARKER = "# Block 17000 (added by AfterTouch)"

class DefaultTelnetURLs:
    """Structure factice pour remplacer l'appel manquant defaultTelnetURLs du Go"""
    def __init__(self, service_url: str):
        self.bmx_registry = f"{service_url}/bmx"
        self.stats = f"{service_url}/stats"
        self.sw_update = f"{service_url}/update"

class Manager:
    def __init__(self, telnet_client=None, ssh_client=None):
        # En Python, on injecterait probablement des instances ou des fabriques 
        # (factories) pour gérer les connexions Telnet et SSH.
        self.telnet_client = telnet_client
        self.ssh_client = ssh_client

    def enable_ssh_via_telnet(self, device_ip: str, service_url: str) -> str:
        """
        Amorce le SSH sur une enceinte via son shell sur le port 17000.
        """
        marge_injected = service_url + REMOTE_SERVICES_INJECTION
        sw_update = service_url + "/update"
        return self.set_bose_urls_via_telnet(device_ip, marge_injected, sw_update)

    def reset_bose_urls(self, device_ip: str, service_url: str) -> str:
        """
        Restaure des boseurls propres après l'activation de SSH.
        """
        return self.set_bose_urls_via_telnet(device_ip, service_url, service_url + "/update")

    def enable_ssh_via_telnet_full_config(self, device_ip: str, service_url: str) -> str:
        """
        Variante pour les appareils où l'injection simple est acceptée mais où sshd ne démarre pas.
        """
        u = DefaultTelnetURLs(service_url)
        marge_injected = service_url + REMOTE_SERVICES_INJECTION

        cmds = [
            f'sys configuration bmxRegistryUrl "{u.bmx_registry}"',
            f'sys configuration statsServerUrl "{u.stats}"',
            f'sys configuration margeServerUrl "{marge_injected}"',
            f'sys configuration swUpdateUrl "{u.sw_update}"',
            f'envswitch boseurls set "{marge_injected}" "{u.sw_update}"',
        ]

        return self._run_telnet_injection(device_ip, [service_url, u.sw_update], cmds)

    def _run_telnet_injection(self, device_ip: str, forbid_quote: List[str], cmds: List[str]) -> str:
        """
        Ouvre le shell 17000 et exécute une liste ordonnée de commandes.
        """
        if not self.telnet_client:
            raise ValueError("telnet not configured: Manager.telnet_client is None")

        for v in forbid_quote:
            if '"' in v:
                raise ValueError("boseurls values must not contain a double quote")

        logs = []

        try:
            # Implémentation théorique du client Telnet
            self.telnet_client.dial(device_ip, 17000)
            
            banner = self.telnet_client.probe()
            if banner:
                logs.append(f'Telnet banner: "{banner.strip()}"')

            for cmd in cmds:
                resp = self.telnet_client.send_command(cmd)
                logs.append(f"→ {cmd}\n{resp.rstrip()}")

                if self._is_command_not_found(resp):
                    raise RuntimeError(f'device rejected "{cmd}" (firmware does not expose this command)')

            try:
                verify = self.telnet_client.send_command("getpdo CurrentSystemConfiguration")
                logs.append(f"→ getpdo CurrentSystemConfiguration\n{verify.rstrip()}")
            except Exception:
                pass # Erreur tolérée selon la philosophie "forgiving" du code Go

        except Exception as e:
            raise RuntimeError(f"Telnet injection failed on {device_ip}: {e}") from e
        finally:
            self.telnet_client.close()

        return "\n".join(logs) + "\n"

    def set_bose_urls_via_telnet(self, device_ip: str, marge: str, sw_update: str) -> str:
        """
        Exécute la commande `envswitch boseurls set` via Telnet.
        """
        if not self.telnet_client:
            raise ValueError("telnet not configured: Manager.telnet_client is None")

        if '"' in marge or '"' in sw_update:
            raise ValueError("boseurls values must not contain a double quote")

        logs = []

        try:
            self.telnet_client.dial(device_ip, 17000)
            
            banner = self.telnet_client.probe()
            if banner:
                logs.append(f'Telnet banner: "{banner.strip()}"')

            cmd = f'envswitch boseurls set "{marge}" "{sw_update}"'
            resp = self.telnet_client.send_command(cmd)
            
            logs.append(f"→ {cmd}\n{resp.rstrip()}")

            if self._is_command_not_found(resp):
                raise RuntimeError(f'device rejected "{cmd}" (firmware does not expose envswitch)')

        except Exception as e:
            raise RuntimeError(f"Telnet dial or command failed on {device_ip}: {e}") from e
        finally:
            self.telnet_client.close()

        return "\n".join(logs) + "\n"

    def close_17000(self, device_ip: str) -> str:
        """
        Bloque l'accès LAN au shell de diagnostic port-17000 via SSH.
        """
        if not self.ssh_client:
            raise ValueError("ssh not configured: Manager.ssh_client is None")

        persist = (
            f"grep -q '{BLOCK_17000_MARKER}' {FW_SCRIPT} 2>/dev/null || cat >> {FW_SCRIPT} <<'AFTEREOF'\n\n"
            f"{BLOCK_17000_MARKER}\n"
            "iptables -I INPUT -p tcp --dport 17000 -j DROP\n"
            "iptables -I INPUT -p tcp --dport 17000 -i lo -j ACCEPT\n"
            "AFTEREOF"
        )

        steps = [
            {"desc": "remount / read-write", "cmd": "mount / -o rw,remount"},
            {"desc": "persist firewall rule", "cmd": persist},
            {"desc": "apply firewall rule now", "cmd": "iptables -I INPUT -p tcp --dport 17000 -j DROP; iptables -I INPUT -p tcp --dport 17000 -i lo -j ACCEPT"},
        ]

        return self._run_ssh_steps(device_ip, steps)

    def install_authorized_key(self, device_ip: str, public_key: str) -> str:
        """
        Installe une clé publique SSH pour l'utilisateur root.
        """
        if not self.ssh_client:
            raise ValueError("ssh not configured: Manager.ssh_client is None")

        key = public_key.strip()
        if not key:
            raise ValueError("public key is empty")

        logs = []
        try:
            # Création du dossier .ssh
            out = self.ssh_client.run(device_ip, "mount / -o rw,remount && mkdir -p -m 700 /home/root/.ssh")
            logs.append(f"→ prepare /home/root/.ssh\n{out.strip()}")

            # Upload de la clé (Nécessitera une méthode SFTP/SCP dans votre client SSH)
            self.ssh_client.upload_content(device_ip, f"{key}\n".encode('utf-8'), "/home/root/.ssh/authorized_keys")

            # Changement des droits
            out = self.ssh_client.run(device_ip, "chmod 600 /home/root/.ssh/authorized_keys")
            logs.append(f"→ chmod authorized_keys\n{out.strip()}")

            logs.append("Installed authorized_keys for root.")
        except Exception as e:
            raise RuntimeError(f"Failed to install authorized key: {e}") from e

        return "\n".join(logs) + "\n"

    def _run_ssh_steps(self, device_ip: str, steps: List[Dict[str, str]]) -> str:
        """
        Exécute une liste ordonnée de commandes shell via SSH.
        """
        logs = []
        for step in steps:
            try:
                out = self.ssh_client.run(device_ip, step["cmd"])
                logs.append(f"→ {step['desc']}\n{out.strip()}")
            except Exception as e:
                raise RuntimeError(f"{step['desc']}: {e}") from e

        return "\n".join(logs) + "\n"

    @staticmethod
    def _is_command_not_found(resp: str) -> bool:
        """Vérifie si la réponse indique que la commande est introuvable."""
        # À adapter selon le comportement exact du shell Bose
        return "not found" in resp.lower() or "unknown command" in resp.lower()


def wait_for_ssh_port(device_ip: str, timeout_seconds: int) -> None:
    """
    Sonde le port TCP 22 sur l'enceinte jusqu'à acceptation ou timeout.
    """
    deadline = time.time() + timeout_seconds

    while True:
        try:
            # Tente de se connecter avec un timeout court
            conn = socket.create_connection((device_ip, 22), timeout=3)
            conn.close()
            return  # Connexion réussie
        except (socket.timeout, ConnectionRefusedError, OSError):
            if time.time() > deadline:
                raise TimeoutError(f"ssh (:22) on {device_ip} not reachable within {timeout_seconds}s")
            
            time.sleep(3)
```
<br>

### `py/update_radio_logo.py`

```python
import requests
import os
import urllib.parse
import json
import re

# ==========================================
# CONFIGURATION DE PRODUCTION
# ==========================================
LOGOS_CACHE_FILE = '/home/pi/sc_tools/data/radio_logos_cache.json' 
LOGOS_DIR = '/home/pi/sc_tools/www/img/radios' 

# User-Agent pour passer les sécurités des serveurs d'images
NAVIGATOR_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ==========================================
# FONCTIONS DE RECHERCHE (Par ordre de qualité)
# ==========================================

def get_itunes_clean_logo(radio_name):
    """ Priorité 1 : API iTunes (Haute résolution 600x600) """
    try:
        search_query = urllib.parse.quote(radio_name)
        url = f"https://itunes.apple.com/search?term={search_query}&limit=5&country=fr"
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            if results:
                # Cherche une correspondance exacte d'abord
                for item in results:
                    collection = item.get('collectionName', '').lower()
                    track = item.get('trackName', '').lower()
                    if radio_name.lower() in collection or radio_name.lower() in track:
                        img_url = item.get('artworkUrl100') or item.get('artworkUrl600')
                        if img_url:
                            return img_url.replace("100x100", "600x600")
                # Sinon prend le premier résultat
                return results[0].get('artworkUrl600') or results[0].get('artworkUrl100')
    except Exception:
        pass
    return None

def get_wikipedia_logo(radio_name):
    """ Priorité 2 : API Wikipédia (Logos officiels détourés) """
    try:
        # 1. Chercher la page Wikipedia de la radio
        search_query = urllib.parse.quote(radio_name + " radio")
        search_url = f"https://fr.wikipedia.org/w/api.php?action=query&list=search&srsearch={search_query}&utf8=&format=json&srlimit=1"
        r = requests.get(search_url, headers=NAVIGATOR_HEADERS, timeout=4)
        
        if r.status_code == 200 and r.json().get('query', {}).get('search'):
            title = r.json()['query']['search'][0]['title']
            
            # 2. Récupérer l'image principale de cette page (Taille 500px)
            img_url = f"https://fr.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(title)}&prop=pageimages&format=json&pithumbsize=500"
            r_img = requests.get(img_url, headers=NAVIGATOR_HEADERS, timeout=4)
            pages = r_img.json().get('query', {}).get('pages', {})
            
            for page_id, page_data in pages.items():
                if 'thumbnail' in page_data:
                    return page_data['thumbnail']['source']
    except Exception:
        pass
    return None

def get_radio_browser_logo(radio_name):
    """ Priorité 3 (Dernier recours) : Radio-Browser """
    try:
        search_query = urllib.parse.quote(radio_name)
        url = f"https://de1.api.radio-browser.info/json/stations/byname/{search_query}"
        response = requests.get(url, headers=NAVIGATOR_HEADERS, timeout=4)
        if response.status_code == 200:
            data = response.json()
            valid_stations = [s for s in data if s.get('favicon') and s['favicon'].startswith('http') and "default" not in s['favicon']]
            if valid_stations:
                valid_stations.sort(key=lambda x: x.get('clickcount', 0), reverse=True)
                return valid_stations[0]['favicon']
    except Exception:
        pass
    return None

def download_logo(radio_name, image_url):
    """ Télécharge l'image physiquement et retourne le chemin relatif pour le JSON """
    safe_name = "".join([c for c in radio_name if c.isalnum()]).lower()
    file_name = f"{safe_name}.jpg"
    local_file_path = os.path.join(LOGOS_DIR, file_name)
    json_target_address = f"/www/img/radios/{file_name}"

    try:
        img_response = requests.get(image_url, headers=NAVIGATOR_HEADERS, timeout=5)
        img_response.raise_for_status()
        
        with open(local_file_path, 'wb') as handler:
            handler.write(img_response.content)
        
        return json_target_address
    except Exception as e:
        print(f"  -> [Erreur Téléchargement] {e}")
        return None

# ==========================================
# MOTEUR PRINCIPAL (TRAITEMENT DU JSON)
# ==========================================
def process_cache_updates():
    if not os.path.exists(LOGOS_CACHE_FILE):
        print(f"[Erreur] Fichier JSON introuvable : {LOGOS_CACHE_FILE}")
        return

    os.makedirs(LOGOS_DIR, exist_ok=True)

    with open(LOGOS_CACHE_FILE, 'r', encoding='utf-8') as f:
        cache_data = json.load(f)

    print(f"📡 Analyse du cache : {len(cache_data)} stations trouvées...")
    has_changes = False

    for station_name, target_address in cache_data.items():
        if target_address == "FA_ICON" or target_address == "":
            print(f"\n🔍 Recherche requise pour : '{station_name}'")
            
            # CASCADE DE RECHERCHE : iTunes -> Wikipedia -> Radio-Browser
            img_url = get_itunes_clean_logo(station_name)
            
            if not img_url:
                print("  -> iTunes échoué, tentative Wikipédia...")
                img_url = get_wikipedia_logo(station_name)
                
            if not img_url:
                print("  -> Wikipédia échoué, tentative Radio-Browser...")
                img_url = get_radio_browser_logo(station_name)

            if img_url:
                new_target_address = download_logo(station_name, img_url)
                if new_target_address:
                    print(f"  ✅ Succès : {new_target_address}")
                    cache_data[station_name] = new_target_address
                    has_changes = True
            else:
                print(f"  ❌ Aucun logo trouvé. Conservé en l'état.")

    if has_changes:
        print("\n💾 Mise à jour du fichier JSON en cours...")
        with open(LOGOS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        print("🎉 Fichier mis à jour avec succès !")
    else:
        print("\n✨ Terminé. Le cache est déjà à jour, aucune action nécessaire.")

if __name__ == "__main__":
    process_cache_updates()
```
<br>

### `py/ws_bose.py`

```python
import websocket
import threading
import time
import sys

# --- GESTION DES ARGUMENTS VIA LIGNE DE COMMANDE ---
ip_suffix = "100"
debug_mode = False

# Argument 1 : Suffixe IP
if len(sys.argv) > 1:
    ip_suffix = sys.argv[1]

# Argument 2 : Mode Debug
if len(sys.argv) > 2:
    if sys.argv[2].lower() == "debug":
        debug_mode = True

# Reconstitution de l'adresse IP complète
SPEAKER_IP = f"192.168.1.{ip_suffix}"

def on_message(ws, message):
    print(f"\n--- [NOUVEAU MESSAGE XML DE L'ENCEINTE] {ip_suffix} ---")
    print(message)

def on_error(ws, error):
    print(f"\n[ERREUR] : {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"\n[CONNEXION FERMÉE {ip_suffix}] L'enceinte a coupé le flux.")

def on_open(ws):
    print(f"\n[SUCCÈS] Connecté au WebSocket de l'enceinte {SPEAKER_IP} !")
    print("En attente des événements en temps réel (change le volume ou de piste sur l'enceinte pour tester)...")

    # On peut aussi lui envoyer des ordres dans ce tunnel !
    # (Exemple : simuler un appui sur le bouton PLAY/PAUSE)
    # ws.send('<key state="press" sender="Gabbo">PLAY_PAUSE</key>')
    # ws.send('<key state="release" sender="Gabbo">PLAY_PAUSE</key>')

def start_listening(enable_debug):
    # Activation du debug réseau selon l'argument 2
    websocket.enableTrace(enable_debug) 
    ws_url = f"ws://{SPEAKER_IP}:8080/"
    
    # Clé secrète Bose (gabbo)
    custom_headers = ["Sec-WebSocket-Protocol: gabbo"]
    
    ws = websocket.WebSocketApp(
        ws_url,
        header=custom_headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # Lancement du client
    ws.run_forever()

if __name__ == "__main__":
    mode_text = " (Mode DEBUG activé)" if debug_mode else ""
    print(f"Tentative de connexion à {SPEAKER_IP}{mode_text}...")
    start_listening(debug_mode)
```
<br>

### `radio_browser.sh`

```bash
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

```
<br>

### `reboot_raspberry.sh`

```bash
#!/bin/bash

# Couleurs pour le terminal web
VERT='\033[0;32m'
ROUGE='\033[0;31m'
NEUTRE='\033[0m'

echo -e "${ROUGE}⚠️  ATTENTION : Vous êtes sur le point de redémarrer le Raspberry Pi principal.${NEUTRE}"
read -p "Confirmez-vous le redémarrage complet ? (o/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Oo]$ ]]; then
    echo -e "➡️  Opération annulée."
    sleep 4
    exit 1
fi

echo -e "${VERT}🔄 Ordre de redémarrage envoyé à l'hôte...${NEUTRE}"
echo -e "La page web va planter d'ici quelques secondes, c'est normal !"
echo -e "Revenez dans environ 2 minutes."

# L'astuce magique : On demande au conteneur de créer un mini-conteneur temporaire 
# qui va "sortir de sa bulle" (nsenter) pour exécuter 'systemctl reboot' directement sur le Raspberry !
docker run --rm --privileged --pid=host python:3.12-slim nsenter -t 1 -m systemctl reboot

exit 0
```
<br>

### `rebootST.sh`

```bash
#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch | All>"
    echo "   Exemple : $0 65"
    exit 1
fi

# Détection automatique du réseau local (ex: 192.168.1)
NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)

if [[ "${1,,}" == "all" ]]; then
	echo "🔎 Détection SoundTouch via Zeroconf + API..."
	echo

	# Vérifier si avahi-browse est installé
	if ! command -v avahi-browse >/dev/null 2>&1; then
		echo "❌ avahi-browse n'est pas installé."
		echo "   Installe-le avec : sudo apt install avahi-utils"
		exit 1
	fi

	avahi-browse -rt _soundtouch._tcp 2>/dev/null | while read -r line; do

		# Détection d'une ligne contenant l'adresse
		if echo "$line" | grep -q "address ="; then
			
			# Extraction robuste de l'IP sans sed
			IP=$(echo "$line" | cut -d'[' -f2 | cut -d']' -f1)

			echo "➡️  Appareil détecté via mDNS : $IP"

				echo "sys reboot" | nc -w 1 $IP 17000
				echo " → Reboot envoyé à $IP"

		fi

	done
	# echo "Scan du réseau : $NET.0/24"

	# for i in $(seq 1 254); do
		# IP="$NET.$i"

		# Test si un SoundTouch répond sur le port 8090
		# if curl -s --connect-timeout 0.3 http://$IP:8090/name >/dev/null; then
			# echo "SoundTouch détecté : $IP"

			# echo "sys reboot" | nc -w 1 $IP 17000
			# echo " → Reboot envoyé à $IP"

		# fi
	# done
else
	IP="${NET}.$1"
		if curl -s --connect-timeout 0.3 http://$IP:8090/name >/dev/null; then
			echo "SoundTouch détecté : $IP"

			echo "sys reboot" | nc -w 1 $IP 17000
			echo " → Reboot envoyé à $IP"
		else
			echo " → SoundTouch non détectée : $IP"
		fi
fi


# echo "Redémarrage de la machine locale…"
# sudo reboot -n

```
<br>

### `rebuild_minidlna.sh`

```bash
#!/usr/bin/env bash

echo "=========================================="
echo "🔄 Début de la reconstruction du cache DLNA"
echo "=========================================="

# 1. Arrêt du conteneur cible via le socket Docker
echo "⏳ Arrêt de local_dlna..."
docker stop local_dlna

# 2. Suppression du cache physique sur l'hôte via un conteneur éphémère
echo "🗑️ Suppression du cache physique (/home/pi/sc_tools/dlna_cache/cache/)..."
docker run --rm -v /home/pi/sc_tools/dlna_cache:/cache alpine rm -rf /cache/cache/

# 3. Redémarrage du conteneur cible
echo "🚀 Redémarrage de local_dlna..."
docker start local_dlna

echo "=========================================="
echo "✅ Opération terminée avec succès."
echo "=========================================="
```
<br>

### `removeCovers.sh`

```bash
#!/bin/bash
#Suppression de toutes les pochettes contenues dans les  mp3 de ce dossiers et sous dossiers
# Vérification des dépendances
if ! command -v eyeD3 &> /dev/null; then
    echo "Erreur : eyeD3 n'est pas installé. (sudo apt install eyed3)"
    exit 1
fi

if ! command -v metaflac &> /dev/null; then
    echo "Erreur : metaflac n'est pas installé. (sudo apt install flac)"
    exit 1
fi

echo "Démarrage du nettoyage récursif dans : $(pwd)"

# Trouver et purger les fichiers MP3
echo "Recherche et traitement des fichiers MP3 en cours..."
find . -type f -iname "*.mp3" -exec eyeD3 --remove-all-images {} + > /dev/null 2>&1

# Trouver et purger les fichiers FLAC
echo "Recherche et traitement des fichiers FLAC en cours..."
find . -type f -iname "*.flac" -exec metaflac --remove-art {} + > /dev/null 2>&1

echo "Opération terminée ! Toutes les pochettes ont été supprimées avec succès."

```
<br>

### `reset_bt.sh`

```bash
#!/bin/bash
# Fichier : reset_bt.sh
# Description : Force la réinitialisation complète de la pile Bluetooth sur Raspberry Pi

echo "[INFO] Vérification des blocages radio (rfkill)..."
sudo rfkill unblock bluetooth
sudo rfkill unblock wlan

echo "[INFO] Arrêt des services Bluetooth..."
sudo systemctl stop bluetooth
sudo systemctl stop hciuart

# Légère pause pour libérer le port série
sleep 2

echo "[INFO] Redémarrage de l'attachement UART (hciuart)..."
sudo systemctl start hciuart
if systemctl status hciuart | grep -q "failed"; then
    echo "[ERREUR] Le service hciuart a échoué. Problème de communication série."
else
    echo "[OK] hciuart démarré."
fi

echo "[INFO] Redémarrage du démon BlueZ..."
sudo systemctl start bluetooth

echo "[INFO] État de l'interface Bluetooth :"
hciconfig -a

echo "=================================================="
echo "[INFO] Derniers logs Kernel (dmesg) pour la puce Bluetooth :"
dmesg | grep -i -E 'blue|bcm43|hci' | tail -n 5
echo "=================================================="

echo "[INFO] Réinitialisation terminée. Tu peux relancer bluetoothctl."
```
<br>

### `resetStateST.sh`

```bash
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
```
<br>

### `rootST.sh`

```bash
#!/usr/bin/env bash

## Donne accès à root via ssh afin de récupérer le fichier Sources.xml, optionnellement le laisser permanent -p

# Sécurité : arrête le script en cas d'erreur (-e), de variable non définie (-u) ou d'erreur dans un pipe (-o pipefail)
set -euo pipefail

# Définition des variables
if (( $# < 1 || $# > 2 )); then
    echo "Syntaxe : $0 <SuffIP_SoundTouch> [-p]"
	echo "   -p : root permanent"
    exit 1
fi

[[ $1 =~ ^[0-9]{1,3}$ ]] || {
    echo "Erreur : suffixe IP invalide."
    exit 1
}

(( $1 >= 1 && $1 <= 254 )) || {
    echo "Erreur : suffixe IP hors plage (1-254)."
    exit 1
}

# Détection automatique du réseau local (ex: 192.168.1)
NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)

IP="${NET}.$1"
permanent=${2:-non}
PORT_APP=17000
PORT_SSH=22
ENV_FILE="/home/pi/sc_tools/.env"
SSH_OPTS="-o ConnectTimeout=5 \
          -o BatchMode=yes \
          -o StrictHostKeyChecking=accept-new"
		  
if nc -z -w 2 "$IP" "$PORT_SSH" > /dev/null 2>&1; then
    echo "Inutile $IP déjà rootée"
		if [[ "$permanent" == "-p" ]]; then
			echo "Root rendu permanent"
			ssh_key
			ssh $SSH_OPTS root@"$IP" touch /mnt/nv/remote_services
		fi
		echo ""
		echo "Configuration Marge :"
		echo $(curl -s http://$IP:8090/info | grep -oP '(?<=<margeURL>).*?(?=</margeURL>)')
		
    exit 0
fi

if [ -f "$ENV_FILE" ]; then
    # Exporte automatiquement les variables chargées
    set -a
    source "$ENV_FILE"
    set +a

    # Affichage des valeurs pour vérifier
    echo "Adresse Marge : $SC_MARGE_ADDR"
    echo "Port Marge    : $SC_MARGE_PORT"
    echo "Compte        : $SC_MARGE_ACCOUNT"
    echo "Base de val.  : $SC_SOUNDCORK_DB"
else
    echo "Erreur : Le fichier $ENV_FILE est introuvable."
    exit 1
fi

margeURL="http://$SC_MARGE_ADDR:$SC_MARGE_PORT/marge"
SOURCES=$SC_SOUNDCORK_DB/$SC_MARGE_ACCOUNT/Sources.xml
mkdir -p "$(dirname "$SOURCES")"

# Variables pour l'animation
spinner() {
    local duration=$1
    local spin='|/-\'

    for ((i=0;i<duration*5;i++)); do
        printf "\r%s" "${spin:$((i%4)):1}"
        sleep 0.2
    done

    printf "\r \r"
}

ssh_key() {
	ssh-keygen -F "$IP" >/dev/null || \
		ssh-keyscan -H "$IP" >> ~/.ssh/known_hosts
}

send_cmd() {
    printf '%s\n' "$1" | nc -w 2 "$IP" "$PORT_APP"
}

# --- Vérifications préalables ---

# Vérifier si la commande 'nc' (netcat) est installée
if ! command -v nc >/dev/null 2>&1; then
    echo "Erreur : 'nc' (netcat) n'est pas installé sur ce système." >&2
    exit 1
fi

echo "Configuration : ST=$IP | Marge=$SC_MARGE_ADDR | Port=$SC_MARGE_PORT"

# --- Exécution du script ---
send_cmd 'envswitch boseurls set "https://server;touch /tmp/remote_services;/etc/init.d/sshd start"  "https://server/update"'

echo "[INFO] Commande envoyée..."
echo ""

# Animation d'attente (la barre qui tourne 10 sec)
spinner 10

if ! nc -z -w 2 "$IP" "$PORT_SSH" > /dev/null 2>&1; then
    echo "[INFO] Le port SSH est injoignable. Déclenchement du redémarrage..."
	send_cmd "sys reboot"

	echo "[INFO] Attente du redémarrage (le port doit de nouveau répondre)..."

	echo ""
	timeout=120
	start=$(date +%s)

	while ! nc -z -w1 "$IP" "$PORT_APP" 2>/dev/null; do
		spinner 1

		(( $(date +%s) - start > timeout )) && {
			echo "[ERREUR] Timeout de redémarrage."
			exit 1
		}
	done

	echo "[INFO] L'enceinte a redémarrée..."
	
    # Animation d'attente (la barre qui tourne 30 sec)
	spinner 30
	
	if ! nc -z -w 1 "$IP" "$PORT_SSH" 2>/dev/null; then
		echo "[ERREUR] L'enceinte n'a pas pu être rootée"
		send_cmd "envswitch boseurls set http://$SC_MARGE_ADDR:$SC_MARGE_PORT/marge http://$SC_MARGE_ADDR:$SC_MARGE_PORT/updates/soundtouch"
		exit 1
	fi

else
    echo "[INFO] Le port SSH est joignable, aucun redémarrage nécessaire."
fi

ssh_key
ssh $SSH_OPTS root@"$IP" cat /mnt/nv/BoseApp-Persistence/1/Sources.xml > "$SOURCES"

spinner 20

# send_cmd "sys configuration margeServerUrl http://$SC_MARGE_ADDR:$SC_MARGE_PORT/marge"
# send_cmd "sys configuration swUpdateUrl http://$SC_MARGE_ADDR:$SC_MARGE_PORT/updates/soundtouch"
send_cmd "envswitch boseurls set $margeURL http://$SC_MARGE_ADDR:$SC_MARGE_PORT/updates/soundtouch"

echo "[INFO] fichier téléchargé $SOURCES"

if [[ "$permanent" == "-p" ]]; then
    ssh $SSH_OPTS root@"$IP" touch /mnt/nv/remote_services
fi

echo ""
echo "Root terminé avec succès "
echo ""

newMargeURL=$(curl -s http://$IP:8090/info | grep -oP '(?<=<margeURL>).*?(?=</margeURL>)')
if [[ "$newMargeURL" == "$margeURL" ]]; then
	echo "✅ La configuation margeURL est correcte, opérations terminée avec succés"
else
	echo "⚠️ Attention la configuration margeURL n'est pas bonne "
	echo "	- Valeur actuelle ❌ : $newMargeURL"
	echo "  - Il faut         ❎ : $margeURL" 	
fi

```
<br>

### `sauve.sh`

```bash
#!/bin/bash
# Fichier : /home/pi/sc_tools/tools/sauve.sh

# Définition stricte du PATH pour cron
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo "⏳ Démarrage de la sauvegarde..."
DEST_DIR="$HOME/.sauve"
ARCHIVE_NAME="sauve$(date +%Y%m%d-%H%M).7z"
LATEST_FILE="sc_tools.latest.7z"

# 1. Création du dossier si inexistant
mkdir -p "$DEST_DIR"

# 2. Nettoyage et préparation
rm -f "$DEST_DIR/$LATEST_FILE"
apt-mark showmanual > "$HOME/sc_tools/docs/paquets_a_installer.txt"

# 3. Sauvegarde sc_tools
cd "$HOME/sc_tools" || { echo "❌ Erreur : Impossible d'accéder à $HOME/sc_tools"; exit 1; }
7z a -t7z -mx=9 "$DEST_DIR/$ARCHIVE_NAME" $(find . -maxdepth 1 -type f) app/ www/ data/ docs/ tools/ update/ '-xr!*.7z' '-xr!*.zip' '-xr!*.mp3' '-xr!core.*' '-xr!__pycache__/'

# 4. Sauvegarde sc_music
cd "$HOME" || { echo "❌ Erreur : Impossible d'accéder à $HOME"; exit 1; }
7z a -t7z -mx=9 "$DEST_DIR/$ARCHIVE_NAME" $(find . -maxdepth 1 -type f) sc_music/ '-xr!*.jpg' '-xr!*.7z' '-xr!*.zip' '-xr!*.mp3' '-xr!*.db' '-xr!core.*' '-xr!__pycache__/'

# 5. Copie et envoi
cp "$DEST_DIR/$ARCHIVE_NAME" "$DEST_DIR/$LATEST_FILE"

echo "📡 Envoi vers le NAS..."
smbclient //192.168.1.150/web -A "$HOME/.smbcredentials" -c "lcd $DEST_DIR ; cd sc_tools ; put $LATEST_FILE"
smbclient //192.168.1.150/web -A "$HOME/.smbcredentials" -c "lcd $HOME/sc_tools/docs ; cd sc_tools ; put SoundcorkSetup.html index.html"

echo "✅ Sauvegarde terminée avec succès !"
```
<br>

### `scanLan.sh`

```bash
#!/usr/bin/env bash

set -euo pipefail

BASE_RESEAU=$(hostname -I | cut -d' ' -f1 | cut -d. -f1-3)
input="$BASE_RESEAU"

# Extraire la base (ex: 192.168.1)
if [[ "$input" =~ ^([0-9]+\.[0-9]+\.[0-9]+)\.0/24$ ]]; then
  base="${BASH_REMATCH[1]}"
elif [[ "$input" =~ ^([0-9]+\.[0-9]+\.[0-9]+)\.0$ ]]; then
  base="${BASH_REMATCH[1]}"
elif [[ "$input" =~ ^([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  base="${BASH_REMATCH[1]}"
else
  echo "Format d'adresse non reconnu. Exemple valide: 192.168.1.0/24 ou 192.168.1" >&2
  exit 2
fi

# Correction : On utilise une chaîne de caractères plutôt qu'un tableau (array)
# Bash ne peut pas exporter un tableau vers les processus enfants (xargs)
PORTS_LIST="22 80 443 8090"

# Timeout en SECONDES (1 seconde est largement suffisant pour un LAN)
ping_timeout=1
port_timeout=1

# Fonction pour obtenir le nom d'hôte PTR
get_hostname() {
  local ip="$1"
  if command -v getent >/dev/null 2>&1; then
    local ge
    ge=$(getent hosts "$ip" 2>/dev/null || true)
    if [ -n "$ge" ]; then
      echo "$ge" | awk '{print $2; exit}'
      return
    fi
  fi

  if command -v host >/dev/null 2>&1; then
    local h
    h=$(host "$ip" 2>/dev/null || true)
    if [[ "$h" =~ pointer[[:space:]]([a-zA-Z0-9._-]+)\.? ]]; then
      echo "${BASH_REMATCH[1]}"
      return
    fi
  fi

  if command -v nslookup >/dev/null 2>&1; then
    local n
    n=$(nslookup "$ip" 2>/dev/null || true)
    if [[ "$n" =~ name[[:space:]]*=[[:space:]]*([a-zA-Z0-9._-]+)\.? ]]; then
      echo "${BASH_REMATCH[1]}"
      return
    fi
  fi

  echo "-"
}

# Test de port via /dev/tcp avec timeout
test_port() {
  local ip="$1"; local port="$2"
  
  # Correction : Ajout de ':' (commande vide) pour garantir la redirection TCP
  # Note: Assurez-vous que la commande GNU 'timeout' est bien installée sur votre système
  if timeout "${port_timeout}" bash -c ": >/dev/tcp/${ip}/${port}" >/dev/null 2>&1; then
    echo "open"
  else
    echo "closed"
  fi
}

# Fonction qui scanne une IP
scan_one() {
  local i="$1"
  local ip="${base}.${i}"

  # Ping rapide pour filtrer hôtes inactifs
  if ping -c 1 -W "${ping_timeout}" "$ip" >/dev/null 2>&1; then
    local hostn
    hostn=$(get_hostname "$ip")
    local open_ports=()
    
    # On itère sur la variable chaîne exportée, qui va se scinder sur les espaces
    for p in $PORTS_LIST; do
      if [ "$(test_port "$ip" "$p")" = "open" ]; then
        open_ports+=("$p")
      fi
    done
    
    # Formatage des ports
    local ports_str="-"
    if [ ${#open_ports[@]} -gt 0 ]; then
      ports_str=$(IFS=,; echo "${open_ports[*]}")
    fi
    printf "%3s\t%-15s\t%-30s\t%s\n" "$i" "$ip" "$hostn" "$ports_str"
  fi
}

# En-tête
printf "%3s\t%-15s\t%-30s\t%s\n" "sfx" "adresse" "hostname" "ports_open"
printf "%3s\t%-15s\t%-30s\t%s\n" "---" "---------------" "------------------------------" "---------"

# Exportation des fonctions et des variables simples pour le sous-shell
export -f get_hostname test_port scan_one
export base PORTS_LIST ping_timeout port_timeout

# Lancer les scans en parallèle
seq 1 254 | xargs -P50 -I{} bash -c 'scan_one "$@"' _ {}

exit 0
```
<br>

### `send_key.sh`

```bash
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
```
<br>

### `setup_audio_daemon.sh`

```bash
#!/bin/bash
# Fichier : setup_audio_daemon.sh
# Description : Configure et force le démarrage du serveur audio en mode headless (sans IHM) pour le Raspberry Pi.
# Exécution : Lancer en tant qu'utilisateur standard (NON ROOT), sans sudo.

if [ "$EUID" -eq 0 ]; then
  echo "[ERREUR] Ne lance pas ce script avec sudo ou en root. Utilise ton utilisateur standard (ex: pi ou ton user de dev)."
  exit 1
fi

USER_UID=$(id -u)
export XDG_RUNTIME_DIR="/run/user/$USER_UID"

echo "[INFO] Activation du mode 'Linger' pour l'utilisateur $USER..."
# Le mode linger permet aux services de l'utilisateur de démarrer au boot 
# et de rester actifs même après la déconnexion SSH.
sudo loginctl enable-linger "$USER"

echo "[INFO] Détection et configuration du serveur audio..."

if command -v pipewire >/dev/null; then
    echo "[INFO] Système basé sur PipeWire détecté."
    # Démarrage et activation au boot des services PipeWire
    systemctl --user enable pipewire pipewire-pulse
    systemctl --user start pipewire pipewire-pulse
elif command -v pulseaudio >/dev/null; then
    echo "[INFO] Système basé sur PulseAudio détecté."
    # Démarrage et activation au boot de PulseAudio
    systemctl --user enable pulseaudio
    systemctl --user start pulseaudio
else
    echo "[ERREUR] Ni PulseAudio ni PipeWire ne sont installés sur le système."
    exit 1
fi

echo "[INFO] Redémarrage de la pile Bluetooth au niveau système..."
sudo systemctl restart bluetooth

echo "[INFO] Attente de l'initialisation des sockets audio..."
sleep 3

echo "=================================================="
echo "[INFO] Test de la connexion au serveur audio :"
if pactl list short sinks > /dev/null 2>&1; then
    echo "[SUCCÈS] Le serveur audio répond."
    pactl list short sinks
else
    echo "[ERREUR] Toujours impossible de joindre le serveur. Vérifie les logs via : journalctl --user -xe"
fi
echo "=================================================="

echo "[NOTE] Pour tes scripts futurs (ex: dans cron ou systemd système), n'oublie pas d'ajouter :"
echo 'export XDG_RUNTIME_DIR="/run/user/'$USER_UID'"'
```
<br>

### `sources_update.sh`

```bash
#!/usr/bin/env bash

# Rechargement du fichier Sources.xml après redémarrage

if [ $# -lt 1 ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch | All>"
    echo "   Exemple : $0 65"
    exit 1
fi

PORT=8090

# Détection automatique du réseau local (ex: 192.168.1)
NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)

if [[ "${1,,}" == "all" ]]; then
	echo "🔎 Détection SoundTouch via Zeroconf + API..."
	echo

	# Vérifier si avahi-browse est installé
	if ! command -v avahi-browse >/dev/null 2>&1; then
		echo "❌ avahi-browse n'est pas installé."
		echo "   Installe-le avec : sudo apt install avahi-utils"
		exit 1
	fi

	avahi-browse -rt _soundtouch._tcp 2>/dev/null | while read -r line; do

		# Détection d'une ligne contenant l'adresse
		if echo "$line" | grep -q "address ="; then
			
			# Extraction robuste de l'IP sans sed
			IP=$(echo "$line" | cut -d'[' -f2 | cut -d']' -f1)

			echo "➡️  Appareil détecté via mDNS : $IP"

			# 2. Récupération dynamique du deviceID
			# On télécharge le XML et on utilise sed pour isoler la valeur dans deviceID="..."
			DEVICE_ID=$(curl -sS "http://$IP:$PORT/info" | sed -n 's/.*<info deviceID="\([^"]*\)".*/\1/p')

			# Vérification de la réussite de l'extraction
			if [ -z "$DEVICE_ID" ]; then
			  echo "Erreur : Impossible de récupérer le deviceID."
			  echo "Vérifiez l'adresse IP ou l'état de l'enceinte."
			  exit 1
			fi

			echo "Device ID récupéré : $DEVICE_ID"
			echo "Envoi de la notification..."

			# 3. Envoi de la requête POST avec le deviceID inséré dynamiquement
			curl -sS -X POST "http://$IP:$PORT/notification" \
			  -H 'Content-Type: application/xml' \
			  -d "<updates deviceID=\"$DEVICE_ID\"><sourcesUpdated/></updates>"
			sleep 2
			echo "sys reboot" | nc -w 1 $IP 17000
			echo " → Reboot envoyé à $IP"

		fi

	done
else
	IP="${NET}.$1"
	# 2. Récupération dynamique du deviceID
	# On télécharge le XML et on utilise sed pour isoler la valeur dans deviceID="..."
	DEVICE_ID=$(curl -sS "http://$IP:$PORT/info" | sed -n 's/.*<info deviceID="\([^"]*\)".*/\1/p')

	# Vérification de la réussite de l'extraction
	if [ -z "$DEVICE_ID" ]; then
	  echo "Erreur : Impossible de récupérer le deviceID."
	  echo "Vérifiez l'adresse IP ou l'état de l'enceinte."
	  exit 1
	fi

	echo "Device ID récupéré : $DEVICE_ID"
	echo "Envoi de la notification..."

	# 3. Envoi de la requête POST avec le deviceID inséré dynamiquement
	curl -sS -X POST "http://$IP:$PORT/notification" \
	  -H 'Content-Type: application/xml' \
	  -d "<updates deviceID=\"$DEVICE_ID\"><sourcesUpdated/></updates>"
	sleep 2
	echo "sys reboot" | nc -w 1 $IP 17000
	echo " → Reboot envoyé à $IP"
fi

```
<br>

### `ST10stereo.sh`

```bash
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

```
<br>

### `swapRpiZero2.sh`

```bash
#!/bin/bash

# Vérification des droits administrateur (root)
if [ "$EUID" -ne 0 ]; then
  echo "❌ Veuillez exécuter ce script avec sudo (ex: sudo bash setup_zram.sh)"
  exit 1
fi

echo "🚀 Début de l'optimisation de la mémoire (ZRAM) pour Pi Zero 2 W..."
echo "------------------------------------------------------------------"

echo "📦 Étape 1 : Désactivation du swap classique (protection de la carte SD)"
# Désactivation de dphys-swapfile si présent (OS Raspberry Pi)
if command -v dphys-swapfile &> /dev/null; then
    dphys-swapfile swapoff
    dphys-swapfile uninstall
    systemctl disable dphys-swapfile
    apt-get purge -y dphys-swapfile
fi

# Désactivation immédiate de tout swap actif
swapoff -a

# Suppression des entrées de swap dans /etc/fstab (Debian classique)
sed -i '/swap/d' /etc/fstab
echo "✔️ Swap classique désactivé."

echo "📦 Étape 2 : Installation de zram-tools"
apt-get update
apt-get install -y zram-tools
echo "✔️ Installation terminée."

echo "⚙️ Étape 3 : Configuration de ZRAM"
# Sauvegarde de la configuration d'origine
if [ -f /etc/default/zramswap ]; then
    cp /etc/default/zramswap /etc/default/zramswap.bak
fi

# Écriture de la nouvelle configuration optimisée
cat <<EOF > /etc/default/zramswap
# --- Optimisation ZRAM pour Raspberry Pi Zero 2 W ---
# Algorithme de compression performant
ALGO=zstd
# Utiliser 50% de la RAM (environ 256 Mo sur 512 Mo)
PERCENT=50
# Priorité haute
PRIORITY=100
EOF
echo "✔️ Configuration appliquée."

echo "🔄 Étape 4 : Redémarrage des services"
systemctl restart zramswap
echo "✔️ Service redémarré."

echo "------------------------------------------------------------------"
echo "✅ TERMINÉ ! Voici l'état actuel de votre mémoire :"
echo ""

# Affichage des résultats
echo "📊 Utilisation Globale (free -h) :"
free -h
echo ""
echo "🗜️ Détails ZRAM (zramctl) :"
zramctl
```
<br>

### `wifi_discover.sh`

```bash
#!/bin/bash

echo "Recherche des réseaux Wi-Fi (SSID) à proximité..."
echo "------------------------------------------------"

# Détection de macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Chemin vers l'utilitaire airport sur macOS
    AIRPORT_CMD="/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
    
    if [ -f "$AIRPORT_CMD" ]; then
        # Exécute le scan, ignore la première ligne (en-tête), et extrait la première colonne (SSID)
        "$AIRPORT_CMD" -s | awk '{print $1}' | tail -n +2 | sort -u
    else
        echo "Erreur : L'utilitaire airport est introuvable sur ce Mac."
    fi

# Détection de Linux (utilisation de NetworkManager - recommandé et ne nécessite pas sudo)
elif command -v nmcli &> /dev/null; then
    # -t : format tabulaire (facile à parser)
    # -f SSID : ne récupérer que la colonne SSID
    # grep -v "^$" : supprime les lignes vides (SSID masqués)
    nmcli -t -f SSID dev wifi | sort -u | grep -v "^$"

# Détection de Linux (utilisation de iwlist - ancienne méthode, nécessite souvent sudo)
elif command -v iwlist &> /dev/null; then
    # Recherche de l'interface Wi-Fi disponible (ex: wlan0)
    WIFI_IFACE=$(iw dev | awk '$1=="Interface"{print $2}' | head -n 1)
    
    if [ -n "$WIFI_IFACE" ]; then
        echo "(Cette méthode peut nécessiter les droits administrateur / sudo)"
        sudo iwlist "$WIFI_IFACE" scan | grep "ESSID" | cut -d'"' -f2 | sort -u | grep -v "^$"
    else
        echo "Erreur : Aucune interface Wi-Fi trouvée via 'iw'."
    fi

else
    echo "Erreur : Impossible de trouver un outil compatible pour scanner le Wi-Fi."
    echo "Sur Linux, installez 'network-manager' (nmcli) ou 'wireless-tools' (iwlist)."
fi

echo "------------------------------------------------"
echo "Scan terminé."
```
<br>

### `wifi_setup.sh`

```bash
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
```
<br>


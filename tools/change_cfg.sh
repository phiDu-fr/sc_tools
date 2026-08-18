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

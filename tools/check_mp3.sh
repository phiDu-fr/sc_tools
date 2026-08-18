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

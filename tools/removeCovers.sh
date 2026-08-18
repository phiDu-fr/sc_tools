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

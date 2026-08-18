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
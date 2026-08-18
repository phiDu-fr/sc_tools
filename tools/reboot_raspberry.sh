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
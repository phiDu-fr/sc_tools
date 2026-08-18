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

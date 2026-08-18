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
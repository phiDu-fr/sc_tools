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
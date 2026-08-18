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



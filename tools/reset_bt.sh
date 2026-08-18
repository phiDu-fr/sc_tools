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
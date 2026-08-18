#!/bin/bash

echo "Recherche des réseaux Wi-Fi (SSID) à proximité..."
echo "------------------------------------------------"

# Détection de macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Chemin vers l'utilitaire airport sur macOS
    AIRPORT_CMD="/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
    
    if [ -f "$AIRPORT_CMD" ]; then
        # Exécute le scan, ignore la première ligne (en-tête), et extrait la première colonne (SSID)
        "$AIRPORT_CMD" -s | awk '{print $1}' | tail -n +2 | sort -u
    else
        echo "Erreur : L'utilitaire airport est introuvable sur ce Mac."
    fi

# Détection de Linux (utilisation de NetworkManager - recommandé et ne nécessite pas sudo)
elif command -v nmcli &> /dev/null; then
    # -t : format tabulaire (facile à parser)
    # -f SSID : ne récupérer que la colonne SSID
    # grep -v "^$" : supprime les lignes vides (SSID masqués)
    nmcli -t -f SSID dev wifi | sort -u | grep -v "^$"

# Détection de Linux (utilisation de iwlist - ancienne méthode, nécessite souvent sudo)
elif command -v iwlist &> /dev/null; then
    # Recherche de l'interface Wi-Fi disponible (ex: wlan0)
    WIFI_IFACE=$(iw dev | awk '$1=="Interface"{print $2}' | head -n 1)
    
    if [ -n "$WIFI_IFACE" ]; then
        echo "(Cette méthode peut nécessiter les droits administrateur / sudo)"
        sudo iwlist "$WIFI_IFACE" scan | grep "ESSID" | cut -d'"' -f2 | sort -u | grep -v "^$"
    else
        echo "Erreur : Aucune interface Wi-Fi trouvée via 'iw'."
    fi

else
    echo "Erreur : Impossible de trouver un outil compatible pour scanner le Wi-Fi."
    echo "Sur Linux, installez 'network-manager' (nmcli) ou 'wireless-tools' (iwlist)."
fi

echo "------------------------------------------------"
echo "Scan terminé."
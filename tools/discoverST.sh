#!/bin/bash

# ==========================================
# PARAMÉTRAGES
# ==========================================
SUBNET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)
STATIC_IPS=""

# Création d'un fichier temporaire pour stocker les IPs trouvées (gère le compteur et évite les doublons)
TMP_FILE=$(mktemp)
trap "rm -f $TMP_FILE" EXIT

# ==========================================
# FONCTION COMMUNE : EXTRACTION ET AFFICHAGE
# ==========================================
extract_and_print() {
    local IP=$1
    local XML=$2

    if [ -n "$XML" ]; then
        local NAME=$(echo "$XML" | grep -oPm1 "(?<=<name>)[^<]+")
        
        if [ -n "$NAME" ]; then
            # --- GESTION DES DOUBLONS ---
            # Si l'IP est déjà dans le fichier temporaire, on ignore (utile pour le mode -b)
            if grep -q "^${IP}$" "$TMP_FILE" 2>/dev/null; then
                return
            fi
            
            # On enregistre l'IP dans le fichier temporaire
            echo "$IP" >> "$TMP_FILE"

            # --- EXTRACTION ---
            local TYPE=$(echo "$XML" | grep -oPm1 "(?<=<type>)[^<]+")
            local DEVICEID=$(echo "$XML" | grep -oP 'deviceID="\K[^"]+')
            local COMPTE=$(echo "$XML" | grep -oPm1 "(?<=<margeAccountUUID>)[^<]+")
            local MARGE=$(echo "$XML" | grep -oPm1 "(?<=<margeURL>)[^<]+")
            
            [ -z "$COMPTE" ] && COMPTE="Non renseigné"

            # Un seul bloc 'echo -e' pour éviter l'entrelacement
            echo -e "➡️  IP       : $IP\n   Nom      : $NAME\n   Modèle   : $TYPE\n   DeviceID : $DEVICEID\n   Compte   : $COMPTE\n   Marge    : $MARGE\n-----------------------------------"
        fi
    fi
}

# ==========================================
# MÉTHODE 1 : SCAN BRUTE FORCE
# ==========================================
scan_brute_force() {
    echo "🔎 Scan brute force du réseau ${SUBNET}.1 à 254..."
    echo "⏳ Patientez environ 2 secondes..."
    echo "-----------------------------------"

    check_device_brute() {
        local IP=$1
        local XML=$(curl -s --connect-timeout 1 --max-time 1.5 "http://$IP:8090/info")
        extract_and_print "$IP" "$XML"
    }

    for i in {1..254}; do
        check_device_brute "${SUBNET}.${i}" &
    done

    wait
}

# ==========================================
# MÉTHODE 2 : ZEROCONF / mDNS + STATIQUE
# ==========================================
scan_mdns() {
    echo "🔎 Détection SoundTouch (Hybride : Zeroconf + IPs statiques)..."
    echo "-----------------------------------"

    if command -v avahi-browse >/dev/null 2>&1; then
        MDNS_IPS=$(avahi-browse -rtp _soundtouch._tcp 2>/dev/null | grep "^=" | grep ";IPv4;" | cut -d';' -f8)
    else
        echo "⚠️ avahi-browse non installé. On utilise uniquement les IPs statiques."
        MDNS_IPS=""
    fi

    ALL_IPS=$(echo -e "${MDNS_IPS}\n${STATIC_IPS}" | sort -u | grep -v '^$')

    for IP in $ALL_IPS; do
        # On vérifie ici aussi pour ne pas faire de curl inutile si on vient du mode -b
        if grep -q "^${IP}$" "$TMP_FILE" 2>/dev/null; then
            continue
        fi

        # --- Attente et récupération de /info en une seule étape ---
        local XML=""
        for i in {1..4}; do
            XML=$(curl -s --connect-timeout 2 --max-time 3 "http://$IP:8090/info")
            if [ -n "$XML" ]; then
                break # Le XML a été récupéré, on sort de la boucle
            fi
            sleep 0.5
        done

        if [ -z "$XML" ]; then
            echo -e "➡️  IP       : $IP\n   ⚠️ API indisponible (pas de réponse sur /info)\n-----------------------------------"
            continue
        fi

        extract_and_print "$IP" "$XML"
    done
}

# ==========================================
# POINT D'ENTRÉE DU SCRIPT (GESTION DES PARAMÈTRES)
# ==========================================
echo "DEBUG : L'argument reçu est : '$1'"
case "$1" in
    "-f")
        scan_brute_force
        ;;
    "-b")
        scan_mdns
        echo ""
        scan_brute_force
        ;;
    "-m"|*)
        scan_mdns
        ;;
esac

# ==========================================
# COMPTEUR FINAL
# ==========================================
TOTAL_FOUND=$(wc -l < "$TMP_FILE")

echo "✅ Scan terminé ! $TOTAL_FOUND appareil(s) SoundTouch trouvé(s)."
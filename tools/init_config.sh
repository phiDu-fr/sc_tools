#!/bin/bash
# Script d'initialisation de la configuration SoundCork / sc_tools

echo "=== Clonage des dépôts ==="
cd $HOME
rm -rf soundcork
rm -rf sc_tools
rm -rf sc_music
rm -rf sc_virtual

git clone https://github.com/deborahgu/soundcork.git
git clone https://github.com/phiDu-fr/sc_tools.git
git clone https://github.com/phiDu-fr/sc_music.git
git clone https://github.com/phiDu-fr/sc_virtual.git

echo "=== Démarrage de l'initialisation ==="

# 1. Récupération de l'IPV4 de la machine (<ValeurIP>)
# On utilise la route par défaut pour isoler l'interface réseau active de façon fiable
ValeurIP=$(ip route get 1.1.1.1 | awk -F"src " 'NR==1{split($2,a," ");print a[1]}')

if [ -z "$ValeurIP" ]; then
    echo "[Erreur] Impossible de déterminer l'IPV4 locale."
    exit 1
fi
echo "[OK] IPV4 de la machine (ValeurIP) : $ValeurIP"

# 2. Remplacements dans docker-compose.yml de Soundcork
DC_FILE="/home/pi/soundcork/docker-compose.yml"

if [ -f "$DC_FILE" ]; then
    echo "[En cours] Modification de $DC_FILE..."
    # Utilisation du délimiteur '|' avec sed pour éviter les conflits avec les '/' des chemins
    sed -i "s|- base_url=http://soundcork:8001|- base_url=http://${ValeurIP}:8000|g" "$DC_FILE"
    sed -i "s|- data_dir=/soundcork/data|- data_dir=/home/pi/soundcork/data|g" "$DC_FILE"
    sed -i "s|- SOUNDCORK_LOG_DIR=/soundcork/logs/traffic|- SOUNDCORK_LOG_DIR=/home/pi/soundcork/logs/traffic|g" "$DC_FILE"
    sed -i "s|- \./data:/soundcork/data|- ./data:/home/pi/soundcork/data|g" "$DC_FILE"
    sed -i "s|- \./logs:/soundcork/logs|- ./logs:/home/pi/soundcork/logs|g" "$DC_FILE"
    echo "[OK] Fichier $DC_FILE mis à jour."
else
    echo "[Erreur] Fichier $DC_FILE introuvable."
fi

# 3. Renommer .env.private en .env
ENV_PRIVATE="/home/pi/sc_tools/.env.private"
ENV_FILE="/home/pi/sc_tools/.env"

if [ -f "$ENV_PRIVATE" ]; then
    mv "$ENV_PRIVATE" "$ENV_FILE"
    echo "[OK] Fichier renommé en $ENV_FILE"
else
    echo "[Info] Le fichier $ENV_PRIVATE n'existe pas. Continuité avec $ENV_FILE s'il existe."
fi

# 4. Force brute réseau pour l'enceinte (port 8090)
echo "[En cours] Balayage réseau force brute (port 8090)..."
SUBNET=$(echo "$ValeurIP" | cut -d. -f1-3)
TMP_DIR=$(mktemp -d)

# Lancement des 254 requêtes en parallèle (timeout ultra court de 1s)
for i in {1..254}; do
    (
        TEST_IP="${SUBNET}.${i}"
        # Execution silencieuse, on filtre directement la réponse XML
        RESP=$(curl -s --connect-timeout 1 -m 1 "http://${TEST_IP}:8090/info" 2>/dev/null)

        if echo "$RESP" | grep -q "<margeAccountUUID>"; then
            echo "$TEST_IP" > "${TMP_DIR}/found_ip"
            echo "$RESP" > "${TMP_DIR}/found_xml"
        fi
    ) &
done

# On attend que tous les jobs parallèles soient terminés
wait

# 5. Traitement de la réponse et extraction de l'UUID
val_margeAccountUUID=""

if [ -f "${TMP_DIR}/found_xml" ]; then
    FOUND_IP=$(cat "${TMP_DIR}/found_ip")
    XML_DATA=$(cat "${TMP_DIR}/found_xml")

    # Extraction propre via regex/sed
    val_margeAccountUUID=$(echo "$XML_DATA" | sed -n 's/.*<margeAccountUUID>\(.*\)<\/margeAccountUUID>.*/\1/p')

    echo "[OK] Enceinte SoundTouch trouvée sur : $FOUND_IP"
    echo "[OK] margeAccountUUID extrait : $val_margeAccountUUID"
else
    echo "[Erreur] Aucune enceinte ne répond sur $SUBNET.1 à $SUBNET.254."
    echo "         Vérifier que les enceintes soient toutes branchées sur le secteur, raccordées au réseau Wifi ou filaire."
    echo "         Puis relancer $0."
fi

# Nettoyage
rm -rf "$TMP_DIR"

# 6. Remplacements dans sc_tools/.env
if [ -f "$ENV_FILE" ]; then
    echo "[En cours] Modification de $ENV_FILE..."

    # Remplacement de l'IP selon tes spécifications (ValeurIP = IP de la machine)
    sed -i "s|SC_MARGE_ADDR=192.168.1.116|SC_MARGE_ADDR=${ValeurIP}|g" "$ENV_FILE"

    if [ -n "$val_margeAccountUUID" ]; then
        sed -i "s|SC_MARGE_ACCOUNT=1234567|SC_MARGE_ACCOUNT=${val_margeAccountUUID}|g" "$ENV_FILE"
        echo "[OK] Fichier $ENV_FILE mis à jour avec succès."
    else
        echo "[Info] SC_MARGE_ACCOUNT ignoré (enceinte non détectée)."
    fi
else
    echo "[Erreur] Fichier $ENV_FILE introuvable pour la configuration finale."
fi

echo "=== Initialisation terminée ==="


#!/usr/bin/env bash

# Créé l'arborescence propre à Soundtouch en scannant tout le réseau local
# et télécharge les fichiers XML associés à chaque enceinte, conforme à Soundcork

BASE_DIR="/home/pi/soundcork/dataX"
TIMEOUT=1

if [ -d "$BASE_DIR" ]; then
    rm -rf "$BASE_DIR"
fi

# ---------- 1. Détection automatique du réseau ----------
LOCAL_IP=$(hostname -I | awk '{print $1}')
[[ -z "$LOCAL_IP" ]] && exit 1

IP_RACINE=$(echo "$LOCAL_IP" | cut -d. -f1-3)
BASE_RESEAU="${IP_RACINE}."

mkdir -p "$BASE_DIR"

# Options SSH pour forcer la connexion aux vieux serveurs Bose et éviter les blocages en sous-shell
SSH_OPTS="-o HostKeyAlgorithms=+ssh-rsa,ssh-dss -o PubkeyAcceptedKeyTypes=+ssh-rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o LogLevel=ERROR -o ConnectTimeout=2"

# ---------- 2. Fonction de traitement ----------
process_device() {

    local suffixe=$1
    local ip="${BASE_RESEAU}${suffixe}"
    local temp_xml="${BASE_DIR}/DeviceInfo_${suffixe}.xml"

    # ---------- Téléchargement du XML ----------
    if curl -sSf \
        --connect-timeout "$TIMEOUT" \
        --max-time 3 \
        "http://${ip}:8090/info" \
        -o "$temp_xml" 2>/dev/null; then

        # ---------- Extraction XML ----------
        local nom
        local compte
        local dev_id
        local ip_xml

        nom=$(xmlstarlet sel -t -v "//name" "$temp_xml" 2>/dev/null | tr -d '\r')
        compte=$(xmlstarlet sel -t -v "//margeAccountUUID" "$temp_xml" 2>/dev/null | tr -d '\r')
        dev_id=$(xmlstarlet sel -t -v "//info/@deviceID" "$temp_xml" 2>/dev/null | tr -d '\r')
        ip_xml=$(xmlstarlet sel -t -v "(//ipAddress)[1]" "$temp_xml" 2>/dev/null | tr -d '\r')

        : "${compte:=inconnu}"
        : "${nom:=enceinte_${suffixe}}"
        : "${ip_xml:=$ip}" # Valeur de secours si le XML est vide

        # ---------- Vérification ----------
        if [[ -n "$dev_id" ]]; then

            echo "🟢 TROUVÉ : $ip_xml ($nom)"

            local target_dir="$BASE_DIR/$compte/devices/$dev_id"

            mkdir -p "$target_dir"

            # Déplacement du fichier d'info principal
            mv "$temp_xml" "$target_dir/DeviceInfo.xml"

            # Fichier témoin avec le nom de l'enceinte
            touch "$target_dir/$nom"

            # ---------- Téléchargements secondaires ----------
            for xml_type in presets recents; do

                curl -sSf \
                    --connect-timeout "$TIMEOUT" \
                    "http://${ip_xml}:8090/${xml_type}" \
                    -o "$BASE_DIR/$compte/${xml_type^}.xml" \
                    2>/dev/null

            done
			
            # ---------- Modification via SSH ----------
            if nc -z -w 2 "${ip_xml}" "22" > /dev/null 2>&1; then
                local SOURCES_XML="$BASE_DIR/$compte/Sources.xml"
                
                # Connexion SSH avec les options adaptées
                if ssh $SSH_OPTS root@"${ip_xml}" cat /mnt/nv/BoseApp-Persistence/1/Sources.xml > "$SOURCES_XML" 2>/dev/null; then
			
                    local BLOCK='<sourceItem source="RADIO_BROWSER" status="READY" isLocal="false" multiroomallowed="true"/>'

                    # Vérifie si RADIO_BROWSER existe déjà
                    if ! grep -q 'type="RADIO_BROWSER"' "$SOURCES_XML"; then
                        # Insère le bloc avant </sources>
                        sed -i "/<\/sources>/i\\
                    $BLOCK
                    " "$SOURCES_XML"

                        echo "Bloc RADIO_BROWSER ajouté pour $nom."
                    else
                        echo "Bloc RADIO_BROWSER déjà présent pour $nom."
                    fi
                else
                    echo "🔴 ÉCHEC SSH : Impossible de récupérer Sources.xml sur $ip_xml"
                fi
            fi
        else
            rm -f "$temp_xml"
        fi
    fi
}

# ---------- 3. Exécution ----------
echo "🔎 Scan en cours sur le réseau ${BASE_RESEAU}0/24..."

for s in {1..254}; do

    process_device "$s" &

    # Limitation des processus simultanés
    if (( s % 64 == 0 )); then
        wait
    fi

done

# Si aucun fichier Sources.xml n'a été créé pendant le scan
if ! find "$BASE_DIR" -type f -name "Sources.xml" -print -quit >/dev/null 2>&1; then
    echo "⚠️ Aucun fichier Sources.xml trouvé."
    echo "  ️  Il faut rooter, même de façon provisoire, une enceinte en utilisant"
    echo "  ️    - Le script ~/sc-tools/tools/rootST.sh <SuffixeIP> de l'enceinte la plus utilisée."
    echo "  ️    - La clé USB fat32 avec un fichier vierge remote_services pour celà utiliser ~/sc-tools/tools/create_remote_services.sh."
fi

echo "🏁 Scan et création de l'arborescence terminés sur $BASE_DIR."
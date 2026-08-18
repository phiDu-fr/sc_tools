#!/usr/bin/env bash

## Donne accès à root via ssh afin de récupérer le fichier Sources.xml, optionnellement le laisser permanent -p

# Sécurité : arrête le script en cas d'erreur (-e), de variable non définie (-u) ou d'erreur dans un pipe (-o pipefail)
set -euo pipefail

# Définition des variables
if (( $# < 1 || $# > 2 )); then
    echo "Syntaxe : $0 <SuffIP_SoundTouch> [-p]"
	echo "   -p : root permanent"
    exit 1
fi

[[ $1 =~ ^[0-9]{1,3}$ ]] || {
    echo "Erreur : suffixe IP invalide."
    exit 1
}

(( $1 >= 1 && $1 <= 254 )) || {
    echo "Erreur : suffixe IP hors plage (1-254)."
    exit 1
}

# Détection automatique du réseau local (ex: 192.168.1)
NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)

IP="${NET}.$1"
permanent=${2:-non}
PORT_APP=17000
PORT_SSH=22
ENV_FILE="/home/pi/sc_tools/.env"
SSH_OPTS="-o ConnectTimeout=5 \
          -o BatchMode=yes \
          -o StrictHostKeyChecking=accept-new"
		  
if nc -z -w 2 "$IP" "$PORT_SSH" > /dev/null 2>&1; then
    echo "Inutile $IP déjà rootée"
		if [[ "$permanent" == "-p" ]]; then
			echo "Root rendu permanent"
			ssh_key
			ssh $SSH_OPTS root@"$IP" touch /mnt/nv/remote_services
		fi
		echo ""
		echo "Configuration Marge :"
		echo $(curl -s http://$IP:8090/info | grep -oP '(?<=<margeURL>).*?(?=</margeURL>)')
		
    exit 0
fi

if [ -f "$ENV_FILE" ]; then
    # Exporte automatiquement les variables chargées
    set -a
    source "$ENV_FILE"
    set +a

    # Affichage des valeurs pour vérifier
    echo "Adresse Marge : $SC_MARGE_ADDR"
    echo "Port Marge    : $SC_MARGE_PORT"
    echo "Compte        : $SC_MARGE_ACCOUNT"
    echo "Base de val.  : $SC_SOUNDCORK_DB"
else
    echo "Erreur : Le fichier $ENV_FILE est introuvable."
    exit 1
fi

margeURL="http://$SC_MARGE_ADDR:$SC_MARGE_PORT/marge"
SOURCES=$SC_SOUNDCORK_DB/$SC_MARGE_ACCOUNT/Sources.xml
mkdir -p "$(dirname "$SOURCES")"

# Variables pour l'animation
spinner() {
    local duration=$1
    local spin='|/-\'

    for ((i=0;i<duration*5;i++)); do
        printf "\r%s" "${spin:$((i%4)):1}"
        sleep 0.2
    done

    printf "\r \r"
}

ssh_key() {
	ssh-keygen -F "$IP" >/dev/null || \
		ssh-keyscan -H "$IP" >> ~/.ssh/known_hosts
}

send_cmd() {
    printf '%s\n' "$1" | nc -w 2 "$IP" "$PORT_APP"
}

# --- Vérifications préalables ---

# Vérifier si la commande 'nc' (netcat) est installée
if ! command -v nc >/dev/null 2>&1; then
    echo "Erreur : 'nc' (netcat) n'est pas installé sur ce système." >&2
    exit 1
fi

echo "Configuration : ST=$IP | Marge=$SC_MARGE_ADDR | Port=$SC_MARGE_PORT"

# --- Exécution du script ---
send_cmd 'envswitch boseurls set "https://server;touch /tmp/remote_services;/etc/init.d/sshd start"  "https://server/update"'

echo "[INFO] Commande envoyée..."
echo ""

# Animation d'attente (la barre qui tourne 10 sec)
spinner 10

if ! nc -z -w 2 "$IP" "$PORT_SSH" > /dev/null 2>&1; then
    echo "[INFO] Le port SSH est injoignable. Déclenchement du redémarrage..."
	send_cmd "sys reboot"

	echo "[INFO] Attente du redémarrage (le port doit de nouveau répondre)..."

	echo ""
	timeout=120
	start=$(date +%s)

	while ! nc -z -w1 "$IP" "$PORT_APP" 2>/dev/null; do
		spinner 1

		(( $(date +%s) - start > timeout )) && {
			echo "[ERREUR] Timeout de redémarrage."
			exit 1
		}
	done

	echo "[INFO] L'enceinte a redémarrée..."
	
    # Animation d'attente (la barre qui tourne 30 sec)
	spinner 30
	
	if ! nc -z -w 1 "$IP" "$PORT_SSH" 2>/dev/null; then
		echo "[ERREUR] L'enceinte n'a pas pu être rootée"
		send_cmd "envswitch boseurls set http://$SC_MARGE_ADDR:$SC_MARGE_PORT/marge http://$SC_MARGE_ADDR:$SC_MARGE_PORT/updates/soundtouch"
		exit 1
	fi

else
    echo "[INFO] Le port SSH est joignable, aucun redémarrage nécessaire."
fi

ssh_key
ssh $SSH_OPTS root@"$IP" cat /mnt/nv/BoseApp-Persistence/1/Sources.xml > "$SOURCES"

spinner 20

# send_cmd "sys configuration margeServerUrl http://$SC_MARGE_ADDR:$SC_MARGE_PORT/marge"
# send_cmd "sys configuration swUpdateUrl http://$SC_MARGE_ADDR:$SC_MARGE_PORT/updates/soundtouch"
send_cmd "envswitch boseurls set $margeURL http://$SC_MARGE_ADDR:$SC_MARGE_PORT/updates/soundtouch"

echo "[INFO] fichier téléchargé $SOURCES"

if [[ "$permanent" == "-p" ]]; then
    ssh $SSH_OPTS root@"$IP" touch /mnt/nv/remote_services
fi

echo ""
echo "Root terminé avec succès "
echo ""

newMargeURL=$(curl -s http://$IP:8090/info | grep -oP '(?<=<margeURL>).*?(?=</margeURL>)')
if [[ "$newMargeURL" == "$margeURL" ]]; then
	echo "✅ La configuation margeURL est correcte, opérations terminée avec succés"
else
	echo "⚠️ Attention la configuration margeURL n'est pas bonne "
	echo "	- Valeur actuelle ❌ : $newMargeURL"
	echo "  - Il faut         ❎ : $margeURL" 	
fi

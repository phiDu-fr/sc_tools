#!/usr/bin/env bash

# Rechargement du fichier Sources.xml après redémarrage

if [ $# -lt 1 ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch | All>"
    echo "   Exemple : $0 65"
    exit 1
fi

PORT=8090

# Détection automatique du réseau local (ex: 192.168.1)
NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)

if [[ "${1,,}" == "all" ]]; then
	echo "🔎 Détection SoundTouch via Zeroconf + API..."
	echo

	# Vérifier si avahi-browse est installé
	if ! command -v avahi-browse >/dev/null 2>&1; then
		echo "❌ avahi-browse n'est pas installé."
		echo "   Installe-le avec : sudo apt install avahi-utils"
		exit 1
	fi

	avahi-browse -rt _soundtouch._tcp 2>/dev/null | while read -r line; do

		# Détection d'une ligne contenant l'adresse
		if echo "$line" | grep -q "address ="; then
			
			# Extraction robuste de l'IP sans sed
			IP=$(echo "$line" | cut -d'[' -f2 | cut -d']' -f1)

			echo "➡️  Appareil détecté via mDNS : $IP"

			# 2. Récupération dynamique du deviceID
			# On télécharge le XML et on utilise sed pour isoler la valeur dans deviceID="..."
			DEVICE_ID=$(curl -sS "http://$IP:$PORT/info" | sed -n 's/.*<info deviceID="\([^"]*\)".*/\1/p')

			# Vérification de la réussite de l'extraction
			if [ -z "$DEVICE_ID" ]; then
			  echo "Erreur : Impossible de récupérer le deviceID."
			  echo "Vérifiez l'adresse IP ou l'état de l'enceinte."
			  exit 1
			fi

			echo "Device ID récupéré : $DEVICE_ID"
			echo "Envoi de la notification..."

			# 3. Envoi de la requête POST avec le deviceID inséré dynamiquement
			curl -sS -X POST "http://$IP:$PORT/notification" \
			  -H 'Content-Type: application/xml' \
			  -d "<updates deviceID=\"$DEVICE_ID\"><sourcesUpdated/></updates>"
			sleep 2
			echo "sys reboot" | nc -w 1 $IP 17000
			echo " → Reboot envoyé à $IP"

		fi

	done
else
	IP="${NET}.$1"
	# 2. Récupération dynamique du deviceID
	# On télécharge le XML et on utilise sed pour isoler la valeur dans deviceID="..."
	DEVICE_ID=$(curl -sS "http://$IP:$PORT/info" | sed -n 's/.*<info deviceID="\([^"]*\)".*/\1/p')

	# Vérification de la réussite de l'extraction
	if [ -z "$DEVICE_ID" ]; then
	  echo "Erreur : Impossible de récupérer le deviceID."
	  echo "Vérifiez l'adresse IP ou l'état de l'enceinte."
	  exit 1
	fi

	echo "Device ID récupéré : $DEVICE_ID"
	echo "Envoi de la notification..."

	# 3. Envoi de la requête POST avec le deviceID inséré dynamiquement
	curl -sS -X POST "http://$IP:$PORT/notification" \
	  -H 'Content-Type: application/xml' \
	  -d "<updates deviceID=\"$DEVICE_ID\"><sourcesUpdated/></updates>"
	sleep 2
	echo "sys reboot" | nc -w 1 $IP 17000
	echo " → Reboot envoyé à $IP"
fi

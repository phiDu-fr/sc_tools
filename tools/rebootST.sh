#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch | All>"
    echo "   Exemple : $0 65"
    exit 1
fi

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

				echo "sys reboot" | nc -w 1 $IP 17000
				echo " → Reboot envoyé à $IP"

		fi

	done
	# echo "Scan du réseau : $NET.0/24"

	# for i in $(seq 1 254); do
		# IP="$NET.$i"

		# Test si un SoundTouch répond sur le port 8090
		# if curl -s --connect-timeout 0.3 http://$IP:8090/name >/dev/null; then
			# echo "SoundTouch détecté : $IP"

			# echo "sys reboot" | nc -w 1 $IP 17000
			# echo " → Reboot envoyé à $IP"

		# fi
	# done
else
	IP="${NET}.$1"
		if curl -s --connect-timeout 0.3 http://$IP:8090/name >/dev/null; then
			echo "SoundTouch détecté : $IP"

			echo "sys reboot" | nc -w 1 $IP 17000
			echo " → Reboot envoyé à $IP"
		else
			echo " → SoundTouch non détectée : $IP"
		fi
fi


# echo "Redémarrage de la machine locale…"
# sudo reboot -n

#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch | All> <cmd>"
    echo "   Exemple : $0 65 info"
    exit 1
fi

cmd="/$2"

# Détection automatique du réseau local (ex: 192.168.1)
NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)

echo "🔎 Détection SoundTouch via Zeroconf + API..."
echo

# Vérifier si avahi-browse est installé
if ! command -v avahi-browse >/dev/null 2>&1; then
	echo "❌ avahi-browse n'est pas installé."
	echo "   Installe-le avec : sudo apt install avahi-utils"
	exit 1
fi

echo '<speakers>'
if [[ "${1,,}" == "all" ]]; then

	avahi-browse -rt _soundtouch._tcp 2>/dev/null | while read -r line; do

		# Détection d'une ligne contenant l'adresse
		if echo "$line" | grep -q "address ="; then
			
			# Extraction robuste de l'IP sans sed
			IP=$(echo "$line" | cut -d'[' -f2 | cut -d']' -f1)

			echo "<speaker IP='${IP}'>"
				curl -s "http://${IP}:8090${cmd}"
			echo '</speaker>'
		fi

	done

else
	IP="${NET}.$1"
		if curl -s --connect-timeout 0.3 http://$IP:8090/name >/dev/null; then
			echo "<speaker IP='$IP'>"
				curl -s http://${IP}:8090${cmd}
			echo '</speaker>'
		else
			echo "<speaker IP='$IP'/>"
		fi
fi
echo '</speakers>'
echo ""
echo ""

# echo "Redémarrage de la machine locale…"
# sudo reboot -n

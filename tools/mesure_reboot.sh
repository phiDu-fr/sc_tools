#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Syntaxe : $0 <SuffIP_SoundTouch"
    echo "   Exemple : $0 65"
    exit 1
fi

# Détection automatique du réseau local (ex: 192.168.1)
NET=$(hostname -I | awk '{print $1}' | cut -d. -f1-3)

IP="${NET}.$1"
PORT_APP="17000"     # Remplacez par le port de votre application

echo "Déclenchement du redémarrage sur $IP..."
START_TIME=$(date +%s)

# Envoi de la commande de reboot
echo "sys reboot" | nc -w 1 "$IP" "$PORT_APP"

echo "Attente de l'arrêt de la machine..."
# On boucle tant que le port répond (la machine n'est pas encore éteinte)
while nc -z -w 1 "$IP" "$PORT_APP" 2>/dev/null; do
    sleep 1
done
echo "Machine hors ligne."

echo "Attente du redémarrage (le port doit de nouveau répondre)..."
# On boucle tant que le port NE répond PAS (la machine est en cours de boot)
while ! nc -z -w 1 "$IP" "$PORT_APP" 2>/dev/null; do
    sleep 1
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "Succès ! La machine et l'application ont mis $DURATION secondes pour redémarrer."

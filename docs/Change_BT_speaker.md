#Remplacement de l'enceinte Bluetooth pour l'utilisation de Pi-bluetooth dans sc_tools
Pour faciliter le changement d'enceinte à l'avenir, la meilleure approche est de combiner une **procédure d'appairage manuelle** (incontournable pour la sécurité Bluetooth) et un **script d'automatisation** qui va modifier ton code Python et redémarrer le service en une fraction de seconde.

Voici le guide complet à conserver.

### Étape 1 : Appairer la nouvelle enceinte au Raspberry Pi

Avant de dire à ton programme d'utiliser une nouvelle enceinte, le système Linux doit la connaître et lui faire confiance.

1. Allume ta nouvelle enceinte et mets-la en **mode appairage** (le voyant Bluetooth doit clignoter).
2. Ouvre ton terminal SSH et lance l'outil Bluetooth :
```bash
bluetoothctl

```


3. Dans l'invite `[bluetoothctl]>`, tape les commandes suivantes :
```text
scan on

```


*Patiente quelques secondes et repère l'adresse MAC de ta nouvelle enceinte (ex: `11:22:33:44:55:66`). Une fois que tu l'as trouvée :*
```text
scan off
pair 11:22:33:44:55:66
trust 11:22:33:44:55:66
connect 11:22:33:44:55:66
exit

```



*(L'étape `trust` est primordiale, c'est elle qui permettra à ton code Python de forcer la reconnexion tout seul plus tard).*

---

### Étape 2 : Créer le script de remplacement

Nous allons créer un petit script bash interactif. Tu n'auras plus jamais besoin de modifier le code Python à la main.

1. Crée le fichier du script dans ton dossier `sc_tools` :
```bash
nano /home/pi/sc_tools/tools/change_speaker.sh

```


2. Colle ce code à l'intérieur :
```bash
#!/bin/bash

# Chemins de configuration
PYTHON_FILE="/home/pi/sc_tools/tools/py/virtual_soundtouch.py"
SERVICE_NAME="virtual_soundtouch.service"

echo "=========================================="
echo "   REMPLACEMENT DE L'ENCEINTE BLUETOOTH   "
echo "=========================================="

# Demander la nouvelle adresse MAC
read -p "Entrez l'adresse MAC de la nouvelle enceinte (ex: 11:22:33:44:55:66) : " NEW_MAC

# Vérification du format de l'adresse MAC
if [[ ! "$NEW_MAC" =~ ^([a-fA-F0-9]{2}:){5}[a-fA-F0-9]{2}$ ]]; then
    echo "❌ Erreur : Format d'adresse MAC invalide."
    exit 1
fi

# Convertir en majuscules pour être propre
NEW_MAC=$(echo "$NEW_MAC" | tr 'a-z' 'A-Z')

echo "Mise à jour du fichier Python..."
# Commande SED pour trouver et remplacer l'ancienne adresse MAC par la nouvelle
sed -i -E "s/BT_MAC_ADDRESS = \"([A-Fa-f0-9:]+)\"/BT_MAC_ADDRESS = \"$NEW_MAC\"/" $PYTHON_FILE

echo "Redémarrage de l'émulateur..."
sudo systemctl restart $SERVICE_NAME

echo "✅ Terminé ! Le système enverra désormais l'audio vers $NEW_MAC."

```


*Enregistre et quitte (Ctrl+O, Entrée, Ctrl+X).*
3. Rend ce script exécutable (tu ne le fais qu'une seule fois) :
```bash
chmod +x /home/pi/sc_tools/tools/change_speaker.sh

```



---

### Étape 3 : Utiliser le script

Maintenant, dès que tu voudras changer d'enceinte (après l'avoir appairée via l'Étape 1), il te suffira de taper cette commande :

```bash
/home/pi/sc_tools/tools/change_speaker.sh

```

Le script te demandera l'adresse MAC, modifiera le code Python automatiquement (la variable gardera le nom `BT_MAC_ADDRESS` dans le code, mais contiendra la nouvelle valeur) et relancera l'enceinte virtuelle. Ta nouvelle enceinte émettra le son immédiatement au prochain lancement d'une radio !

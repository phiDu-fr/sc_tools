#!/bin/bash

# Construit un fichier Soundtouch.ini contenant constituant les données de la base Soundcork
# Aucune utilité pour soundcork mais rend les données lisibles

# Fait un compte rendu final pour s'assurer que toutes les enceintes soient bien sur le même compte
 
BASE_DIR="/home/pi/soundcork/dataX"
INI_FILE="$BASE_DIR/Soundtouch.ini"

TMP_INI="/tmp/Soundtouch.ini.tmp"

declare -A UUID_COUNT
declare -A UUID_NAMES

if [ ! -d "$BASE_DIR" ]; then
    echo "Le répertoire $BASE_DIR n'existe pas ou n'est pas le bon"
    echo "Lancez au préalable create_data.sh ou vérifiez si $BASE_DIR est aussi dans create_data"
    exit 1
fi

echo "Analyse des DeviceInfo.xml..."

# Initialisation du fichier INI
echo "[Compte]" > "$TMP_INI"
echo "margeAccountUUID=" >> "$TMP_INI"

while read xmlfile
do

compte=$(xmlstarlet sel -t -v "//margeAccountUUID" "$xmlfile" 2>/dev/null | tr -d '\r\n\t ')
nom=$(xmlstarlet sel -t -v "//name" "$xmlfile" 2>/dev/null | tr -d '\r')
dev_id=$(xmlstarlet sel -t -v "//info/@deviceID" "$xmlfile" 2>/dev/null | tr -d '\r')
type=$(xmlstarlet sel -t -v "//type" "$xmlfile" 2>/dev/null | tr -d '\r')
marge_url=$(xmlstarlet sel -t -v "//margeURL" "$xmlfile" 2>/dev/null | tr -d '\r')

# Extraction de la première IP pour éviter les sauts de lignes
ip_xml=$(xmlstarlet sel -t -v "(//ipAddress)[1]" "$xmlfile" 2>/dev/null | tr -d '\r')

if [ -z "$dev_id" ]; then
    continue
fi

echo "Trouvé : $nom"
echo "DeviceID : $dev_id"
echo "UUID : $compte"
echo "IP : $ip_xml"
echo

# Comptage UUID
if [ -z "${UUID_COUNT[$compte]}" ]; then
    UUID_COUNT[$compte]=1
    UUID_NAMES[$compte]="$nom"
else
    UUID_COUNT[$compte]=$(( ${UUID_COUNT[$compte]} + 1 ))
    UUID_NAMES[$compte]="${UUID_NAMES[$compte]}, $nom"
fi

# Ajout section INI
echo "" >> "$TMP_INI"
echo "[$dev_id]" >> "$TMP_INI"
echo "nom=$nom" >> "$TMP_INI"
echo "ip=$ip_xml" >> "$TMP_INI"
echo "type=$type" >> "$TMP_INI"
echo "margeAccountUUID=$compte" >> "$TMP_INI"
echo "margeURL=$marge_url" >> "$TMP_INI"

done < <(find "$BASE_DIR" -type f -name "DeviceInfo.xml")

echo
echo "=============================="
echo "COMPTE RENDU"
echo "=============================="

UUID_TOTAL=0

for uuid in "${!UUID_COUNT[@]}"
do
UUID_TOTAL=$((UUID_TOTAL + 1))
done

if [ "$UUID_TOTAL" -eq 1 ]; then

for uuid in "${!UUID_COUNT[@]}"
do
    echo "Toutes les enceintes utilisent le même margeAccountUUID"
    echo
    echo "UUID : $uuid"

    sed -i "s|^margeAccountUUID=$|margeAccountUUID=$uuid|" "$TMP_INI"
done

else

echo "Plusieurs margeAccountUUID détectés"
echo

sed -i "s|^margeAccountUUID=$|margeAccountUUID=error|" "$TMP_INI"

for uuid in "${!UUID_COUNT[@]}"
do
    echo "UUID : $uuid"
    echo "Nombre : ${UUID_COUNT[$uuid]}"
    echo "Enceintes : ${UUID_NAMES[$uuid]}"
    echo
done

fi

mv "$TMP_INI" "$INI_FILE"

echo "INI mis à jour : $INI_FILE"

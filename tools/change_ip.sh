#!/usr/bin/env bash
set -euo pipefail               # Arrêt sur erreur, variables non définies, pipelines sécurisés
IFS=$'\n\t'                     # Gestion sûre des espaces dans les noms de fichiers

# IP locale
LOCAL_IP=$(hostname -I|awk '{print $1}')
echo "IP locale : $LOCAL_IP"
cd /home/pi

# fichiers à traiter
files=(
./soundcork/docker-compose.yml
./soundcork-stockholm-app/docker-compose.yml
./soundcork-stockholm-app/.env
)

#./soundcork/soundcork/.env.private:base_url
#./soundcork-stockholm-app/.env

for entry in "${files[@]}"; do
  file="${entry%%:*}"
  [[ -f "$file" ]]||{ echo "⚠️  $file absent ; skip"; continue; }
  echo -e "\n---\nFichier : $file"
  # read -rp "Remplacer l'IP dans ce fichier ? [o/N] " ans
  # [[ "$ans" =~ ^[oO]$ ]]||continue
  cp "$file" "${file}.bak"
  sed -i "s/{@margeIP@}/${LOCAL_IP}/g" "$file"
  #sed -i -E "s/[0-9]{1,3}(\.[0-9]{1,3}){3}/${LOCAL_IP}/g" "$file"
done

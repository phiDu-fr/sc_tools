#!/usr/bin/env bash
set -euo pipefail

# Usage:
# ./lireMP3.sh SOUNDTOUCH_IP MEDIA_SERVER_IP MP3_PATH [TITLE]
# Exemple:
# ./lireMP3.sh 192.168.1.65 192.168.1.116 /local_podcast/podcast.mp3 'front populaire'

soundtouch_ip="${1:-}"
media_server_ip="${2:-}"
mp3_path="${3:-}"
title="${4:-Podcast}"
port="8000"

if [[ -z "$soundtouch_ip" || -z "$media_server_ip" || -z "$mp3_path" ]]; then
  echo "Usage: $0 SOUNDTOUCH_IP MEDIA_SERVER_IP MP3_PATH [TITLE]"
  exit 1
fi

# Construire l'URL du mp3
mp3_url="http://${media_server_ip}${mp3_path}"

# Construire le JSON compact. ATTENTION: si title ou mp3_url contiennent des guillemets ou caractères spéciaux,
# il faut les échapper correctement. Ce script suppose des valeurs simples.
json_data="{\"name\":\"${title}\",\"imageUrl\":\"\",\"streamUrl\":\"${mp3_url}\"}"

# Encoder en base64 sans saut de ligne
b64=$(printf '%s' "$json_data" | base64 | tr -d '\n')

# Construire l'URL orion (même structure que dans le script Python)
orion_url="http://${media_server_ip}:${port}/core02/svc-bmx-adapter-orion/prod/orion/station?data=${b64}"

# Construire le XML
xml="<ContentItem source=\"LOCAL_INTERNET_RADIO\" type=\"stationurl\" location=\"${orion_url}\"><itemName>${title}</itemName></ContentItem>"
echo $xml

# Envoyer la requête POST au SoundTouch
curl -s -X POST "http://${soundtouch_ip}:8090/select" \
  -H "Content-Type: text/xml" \
  --data "$xml"

# Retourner le code de sortie de curl
exit $?

#!/usr/bin/env bash

set -euo pipefail

BASE_RESEAU=$(hostname -I | cut -d' ' -f1 | cut -d. -f1-3)
input="$BASE_RESEAU"

# Extraire la base (ex: 192.168.1)
if [[ "$input" =~ ^([0-9]+\.[0-9]+\.[0-9]+)\.0/24$ ]]; then
  base="${BASH_REMATCH[1]}"
elif [[ "$input" =~ ^([0-9]+\.[0-9]+\.[0-9]+)\.0$ ]]; then
  base="${BASH_REMATCH[1]}"
elif [[ "$input" =~ ^([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  base="${BASH_REMATCH[1]}"
else
  echo "Format d'adresse non reconnu. Exemple valide: 192.168.1.0/24 ou 192.168.1" >&2
  exit 2
fi

# Correction : On utilise une chaîne de caractères plutôt qu'un tableau (array)
# Bash ne peut pas exporter un tableau vers les processus enfants (xargs)
PORTS_LIST="22 80 443 8090"

# Timeout en SECONDES (1 seconde est largement suffisant pour un LAN)
ping_timeout=1
port_timeout=1

# Fonction pour obtenir le nom d'hôte PTR
get_hostname() {
  local ip="$1"
  if command -v getent >/dev/null 2>&1; then
    local ge
    ge=$(getent hosts "$ip" 2>/dev/null || true)
    if [ -n "$ge" ]; then
      echo "$ge" | awk '{print $2; exit}'
      return
    fi
  fi

  if command -v host >/dev/null 2>&1; then
    local h
    h=$(host "$ip" 2>/dev/null || true)
    if [[ "$h" =~ pointer[[:space:]]([a-zA-Z0-9._-]+)\.? ]]; then
      echo "${BASH_REMATCH[1]}"
      return
    fi
  fi

  if command -v nslookup >/dev/null 2>&1; then
    local n
    n=$(nslookup "$ip" 2>/dev/null || true)
    if [[ "$n" =~ name[[:space:]]*=[[:space:]]*([a-zA-Z0-9._-]+)\.? ]]; then
      echo "${BASH_REMATCH[1]}"
      return
    fi
  fi

  echo "-"
}

# Test de port via /dev/tcp avec timeout
test_port() {
  local ip="$1"; local port="$2"
  
  # Correction : Ajout de ':' (commande vide) pour garantir la redirection TCP
  # Note: Assurez-vous que la commande GNU 'timeout' est bien installée sur votre système
  if timeout "${port_timeout}" bash -c ": >/dev/tcp/${ip}/${port}" >/dev/null 2>&1; then
    echo "open"
  else
    echo "closed"
  fi
}

# Fonction qui scanne une IP
scan_one() {
  local i="$1"
  local ip="${base}.${i}"

  # Ping rapide pour filtrer hôtes inactifs
  if ping -c 1 -W "${ping_timeout}" "$ip" >/dev/null 2>&1; then
    local hostn
    hostn=$(get_hostname "$ip")
    local open_ports=()
    
    # On itère sur la variable chaîne exportée, qui va se scinder sur les espaces
    for p in $PORTS_LIST; do
      if [ "$(test_port "$ip" "$p")" = "open" ]; then
        open_ports+=("$p")
      fi
    done
    
    # Formatage des ports
    local ports_str="-"
    if [ ${#open_ports[@]} -gt 0 ]; then
      ports_str=$(IFS=,; echo "${open_ports[*]}")
    fi
    printf "%3s\t%-15s\t%-30s\t%s\n" "$i" "$ip" "$hostn" "$ports_str"
  fi
}

# En-tête
printf "%3s\t%-15s\t%-30s\t%s\n" "sfx" "adresse" "hostname" "ports_open"
printf "%3s\t%-15s\t%-30s\t%s\n" "---" "---------------" "------------------------------" "---------"

# Exportation des fonctions et des variables simples pour le sous-shell
export -f get_hostname test_port scan_one
export base PORTS_LIST ping_timeout port_timeout

# Lancer les scans en parallèle
seq 1 254 | xargs -P50 -I{} bash -c 'scan_one "$@"' _ {}

exit 0
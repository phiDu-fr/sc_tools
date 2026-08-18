#!/bin/bash

# SC_TOOLS

# Nom du fichier de sortie 
OUTPUT_FILE="documentation_sources.md"
TARGET_DIR="${1:-.}"

echo "# Documentation des codes sources" > "$OUTPUT_FILE"
echo "Généré le $(date '+\%Y-\%m-\%d \%H:\%M:\%S')" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# ==========================================
# 1. GÉNÉRATION DE L'ARBORESCENCE (TREE)
# ==========================================
echo "## Arborescence du projet" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo '```text' >> "$OUTPUT_FILE"

# On vérifie si la commande "tree" est installée
if command -v tree >/dev/null 2>&1; then
    echo "Génération de l'arborescence..."
    # -I : dossiers à ignorer
    # -P : extensions à inclure
    # --prune : ne pas afficher les dossiers vides
    tree "$TARGET_DIR" \
        -I "Music|music|.git|node_modules|__pycache__|venv|tools|docs|update" \
        -P "*.py|*.js|*.html|*.yml|*.yaml|Dockerfile*|*.sh|*.css" \
        --prune >> "$OUTPUT_FILE"
else
    echo "[!] La commande 'tree' n'est pas installée sur ce système." >> "$OUTPUT_FILE"
    echo "[!] Installez-la (ex: sudo apt install tree) pour afficher l'arborescence ici." >> "$OUTPUT_FILE"
fi

echo '```' >> "$OUTPUT_FILE"
echo "<br>" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "---" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "## Fichiers sources" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"


# ==========================================
# 2. GÉNÉRATION DU CODE SOURCE (FIND)
# ==========================================
# Fonction pour déterminer le langage Markdown
get_markdown_lang() {
    local filename=$(basename "$1")
    local ext="${filename##*.}"
    
    if [ "$filename" = "$ext" ]; then
        if [[ "$filename" == *"Dockerfile"* ]]; then echo "dockerfile"; else echo "text"; fi
    else
        case "$ext" in
            py) echo "python" ;;
            js) echo "javascript" ;;
            html|htm) echo "html" ;;
            yml|yaml) echo "yaml" ;;
            sh) echo "bash" ;;
            *) echo "text" ;;
        esac
    fi
}

echo "Génération des sources en cours dans '$OUTPUT_FILE'..."

# On cherche et on ajoute le contenu des fichiers
find "$TARGET_DIR" \
    -type d \( -name ".git" -o -name "node_modules" -o -name "__pycache__" -o -name "venv" -o -name "Music" -o -name "music" -o -name "tools" -o -name "docs" -o -name "update" \) -prune -o \
    -type f \( -name "*.py" -o -name "*.js" -o -name "*.html" -o -name "*.yml" -o -name "*.yaml" -o -name "Dockerfile*" -o -name "*.sh" -o -name "*.css" \) -print \
    | sort | while IFS= read -r file; do
    
    # Nettoyer le chemin
    rel_path="${file#./}"
    
    # Éviter de s'inclure soi-même ou le fichier de sortie
    if [[ "$rel_path" == "$(basename "$0")" || "$rel_path" == "$OUTPUT_FILE" ]]; then
        continue
    fi

    lang=$(get_markdown_lang "$file")
    echo "Ajout de : $rel_path"
    
    echo "### \`$rel_path\`" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo '```'"$lang" >> "$OUTPUT_FILE"
    cat "$file" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo '```' >> "$OUTPUT_FILE"
    echo "<br>" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"

done

echo "✅ Terminé ! Consultez le fichier $OUTPUT_FILE"

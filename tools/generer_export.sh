#!/bin/bash
# Fichier : generer_export.sh
# Description : Génère un fichier global avec l'arbre des fichiers du projet et le contenu concaténé.

FICHIER_GLOBAL="./export_pour_ia_complet.txt"
LISTE_FICHIERS="/tmp/filelist_$$.txt"

# Nettoyage préalable
rm -f "$FICHIER_GLOBAL" "$LISTE_FICHIERS"

# Récupération des fichiers suivis par Git en excluant les binaires/assets et dossiers inutiles
git ls-files --exclude-standard | grep -vE '\.(png|svg|md|ico)$|^tools/' > "$LISTE_FICHIERS"

# Génération de l'arborescence en tête de fichier
if command -v tree &> /dev/null; then
    tree --gitignore --noreport > "$FICHIER_GLOBAL"
else
    echo "=== ARBORESCENCE DES FICHIERS ===" > "$FICHIER_GLOBAL"
    cat "$LISTE_FICHIERS" >> "$FICHIER_GLOBAL"
fi

# Concaténation de chaque fichier avec un séparateur clair
while IFS= read -r fichier; do
    if [ -f "$fichier" ]; then
        awk 'FNR==1{print "\n\n========================================\nFichier : "FILENAME"\n========================================\n"}1' "$fichier" >> "$FICHIER_GLOBAL"
    fi
done < "$LISTE_FICHIERS"

rm -f "$LISTE_FICHIERS"

echo "Génération terminée : $FICHIER_GLOBAL ($(wc -l < "$FICHIER_GLOBAL") lignes au total)."

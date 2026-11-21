#!/bin/bash
# Fichier : decouper_export.sh
# Description : Découpe export_pour_ia_complet.txt en fichiers de 10 000 lignes maximum.

FICHIER_ENTREE="./export_pour_ia_complet.txt"
PREFIXE_SORTIE="export_pour_ia_part"
MAX_LIGNES=10000

if [ ! -f "$FICHIER_ENTREE" ]; then
    echo "Erreur : Le fichier $FICHIER_ENTREE est introuvable. Lance d'abord generer_export.sh."
    exit 1
fi

# Nettoyage des anciens découpages
rm -f "${PREFIXE_SORTIE}"*.txt

awk -v max="$MAX_LIGNES" -v prefix="$PREFIXE_SORTIE" '
BEGIN {
    part = 1
    line_count = 0
    out_file = sprintf("%s%02d.txt", prefix, part)
}
{
    # Si on atteint un séparateur de fichier et que le bloc suivant risque de dépasser la limite
    # (ou si on approche à 85% de la limite), on bascule proprement sur le fichier suivant
    if ($0 == "========================================" && line_count > (max * 0.85)) {
        close(out_file)
        part++
        line_count = 0
        out_file = sprintf("%s%02d.txt", prefix, part)
    }

    # Sécurité absolue : si un seul fichier dépasse à lui seul les 10 000 lignes, on coupe net
    if (line_count >= max) {
        close(out_file)
        part++
        line_count = 0
        out_file = sprintf("%s%02d.txt", prefix, part)
    }

    print $0 >> out_file
    line_count++
}
END {
    close(out_file)
    printf "Découpage terminé en %d fichier(s) :\n", part
}
' "$FICHIER_ENTREE"

# Affichage du récapitulatif des fichiers créés avec leur nombre de lignes exact
wc -l "${PREFIXE_SORTIE}"*.txt
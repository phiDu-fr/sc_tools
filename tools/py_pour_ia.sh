#!/bin/bash
# Fichier : rapport_pour_ia.sh
# Description : génère un fichier avec l'abre des fichiers du projet, et tous les fichiers cocaténés.
# à transmettre à une IA.


rm -f ./export_py_ia.txt
find tools/ -name *.py  > /tmp/filelist.txt

while read -r fichier; do
    awk 'FNR==1{print "\n\n========================================\nFichier : "FILENAME"\n========================================\n"}1' "$fichier" >> export_py_ia.txt
done < /tmp/filelist.txt
rm -f /tmp/filelist.txt


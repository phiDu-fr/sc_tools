#!/bin/bash

# Vérification qu'au moins un argument (le script cible) est fourni
if [ $# -eq 0 ]; then
    echo "❌ Erreur : Aucun script spécifié."
    echo "💡 Utilisation : $0 <commande_ou_script> [param1] [param2] ..."
    exit 1
fi

echo "🚀 Lancement de : $@"
echo "-----------------------------------"

# 1. Enregistrement du temps de début (secondes.nanosecondes)
START_TIME=$(date +%s.%N)

# 2. Exécution du script cible avec TOUS ses paramètres ("$@")
# Les guillemets sont obligatoires pour préserver les espaces dans les arguments
"$@"

# 3. Sauvegarde du code de retour du script exécuté (succès=0, erreur>0)
EXIT_CODE=$?

# 4. Enregistrement du temps de fin
END_TIME=$(date +%s.%N)

echo "-----------------------------------"

# 5. Calcul de la différence avec awk (plus standard et évite d'installer 'bc')
DURATION=$(awk "BEGIN {printf \"%.3f\", $END_TIME - $START_TIME}")

# Affichage du résultat
echo "⏱️  Durée d'exécution : $DURATION secondes."

# 6. On quitte en renvoyant le code d'erreur exact du script d'origine
exit $EXIT_CODE
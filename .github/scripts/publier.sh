#!/usr/bin/env bash
# Commite et pousse les fichiers produits par le service (docs/ et etat/).
# Usage : publier.sh "message de commit"
# Chaque exécution commite : cela garde aussi les tâches planifiées actives (section 15).
set -euo pipefail
message="$1"
git config user.name "onlybrief-bot"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add docs etat
if git diff --cached --quiet; then
  echo "Rien de nouveau à publier."
  exit 0
fi
git commit -m "$message"
for essai in 1 2 3 4 5; do
  if git push; then
    echo "Publié : $message"
    exit 0
  fi
  echo "Envoi refusé (essai $essai), mise à jour puis nouvel essai…"
  git pull --rebase
  sleep $((essai * 5))
done
echo "::error::Impossible de pousser les fichiers publiés."
exit 1

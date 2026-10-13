#!/usr/bin/env bash
# Crée la clé de signature de l'APK OnlyBrief sur Mac (à faire UNE SEULE FOIS).
# Usage (Terminal, à la racine du dépôt) :  bash outils/creer-cle-signature.sh
set -euo pipefail
dossier="$HOME/OnlyBrief-signature"
cle="$dossier/onlybrief.jks"
keytool="${JAVA_HOME:-/Applications/Android Studio.app/Contents/jbr/Contents/Home}/bin/keytool"
[ -x "$keytool" ] || keytool="$(command -v keytool)"
[ -e "$cle" ] && { echo "Une clé existe déjà : $cle. Ne la remplacez pas."; exit 1; }
mkdir -p "$dossier"
echo "keytool va demander un mot de passe (choisissez-en un solide et notez-le)."
"$keytool" -genkeypair -v -keystore "$cle" -alias onlybrief -keyalg RSA -keysize 4096 -validity 36500 \
  -dname "CN=OnlyBrief, O=Mathieu Ferrante, C=FR"
base64 -i "$cle" | tr -d '\n' > "$dossier/KEYSTORE_BASE64.txt"
echo
echo "Clé créée : $cle"
echo "1. Copiez le dossier $dossier sur DEUX supports hors du Mac."
echo "2. Secrets GitHub : KEYSTORE_BASE64 (contenu de KEYSTORE_BASE64.txt), KEYSTORE_PASSWORD, KEY_PASSWORD, KEY_ALIAS = onlybrief."
echo "3. Supprimez ensuite KEYSTORE_BASE64.txt."

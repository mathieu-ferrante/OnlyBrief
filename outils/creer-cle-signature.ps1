# Crée la clé de signature de l'APK OnlyBrief (à faire UNE SEULE FOIS).
# Usage (PowerShell, à la racine du dépôt) :  powershell -ExecutionPolicy Bypass -File outils\creer-cle-signature.ps1
# La clé est créée HORS du dépôt, dans %USERPROFILE%\OnlyBrief-signature. Ne jamais la commiter.

$ErrorActionPreference = "Stop"
$dossier = Join-Path $env:USERPROFILE "OnlyBrief-signature"
$cle = Join-Path $dossier "onlybrief.jks"

$keytool = @(
    "$env:JAVA_HOME\bin\keytool.exe",
    "C:\Program Files\Android\Android Studio\jbr\bin\keytool.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $keytool) { throw "keytool introuvable : installez Android Studio ou un JDK." }

if (Test-Path $cle) { throw "Une clé existe déjà : $cle. Ne la remplacez pas, sinon les mises à jour seront impossibles." }
New-Item -ItemType Directory -Force $dossier | Out-Null

Write-Host "keytool va demander un mot de passe (choisissez-en un solide et notez-le)." -ForegroundColor Cyan
& $keytool -genkeypair -v -keystore $cle -alias onlybrief -keyalg RSA -keysize 4096 -validity 36500 `
    -dname "CN=OnlyBrief, O=Mathieu Ferrante, C=FR"
if ($LASTEXITCODE -ne 0) { throw "La création de la clé a échoué." }

$texte = [Convert]::ToBase64String([IO.File]::ReadAllBytes($cle))
Set-Content -Path (Join-Path $dossier "KEYSTORE_BASE64.txt") -Value $texte -Encoding ascii -NoNewline

Write-Host ""
Write-Host "Clé créée : $cle" -ForegroundColor Green
Write-Host "1. Copiez maintenant le dossier $dossier sur DEUX supports hors du PC (clé USB, cloud personnel)."
Write-Host "2. Secrets GitHub à créer : KEYSTORE_BASE64 (contenu de KEYSTORE_BASE64.txt), KEYSTORE_PASSWORD et KEY_PASSWORD (le mot de passe), KEY_ALIAS = onlybrief."
Write-Host "3. Supprimez ensuite KEYSTORE_BASE64.txt du PC (la clé .jks reste dans le dossier)."

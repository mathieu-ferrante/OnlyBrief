# Mise en service d'OnlyBrief — à faire une seule fois

Ces étapes demandent ton compte GitHub, ton compte Google et ton téléphone : elles ne peuvent
pas être faites à ta place. Compte environ 30 minutes. Tout est gratuit.

Coche au fur et à mesure.

---

## 1. GitHub : publication et automatisation

Sur <https://github.com/mathieu-ferrante/OnlyBrief> :

- [ ] **Pages** : *Settings* → *Pages* → *Build and deployment* → *Source* : « Deploy from a branch » →
      branche `main`, dossier `/docs` → *Save*.
      Au bout de 1 à 2 minutes, <https://mathieu-ferrante.github.io/OnlyBrief/apercu.html> affiche l'édition.
- [ ] **Droits d'écriture des automatisations** : *Settings* → *Actions* → *General* →
      *Workflow permissions* → « Read and write permissions » → *Save*.
- [ ] **Clé Gemini** : *Settings* → *Secrets and variables* → *Actions* → *New repository secret* →
      nom `GEMINI_API_KEY`, valeur = ta clé Gemini.
      Conseil : comme la clé a circulé dans une conversation, tu peux en générer une nouvelle sur
      <https://aistudio.google.com/apikey>, supprimer l'ancienne et mettre la nouvelle ici.

**Premier essai** : onglet *Actions* → « Édition quotidienne » → *Run workflow* → *Run workflow*.
En 2 à 3 minutes, un commit « Édition du … (automatique) » apparaît et l'aperçu en ligne est à jour.
L'avertissement « FIREBASE_SERVICE_ACCOUNT absente » est normal tant que l'étape 2 n'est pas faite.

À partir de là, l'édition part **seule** chaque jour à 7 h 30 (semaine) et 10 h (week-end),
et les alertes sont vérifiées toutes les deux heures de 9 h à 21 h.

---

## 2. Firebase : les notifications

Sur <https://console.firebase.google.com>, avec ton compte Google :

- [ ] *Créer un projet* → nom `onlybrief` → **désactive Google Analytics** (aucune mesure d'audience, NF-09) → *Créer*.
- [ ] Dans le projet : icône Android (*Ajouter une application*) →
      nom du package : `io.github.mathieuferrante.onlybrief` → surnom : OnlyBrief → *Enregistrer*.
- [ ] *Télécharger google-services.json*. Puis :
  - copie le fichier dans le dossier `app\` du dépôt (il est ignoré par git, il ne sera pas publié) ;
  - crée le secret GitHub `GOOGLE_SERVICES_JSON` en collant **tout le contenu** du fichier.
  - Les étapes suivantes de l'assistant Firebase (« ajouter le SDK ») sont déjà faites : clique sur *Suivant* jusqu'au bout.
- [ ] ⚙️ *Paramètres du projet* → onglet *Comptes de service* → *Générer une nouvelle clé privée* → *Générer la clé*.
      Un fichier `.json` est téléchargé :
  - crée le secret GitHub `FIREBASE_SERVICE_ACCOUNT` en collant **tout son contenu** ;
  - puis **supprime ce fichier** de ton PC (c'est une vraie clé secrète).
- [ ] Vérifie dans *Paramètres du projet* → *Cloud Messaging* que « API Firebase Cloud Messaging (V1) » est **activée**.

---

## 3. Clé de signature de l'application

La clé permet d'installer les mises à jour par-dessus l'ancienne version. **Si elle est perdue,
il faudra désinstaller l'application (et perdre l'historique) à chaque mise à jour.**

- [ ] Dans PowerShell, à la racine du dépôt :

  ```powershell
  powershell -ExecutionPolicy Bypass -File outils\creer-cle-signature.ps1
  ```

  (sur Mac : `bash outils/creer-cle-signature.sh`). Choisis un mot de passe solide et note-le dans ton gestionnaire de mots de passe.
- [ ] Copie le dossier `C:\Users\mathieu.ferrante\OnlyBrief-signature` sur **deux supports hors du PC**
      (par exemple une clé USB et ton cloud personnel).
- [ ] Crée les secrets GitHub :

  | Secret | Valeur |
  | --- | --- |
  | `KEYSTORE_BASE64` | contenu du fichier `KEYSTORE_BASE64.txt` |
  | `KEYSTORE_PASSWORD` | le mot de passe choisi |
  | `KEY_PASSWORD` | le même mot de passe |
  | `KEY_ALIAS` | `onlybrief` |

- [ ] Supprime ensuite `KEYSTORE_BASE64.txt` (le fichier `onlybrief.jks` reste dans le dossier).

---

## 4. Publier la version 1.0.0

Dans un terminal, à la racine du dépôt :

```powershell
git tag v1.0.0
git push origin v1.0.0
```

L'onglet *Actions* → « APK signé » construit l'application (5 à 10 minutes), puis la publie dans
*Releases* et met à jour `version.json`.

---

## 5. Installer sur le POCO M7 Pro 5G

- [ ] Sur le téléphone, ouvre <https://github.com/mathieu-ferrante/OnlyBrief/releases/latest>
      et touche `onlybrief-1.0.0.apk`.
- [ ] Ouvre le fichier téléchargé ; à la question sur les « sources inconnues », autorise le navigateur.
- [ ] Lance OnlyBrief et **autorise les notifications** quand l'application le demande.
- [ ] Pour des notifications à l'heure, dans *Paramètres* → *Applications* → *Gérer les applications* → *OnlyBrief* :
  - active **Démarrage automatique** ;
  - *Économiseur de batterie* → **Aucune restriction**.

  (Le bouton « Ouvrir la fiche de l'application » de l'écran Réglages d'OnlyBrief y mène directement.)

C'est terminé : la recette (section 12 du cahier des charges) peut commencer.

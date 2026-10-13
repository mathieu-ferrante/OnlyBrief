# OnlyBrief

Veille quotidienne livrée sur Android : chaque matin (7 h 30 en semaine, 10 h le week-end), une
édition courte organisée par sujet, avec pour chaque actualité un résumé de deux lignes en
français et une ligne « Pourquoi c'est important ». Au plus une alerte par jour pour une annonce majeure.

| Dossier | Rôle |
| --- | --- |
| `sujets.yaml` | sujets suivis et leurs sources : **le seul fichier à modifier pour changer la veille** |
| `service/` | service Python : collecte, filtres, résumés (Google Gemini), publication, notifications |
| `docs/` | fichiers publiés par GitHub Pages : éditions, alertes, `index.json`, `version.json`, `apercu.html` |
| `etat/` | mémoire du service : liens cités (14 jours), dernière configuration valide, notifications envoyées |
| `app/` | application Android (Kotlin, Compose, Room, Firebase Cloud Messaging) |
| `.github/workflows/` | `edition.yml` (chaque matin), `alertes.yml` (toutes les 2 h), `apk.yml` (version signée) |

Première installation : voir **[MISE_EN_SERVICE.md](MISE_EN_SERVICE.md)**.
Référence : [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md). Le modèle de langage est Google Gemini
(offre gratuite) : GitHub Models, prévu à l'origine, a été retiré par GitHub le 30 juillet 2026.

---

## Note d'exploitation

### Ajouter, modifier ou suspendre un sujet

1. Sur GitHub, ouvrir `sujets.yaml` → icône crayon (*Edit*).
2. Copier un bloc de sujet existant (de `- id:` jusqu'à ses sources), changer `id`, `nom`, `ordre`, les mots-clés et les sources.
   Les explications de chaque champ sont en tête du fichier. Pour suspendre un sujet sans le supprimer : `actif: false`.
3. *Commit changes*. L'édition suivante contient la nouvelle section, sans toucher à l'application.

Si le fichier est mal écrit, l'édition part quand même avec la dernière configuration valide et l'erreur
apparaît dans le journal (ci-dessous) et en bas de l'aperçu. Pour vérifier avant d'enregistrer, sur son poste :
`python -m onlybrief verifier-config`.

### Lire le journal d'exécution

- Onglet **Actions** du dépôt → « Édition quotidienne » ou « Alertes en journée » → l'exécution voulue →
  étape « Préparer l'édition ». On y lit les sources lues, les articles retenus et écartés, les requêtes au modèle et les erreurs.
- Résumé dans chaque édition : <https://mathieu-ferrante.github.io/OnlyBrief/apercu.html> → « Journal d'exécution » en bas de page.
- Une exécution en échec (aucune édition produite) apparaît en rouge et GitHub envoie un courriel ; aucune notification vide n'est envoyée.
- Une source en panne trois jours de suite est signalée dans les erreurs : remplacer son flux dans `sujets.yaml`.

### Réglages de batterie HyperOS (POCO M7 Pro 5G)

*Paramètres* → *Applications* → *Gérer les applications* → *OnlyBrief* :
**Démarrage automatique** activé, *Économiseur de batterie* → **Aucune restriction**.
Sans ces réglages, la notification peut arriver en retard ; l'édition est de toute façon téléchargée à l'ouverture.

### Publier et installer une nouvelle version de l'application

1. Mettre à jour le code, puis dans un terminal à la racine du dépôt :
   `git tag v1.0.1` puis `git push origin v1.0.1` (numéro toujours supérieur au précédent).
2. L'action « APK signé » construit et publie l'APK dans *Releases* ; l'écran Réglages de l'application signale la nouvelle version.
3. Sur le téléphone, télécharger l'APK depuis *Releases* et l'ouvrir : il s'installe par-dessus, l'historique est conservé.

**Recompiler à la main** (tiers ou nouveau poste) : installer Android Studio, ouvrir le dossier `app/`, puis
`gradlew assembleRelease` (Windows : `app\gradlew.bat assembleRelease`). Pour signer, créer `app/signature.properties`
(jamais commité) avec `magasin=<chemin du .jks>`, `motDePasseMagasin=…`, `alias=onlybrief`, `motDePasseCle=…`.
La clé de signature est la même pour toutes les versions : elle est sauvegardée en deux copies hors du poste.

---

## Développement sur son poste

**Installation** (une fois), à la racine du dépôt :

- Windows : `py -3.13 -m venv service\.venv` puis `service\.venv\Scripts\python -m pip install -e "service[dev]"`
- Mac : `python3 -m venv service/.venv` puis `service/.venv/bin/python -m pip install -e "service[dev]"`

**Clé Gemini** : créer à la racine du dépôt un fichier `.env` (ignoré par git, jamais publié) contenant
`GEMINI_API_KEY=ta-cle`.

**Commandes** (Windows : `service\.venv\Scripts\python -m onlybrief …` ; Mac : `service/.venv/bin/python -m onlybrief …`) :

| Commande | Effet |
| --- | --- |
| `edition` | prépare l'édition du jour dans `docs/` |
| `edition --sans-modele` | simule un modèle indisponible (résumés = chapôs RSS) |
| `alerte` | cherche une annonce majeure maintenant |
| `verifier-config` | vérifie `sujets.yaml` |

**Aperçu** : `python -m http.server 8000 --directory docs` puis <http://localhost:8000/apercu.html>.

**Tests** : `python -m pytest service` (service) ; dans `app/` : `gradlew testDebugUnitTest` (application).

# OnlyBrief

Veille quotidienne livrée sur Android : chaque matin, une édition courte organisée par sujet
(IA / LLM, tech générale, Counter-Strike / esport…), avec pour chaque actualité un résumé de deux
lignes en français et une ligne « Pourquoi c'est important ».

- `sujets.yaml` : les sujets suivis et leurs sources. **C'est le seul fichier à modifier pour changer la veille.**
- `service/` : le service Python qui collecte, filtre, fait résumer et publie l'édition.
- `docs/` : les fichiers publiés (éditions JSON, index, page `apercu.html`).
- `etat/` : la mémoire du service (liens déjà cités, dernière configuration valide).

Référence complète : [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md).

> Le modèle de langage est **Google Gemini** (offre gratuite, modèle Flash-Lite) : GitHub Models,
> prévu au cahier des charges, a été retiré par GitHub le 30 juillet 2026.

---

## Lancer le service sur son poste

### 1. Installation (une seule fois)

Il faut Python 3.12 ou plus récent. Ouvrir un terminal **à la racine du dépôt**.

**Windows (PowerShell)**

```powershell
py -3.13 -m venv service\.venv
service\.venv\Scripts\python -m pip install -e "service[dev]"
```

**Mac**

```bash
python3 -m venv service/.venv
service/.venv/bin/python -m pip install -e "service[dev]"
```

### 2. Clé Gemini (gratuite, jamais dans le dépôt)

1. Aller sur <https://aistudio.google.com/apikey> avec son compte Google, accepter les conditions
   et cliquer sur « Create API key ». Aucune carte bancaire n'est demandée.
2. Copier la clé et la donner au terminal **pour la session en cours seulement** :

   - Windows : `$env:GEMINI_API_KEY = "collez-la-cle-ici"`
   - Mac : `export GEMINI_API_KEY="collez-la-cle-ici"`

La clé ne doit jamais être écrite dans un fichier du dépôt (le dépôt est public).

### 3. Produire l'édition du jour

- Windows : `service\.venv\Scripts\python -m onlybrief edition`
- Mac : `service/.venv/bin/python -m onlybrief edition`

Le journal s'affiche dans le terminal. L'édition est écrite dans `docs/editions/AAAA-MM-JJ.json`
et `docs/index.json` est mis à jour. Relancer la commande le même jour reconstruit l'édition du jour.

Autres commandes utiles :

| Commande | Effet |
| --- | --- |
| `python -m onlybrief verifier-config` | vérifie `sujets.yaml` sans rien collecter |
| `python -m onlybrief edition --sans-modele` | simule un modèle indisponible (résumés = chapôs RSS) |

### 4. Voir l'édition dans le navigateur

- Windows : `service\.venv\Scripts\python -m http.server 8000 --directory docs`
- Mac : `service/.venv/bin/python -m http.server 8000 --directory docs`

Puis ouvrir <http://localhost:8000/apercu.html>. `Ctrl+C` dans le terminal arrête le serveur.

### 5. Tests automatiques

- Windows : `service\.venv\Scripts\python -m pytest service`
- Mac : `service/.venv/bin/python -m pytest service`

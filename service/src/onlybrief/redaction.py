"""Tri et rédaction des items par le modèle de langage (COL-07, COL-08, COL-13, CFG-05).

Un appel par sujet : le modèle reçoit les candidats, choisit les plus
importants (au plus `max_items`) et rédige pour chacun un résumé de deux
lignes et une ligne « Pourquoi c'est important », en français.

Le fournisseur est réglé dans `sujets.yaml` (bloc `modele`) ; la clé d'API est
lue dans une variable d'environnement, jamais dans un fichier du dépôt.
Si l'appel échoue, les items partent avec le chapô du flux RSS (COL-13).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field

import httpx

from .collecte import Article, texte_brut
from .config import Modele, Sujet

log = logging.getLogger(__name__)

FOURNISSEURS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1/", "GROQ_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1/", "MISTRAL_API_KEY"),
}

MAX_CANDIDATS = 40
LONGUEUR_EXTRAIT = 400
BUDGET_CARACTERES = 24_000     # ≈ 6 000 jetons d'entrée, sous la limite de 8 000 (section 9)
LONGUEUR_RESUME = 240
LONGUEUR_POURQUOI = 160
ESSAIS = 3
POURQUOI_DEGRADE = "Résumé automatique indisponible : extrait fourni par la source."

CONSIGNES_GENERALES = """\
Tu es le rédacteur d'une revue de presse quotidienne en français, nommée OnlyBrief.
On te donne des articles candidats pour la rubrique « {nom} ».

Ta tâche :
1. Choisis au plus {max_items} articles, les plus importants pour un lecteur qui suit ce sujet de près.
   Écarte la publicité, les bons plans, les tests de produits mineurs, les contenus hors sujet
   et les doublons (si plusieurs articles traitent du même fait, garde le plus complet).
   Il est permis de n'en choisir aucun si rien n'est notable.
2. Pour chaque article retenu, rédige en français, même si l'article est en anglais :
   - "resume" : deux lignes au maximum (moins de 240 caractères), factuel ;
   - "pourquoi" : une seule ligne (moins de 160 caractères) expliquant la portée de l'information.
3. N'utilise QUE les informations présentes dans le titre et l'extrait fournis.
   N'ajoute aucun fait, chiffre ou nom absent de l'article. Ne recopie pas l'extrait mot pour mot.
4. Classe les articles retenus du plus important au moins important.
{consignes}
Réponds uniquement par un objet JSON de la forme :
{{"items": [{{"n": <numéro du candidat>, "resume": "...", "pourquoi": "..."}}]}}
"""

SCHEMA_REPONSE = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "resume": {"type": "string"},
                    "pourquoi": {"type": "string"},
                },
                "required": ["n", "resume", "pourquoi"],
            },
        }
    },
    "required": ["items"],
}


class ModeleIndisponible(Exception):
    """Le modèle n'a pas pu produire une réponse exploitable."""


@dataclass
class ItemRedige:
    article: Article
    resume: str
    pourquoi: str


@dataclass
class ResultatRedaction:
    items: list[ItemRedige]
    degrade: bool
    requetes: int = 0
    erreur: str = ""
    non_retenus: int = 0


@dataclass
class ClientModele:
    """Client minimal pour une API compatible « chat completions »."""

    modele: Modele
    cle: str
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=httpx.Timeout(90.0, connect=15.0)))
    requetes: int = 0

    @classmethod
    def depuis_environnement(cls, modele: Modele) -> "ClientModele":
        if modele.fournisseur not in FOURNISSEURS:
            raise ModeleIndisponible(f"fournisseur inconnu : {modele.fournisseur}")
        variable = FOURNISSEURS[modele.fournisseur][1]
        cle = os.environ.get(variable, "").strip()
        if not cle:
            raise ModeleIndisponible(f"variable d'environnement {variable} absente")
        return cls(modele=modele, cle=cle)

    def completer(self, systeme: str, utilisateur: str) -> dict:
        url = FOURNISSEURS[self.modele.fournisseur][0] + "chat/completions"
        corps = {
            "model": self.modele.nom,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": systeme},
                {"role": "user", "content": utilisateur},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "edition", "schema": SCHEMA_REPONSE},
            },
        }
        derniere_erreur = ""
        for essai in range(1, ESSAIS + 1):
            self.requetes += 1
            try:
                reponse = self.client.post(url, json=corps, headers={"Authorization": f"Bearer {self.cle}"})
            except httpx.HTTPError as exc:
                derniere_erreur = f"{type(exc).__name__} : {exc}"
            else:
                if reponse.status_code == 200:
                    try:
                        contenu = reponse.json()["choices"][0]["message"]["content"]
                        return json.loads(_sans_balises_code(contenu))
                    except (KeyError, IndexError, TypeError, ValueError) as exc:
                        raise ModeleIndisponible(f"réponse illisible : {exc}") from exc
                derniere_erreur = f"HTTP {reponse.status_code} : {reponse.text[:300]}"
                if reponse.status_code not in (429, 500, 502, 503, 504):
                    break
            if essai < ESSAIS:
                attente = 20 * essai
                log.warning("Modèle : essai %d échoué (%s), nouvel essai dans %d s", essai, derniere_erreur, attente)
                time.sleep(attente)
        raise ModeleIndisponible(derniere_erreur)


def _sans_balises_code(texte: str) -> str:
    texte = texte.strip()
    if texte.startswith("```"):
        texte = texte.split("\n", 1)[1] if "\n" in texte else ""
        texte = texte.rsplit("```", 1)[0]
    return texte


def _par_recence(articles: list[Article]) -> list[Article]:
    return sorted(articles, key=lambda a: a.publie_le.timestamp() if a.publie_le else 0, reverse=True)


def preparer_candidats(articles: list[Article]) -> list[Article]:
    """Garde les candidats les plus récents dans la limite du budget d'entrée."""
    candidats, taille = [], 0
    for article in _par_recence(articles)[:MAX_CANDIDATS]:
        cout = len(article.titre) + min(len(article.chapo), LONGUEUR_EXTRAIT) + len(article.source) + 60
        if taille + cout > BUDGET_CARACTERES:
            break
        candidats.append(article)
        taille += cout
    return candidats


def construire_messages(sujet: Sujet, candidats: list[Article], deja_traites: list[str] = ()) -> tuple[str, str]:
    consignes = ""
    if sujet.consignes:
        consignes = f"\nConsignes particulières pour cette rubrique : {sujet.consignes}\n"
    if sujet.mots_cles:
        consignes += f"Mots-clés indicatifs de la rubrique : {', '.join(sujet.mots_cles)}.\n"
    if deja_traites:
        consignes += (
            "Faits déjà traités dans d'autres rubriques de l'édition (ne les reprends pas, même sous un autre titre) :\n"
            + "\n".join(f"- {titre}" for titre in deja_traites) + "\n"
        )
    consignes += "À importance comparable, varie les sources.\n"
    systeme = CONSIGNES_GENERALES.format(nom=sujet.nom, max_items=sujet.max_items, consignes=consignes)
    lignes = [
        {
            "n": i,
            "titre": a.titre,
            "source": a.source,
            "date": a.publie_le.isoformat() if a.publie_le else "",
            "extrait": texte_brut(a.chapo, LONGUEUR_EXTRAIT),
        }
        for i, a in enumerate(candidats, start=1)
    ]
    return systeme, json.dumps({"candidats": lignes}, ensure_ascii=False)


def _lire_reponse(reponse: dict, candidats: list[Article], max_items: int) -> list[ItemRedige]:
    items_bruts = reponse.get("items") if isinstance(reponse, dict) else None
    if not isinstance(items_bruts, list):
        raise ModeleIndisponible("réponse sans liste « items »")
    items, vus = [], set()
    for brut in items_bruts:
        if not isinstance(brut, dict):
            continue
        n = brut.get("n")
        resume = str(brut.get("resume") or "").strip()
        pourquoi = str(brut.get("pourquoi") or "").strip()
        if not isinstance(n, int) or not 1 <= n <= len(candidats) or n in vus or not resume or not pourquoi:
            log.warning("Item du modèle ignoré (incomplet ou numéro invalide) : %s", brut)
            continue
        vus.add(n)
        items.append(ItemRedige(
            article=candidats[n - 1],
            resume=texte_brut(resume, LONGUEUR_RESUME),
            pourquoi=texte_brut(pourquoi, LONGUEUR_POURQUOI),
        ))
        if len(items) == max_items:
            break
    if items_bruts and not items:
        raise ModeleIndisponible("aucun item exploitable dans la réponse")
    return items


def rediger_degrade(sujet: Sujet, articles: list[Article]) -> list[ItemRedige]:
    """Repli COL-13 : les plus récents, avec le chapô du flux comme résumé."""
    return [
        ItemRedige(
            article=a,
            resume=texte_brut(a.chapo, LONGUEUR_RESUME) or a.titre,
            pourquoi=POURQUOI_DEGRADE,
        )
        for a in _par_recence(articles)[: sujet.max_items]
    ]


def rediger(
    sujet: Sujet, articles: list[Article], client: ClientModele | None, deja_traites: list[str] = (),
) -> ResultatRedaction:
    """Choisit et rédige les items d'une section (COL-07, COL-08), avec repli (COL-13)."""
    if not articles:
        return ResultatRedaction(items=[], degrade=False)
    candidats = preparer_candidats(articles)
    if client is None:
        items = rediger_degrade(sujet, articles)
        return ResultatRedaction(items=items, degrade=True, non_retenus=len(articles) - len(items))
    avant = client.requetes
    try:
        systeme, utilisateur = construire_messages(sujet, candidats, deja_traites)
        items = _lire_reponse(client.completer(systeme, utilisateur), candidats, sujet.max_items)
    except ModeleIndisponible as exc:
        log.error("Modèle indisponible pour « %s » : %s — repli sur les chapôs RSS", sujet.nom, exc)
        items = rediger_degrade(sujet, articles)
        return ResultatRedaction(items=items, degrade=True, requetes=client.requetes - avant,
                                 erreur=str(exc), non_retenus=len(articles) - len(items))
    return ResultatRedaction(items=items, degrade=False, requetes=client.requetes - avant,
                             non_retenus=len(articles) - len(items))

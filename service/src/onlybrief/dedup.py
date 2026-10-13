"""Déduplication des articles et mémoire des liens déjà cités (COL-06).

L'état est conservé dans `etat/liens_cites.json` : chaque lien publié y est
noté avec la date de l'édition qui l'a cité. Un lien cité dans les 14
derniers jours n'est pas repris.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .collecte import Article
from .filtres import normaliser

log = logging.getLogger(__name__)

DUREE_MEMOIRE = timedelta(days=14)
_PARAMETRES_SUIVI = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "xtor", "at_medium", "at_campaign")


def normaliser_lien(lien: str) -> str:
    """Forme canonique d'un lien : https, sans « www. », sans paramètres de suivi ni ancre."""
    morceaux = urlsplit(lien.strip())
    hote = morceaux.netloc.lower().removeprefix("www.")
    requete = [
        (k, v) for k, v in parse_qsl(morceaux.query, keep_blank_values=True)
        if not k.lower().startswith(_PARAMETRES_SUIVI)
    ]
    chemin = morceaux.path.rstrip("/") or "/"
    return urlunsplit(("https", hote, chemin, urlencode(requete), ""))


def dedoublonner(articles: list[Article]) -> tuple[list[Article], int]:
    """Supprime les doublons stricts : même lien, ou même titre (sources différentes).

    Le premier article rencontré est gardé ; les sources des doublons de titre
    sont ajoutées à `autres_sources`. Renvoie (articles gardés, nombre écartés).
    """
    par_lien: dict[str, Article] = {}
    par_titre: dict[str, Article] = {}
    gardes: list[Article] = []
    ecartes = 0
    for article in articles:
        cle_lien = normaliser_lien(article.lien)
        cle_titre = normaliser(article.titre)
        deja = par_lien.get(cle_lien) or par_titre.get(cle_titre)
        if deja is not None:
            if article.source != deja.source and article.source not in deja.autres_sources:
                deja.autres_sources.append(article.source)
            ecartes += 1
            continue
        par_lien[cle_lien] = article
        par_titre[cle_titre] = article
        gardes.append(article)
    return gardes, ecartes


class LiensCites:
    """Mémoire des liens publiés, persistée en JSON."""

    def __init__(self, chemin: Path):
        self.chemin = chemin
        self.liens: dict[str, str] = {}
        if chemin.exists():
            try:
                donnees = json.loads(chemin.read_text(encoding="utf-8"))
                self.liens = dict(donnees.get("liens", {}))
            except (OSError, ValueError) as exc:
                log.error("État des liens illisible (%s) : il est réinitialisé", exc)

    def deja_cite(self, lien: str, jour: date) -> bool:
        """Vrai si le lien a été cité dans une édition des 14 jours précédant `jour`.

        Les liens notés à la date `jour` elle-même sont ignorés : relancer
        l'édition du jour la reconstruit au lieu de la vider.
        """
        cite_le = self.liens.get(normaliser_lien(lien))
        if cite_le is None:
            return False
        cite = date.fromisoformat(cite_le)
        return jour - DUREE_MEMOIRE <= cite < jour

    def filtrer(self, articles: list[Article], jour: date) -> tuple[list[Article], int]:
        gardes = [a for a in articles if not self.deja_cite(a.lien, jour)]
        return gardes, len(articles) - len(gardes)

    def enregistrer(self, liens: list[str], jour: date) -> None:
        """Note les liens publiés le jour donné et oublie ceux de plus de 14 jours."""
        for cle in [k for k, v in self.liens.items() if v == jour.isoformat()]:
            del self.liens[cle]  # l'édition du jour est réécrite en entier
        for lien in liens:
            self.liens[normaliser_lien(lien)] = jour.isoformat()
        limite = jour - DUREE_MEMOIRE
        self.liens = {k: v for k, v in self.liens.items() if date.fromisoformat(v) >= limite}

    def sauvegarder(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        contenu = {"liens": dict(sorted(self.liens.items(), key=lambda kv: (kv[1], kv[0])))}
        self.chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

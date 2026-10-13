"""Filtrage des articles collectés (COL-03, COL-04)."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from .collecte import Article
from .config import Sujet


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, espaces simples : « Modèle  IA » → « modele ia »."""
    decompose = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sans_accents.casefold()).strip()


def contient(texte: str, mot_cle: str) -> bool:
    """Le mot-clé apparaît-il comme mot entier (ou expression entière) dans le texte ?

    Insensible à la casse et aux accents : « transfert » trouve « Transfert »,
    « IA générative » trouve « ia generative », mais « patch » ne trouve pas
    « dispatcher ».
    """
    cle = normaliser(mot_cle)
    if not cle:
        return False
    motif = r"(?<![\w])" + re.escape(cle) + r"(?![\w])"
    return re.search(motif, normaliser(texte)) is not None


def contient_un(texte: str, mots_cles) -> str | None:
    """Renvoie le premier mot-clé trouvé, ou None."""
    for mot in mots_cles:
        if contient(texte, mot):
            return mot
    return None


@dataclass
class ResultatFiltrage:
    retenus: list[Article]
    ecartes: Counter = field(default_factory=Counter)


def filtrer(articles: list[Article], sujet: Sujet, depuis: datetime) -> ResultatFiltrage:
    """Applique au sujet les règles de date et de mots-clés.

    - COL-03 : seuls les articles publiés après `depuis` sont gardés
      (un article sans date est écarté, faute de pouvoir le situer) ;
    - COL-04 : un mot-clé d'exclusion écarte l'article ; pour une source
      `mots_cles_obligatoires`, l'article doit contenir un mot-clé du sujet.
    """
    resultat = ResultatFiltrage(retenus=[])
    for article in articles:
        if article.sujet_id != sujet.id:
            continue
        if article.publie_le is None:
            resultat.ecartes["sans date"] += 1
            continue
        if article.publie_le <= depuis:
            resultat.ecartes["antérieur à l'édition précédente"] += 1
            continue
        texte = f"{article.titre} {article.chapo}"
        if contient_un(texte, sujet.exclusions):
            resultat.ecartes["mot-clé d'exclusion"] += 1
            continue
        if article.mots_cles_obligatoires and sujet.mots_cles and not contient_un(texte, sujet.mots_cles):
            resultat.ecartes["hors mots-clés (source filtrée)"] += 1
            continue
        resultat.retenus.append(article)
    return resultat

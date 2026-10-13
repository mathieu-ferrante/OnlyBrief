"""Collecte des flux RSS / Atom (COL-02, COL-10)."""

from __future__ import annotations

import calendar
import html
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import feedparser
import httpx

from .config import Source, Sujet

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; OnlyBrief/0.1; +https://github.com/mathieu-ferrante/OnlyBrief)"
DELAI = httpx.Timeout(20.0, connect=10.0)
LONGUEUR_CHAPO = 600


@dataclass
class Article:
    sujet_id: str
    source: str
    titre: str
    lien: str
    publie_le: datetime | None
    chapo: str = ""
    mots_cles_obligatoires: bool = False
    autres_sources: list[str] = field(default_factory=list)


@dataclass
class ResultatCollecte:
    articles: list[Article]
    sources_lues: list[str]
    sources_en_echec: list[str]
    erreurs: dict[str, str]


_BALISES = re.compile(r"<[^>]+>")
_ESPACES = re.compile(r"\s+")


def texte_brut(fragment: str, longueur: int = LONGUEUR_CHAPO) -> str:
    """Retire le HTML d'un chapô RSS et le tronque proprement."""
    texte = _ESPACES.sub(" ", html.unescape(_BALISES.sub(" ", fragment or ""))).strip()
    if len(texte) <= longueur:
        return texte
    coupe = texte[:longueur].rsplit(" ", 1)[0]
    return coupe.rstrip(" ,;:.") + "…"


def _date_entree(entree) -> datetime | None:
    for cle in ("published_parsed", "updated_parsed", "created_parsed"):
        valeur = entree.get(cle)
        if valeur:
            return datetime.fromtimestamp(calendar.timegm(valeur), tz=timezone.utc)
    return None


def analyser_flux(contenu: bytes, sujet: Sujet, source: Source) -> list[Article]:
    """Transforme le contenu brut d'un flux en articles."""
    flux = feedparser.parse(contenu)
    if flux.bozo and not flux.entries:
        raise ValueError(f"flux illisible ({flux.get('bozo_exception', 'format inconnu')})")
    articles = []
    for entree in flux.entries:
        titre = texte_brut(entree.get("title", ""), 300)
        lien = (entree.get("link") or "").strip()
        if not titre or not lien.startswith(("https://", "http://")):
            continue
        resume = entree.get("summary") or ""
        if not resume and entree.get("content"):
            resume = entree["content"][0].get("value", "")
        articles.append(Article(
            sujet_id=sujet.id,
            source=source.nom,
            titre=titre,
            lien=lien,
            publie_le=_date_entree(entree),
            chapo=texte_brut(resume),
            mots_cles_obligatoires=source.mots_cles_obligatoires,
        ))
    return articles


def lire_source(client: httpx.Client, sujet: Sujet, source: Source) -> list[Article]:
    reponse = client.get(source.flux)
    reponse.raise_for_status()
    return analyser_flux(reponse.content, sujet, source)


def collecter(sujets: list[Sujet], client: httpx.Client | None = None) -> ResultatCollecte:
    """Lit toutes les sources des sujets. Une source en échec ne bloque rien (COL-10)."""
    proprietaire = client is None
    client = client or httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=DELAI, follow_redirects=True
    )
    resultat = ResultatCollecte([], [], [], {})
    try:
        for sujet in sujets:
            for source in sujet.sources:
                cle = f"{sujet.id}/{source.nom}"
                try:
                    articles = lire_source(client, sujet, source)
                except Exception as exc:  # toute panne de source est tolérée
                    message = f"{type(exc).__name__} : {exc}"
                    log.warning("Source injoignable [%s] %s — %s", sujet.id, source.nom, message)
                    resultat.sources_en_echec.append(cle)
                    resultat.erreurs[cle] = message
                    continue
                log.info("Source lue [%s] %s : %d article(s)", sujet.id, source.nom, len(articles))
                resultat.sources_lues.append(cle)
                resultat.articles.extend(articles)
    finally:
        if proprietaire:
            client.close()
    return resultat

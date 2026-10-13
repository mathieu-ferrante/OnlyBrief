"""Outils communs aux tests."""

from datetime import datetime, timezone

import pytest

from onlybrief.collecte import Article
from onlybrief.config import Source, Sujet


@pytest.fixture
def sujet_cs2():
    return Sujet(
        id="cs2", nom="Counter-Strike / esport", ordre=3, max_items=2,
        mots_cles=("CS2", "Counter-Strike", "Major", "transfert"),
        exclusions=("skin", "case opening"),
        consignes="ignorer les compétitions en dessous du tier 2",
        sources=(Source("HLTV.org", "https://www.hltv.org/rss/news"),
                 Source("Dexerto.fr", "https://www.dexerto.fr/feed/", mots_cles_obligatoires=True)),
    )


def fabriquer_article(titre="Titre", lien="https://exemple.fr/a", source="HLTV.org", sujet_id="cs2",
                      publie_le=datetime(2026, 10, 13, 6, 0, tzinfo=timezone.utc), chapo="", obligatoires=False):
    return Article(sujet_id=sujet_id, source=source, titre=titre, lien=lien, publie_le=publie_le,
                   chapo=chapo, mots_cles_obligatoires=obligatoires)


@pytest.fixture
def article():
    return fabriquer_article

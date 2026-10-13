"""Filtrage par date et par mots-clés (COL-03, COL-04)."""

from datetime import datetime, timezone

import pytest

from onlybrief.filtres import contient, filtrer, normaliser

DEPUIS = datetime(2026, 10, 12, 5, 30, tzinfo=timezone.utc)


def test_normaliser_accents_et_casse():
    assert normaliser("  Modèle   de LANGAGE ") == "modele de langage"


@pytest.mark.parametrize("texte, mot, attendu", [
    ("Un nouveau Transfert chez Vitality", "transfert", True),
    ("IA generative : la France investit", "IA générative", True),
    ("Le dispatcher plante", "patch", False),
    ("Patch 1.2 de CS2 disponible", "patch", True),
    ("GPT-6 annoncé", "GPT", True),
    ("Les skins les plus chers", "skin", False),   # mot entier : « skins » ≠ « skin »
    ("Un skin rare", "skin", True),
    ("", "CS2", False),
])
def test_contient_mot_entier(texte, mot, attendu):
    assert contient(texte, mot) is attendu


def test_col03_articles_anterieurs_ou_sans_date_ecartes(sujet_cs2, article):
    articles = [
        article(titre="Récent", publie_le=datetime(2026, 10, 12, 20, 0, tzinfo=timezone.utc)),
        article(titre="Ancien", publie_le=datetime(2026, 10, 11, 20, 0, tzinfo=timezone.utc)),
        article(titre="Pile à la limite", publie_le=DEPUIS),
        article(titre="Sans date", publie_le=None),
    ]
    resultat = filtrer(articles, sujet_cs2, DEPUIS)
    assert [a.titre for a in resultat.retenus] == ["Récent"]
    assert resultat.ecartes["sans date"] == 1
    assert resultat.ecartes["antérieur à l'édition précédente"] == 2


def test_col04_exclusions(sujet_cs2, article):
    articles = [
        article(titre="Vitality gagne le Major"),
        article(titre="Ouverture de caisse", chapo="Notre meilleur case opening de la semaine"),
        article(titre="Un SKIN à 1 million"),
    ]
    resultat = filtrer(articles, sujet_cs2, DEPUIS)
    assert [a.titre for a in resultat.retenus] == ["Vitality gagne le Major"]
    assert resultat.ecartes["mot-clé d'exclusion"] == 2


def test_col04_mots_cles_obligatoires_seulement_pour_la_source_marquee(sujet_cs2, article):
    articles = [
        article(titre="Fortnite : nouvelle saison", source="Dexerto.fr", obligatoires=True),
        article(titre="Counter-Strike : la Team Vitality recrute", source="Dexerto.fr", obligatoires=True),
        article(titre="Interview d'un coach", source="HLTV.org"),
    ]
    resultat = filtrer(articles, sujet_cs2, DEPUIS)
    assert [a.titre for a in resultat.retenus] == ["Counter-Strike : la Team Vitality recrute", "Interview d'un coach"]
    assert resultat.ecartes["hors mots-clés (source filtrée)"] == 1


def test_filtre_ne_prend_que_le_sujet_demande(sujet_cs2, article):
    resultat = filtrer([article(sujet_id="ia")], sujet_cs2, DEPUIS)
    assert resultat.retenus == []

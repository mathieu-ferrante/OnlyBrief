"""Chaîne complète d'une édition, sources et modèle simulés (COL-03, COL-06, COL-09, COL-10, COL-13, ALR-02)."""

import json
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from onlybrief import edition as module_edition
from onlybrief.collecte import ResultatCollecte
from onlybrief.edition import Chemins, EditionImpossible, preparer_edition

RACINE = Path(__file__).resolve().parents[2]
JOUR = date(2026, 10, 13)
PUBLICATION = datetime.fromisoformat("2026-10-13T07:30:00+02:00")


@pytest.fixture
def depot(tmp_path):
    shutil.copy(RACINE / "sujets.yaml", tmp_path / "sujets.yaml")
    return Chemins(tmp_path)


def simuler_collecte(monkeypatch, article, liens):
    recent = datetime(2026, 10, 13, 3, 0, tzinfo=timezone.utc)
    articles = [article(titre=f"Article {lien}", lien=f"https://exemple.fr/{lien}", source="The Decoder",
                        sujet_id="ia", publie_le=recent - timedelta(minutes=i)) for i, lien in enumerate(liens)]
    articles.append(article(titre="Vieux", lien="https://exemple.fr/vieux", sujet_id="ia",
                            publie_le=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    resultat = ResultatCollecte(articles=articles, sources_lues=["ia/The Decoder"],
                                sources_en_echec=["cs2/HLTV.org"], erreurs={"cs2/HLTV.org": "HTTP 503"})
    monkeypatch.setattr(module_edition, "collecter", lambda sujets: resultat)


def test_edition_complete_en_mode_degrade(depot, monkeypatch, article):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    simuler_collecte(monkeypatch, article, ["a", "b"])
    chemin = preparer_edition(depot, jour=JOUR, publiee_le=PUBLICATION, planifiee=True)
    contenu = json.loads(chemin.read_text(encoding="utf-8"))

    assert contenu["publiee_le"] == "2026-10-13T07:30:00+02:00"
    assert contenu["resumes_degrades"] is True, "COL-13 : le mode dégradé est signalé"
    assert [s["sujet_id"] for s in contenu["sections"]] == ["ia", "tech", "cs2"]
    ia, tech, cs2 = contenu["sections"]
    assert [i["lien"] for i in ia["items"]] == ["https://exemple.fr/a", "https://exemple.fr/b"]
    assert tech["items"] == [], "APP-05 : section vide conservée"
    assert cs2["sources_en_echec"] == ["HLTV.org"], "COL-10"
    assert contenu["journal"]["planifiee"] is True
    assert any("GEMINI_API_KEY" in e for e in contenu["journal"]["erreurs"])
    index = json.loads((depot.docs / "index.json").read_text(encoding="utf-8"))
    assert index["editions"][0]["date"] == "2026-10-13"


def test_le_lendemain_les_liens_deja_cites_sont_ecartes(depot, monkeypatch, article):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    simuler_collecte(monkeypatch, article, ["a", "b"])
    preparer_edition(depot, jour=JOUR, publiee_le=PUBLICATION)
    simuler_collecte(monkeypatch, article, ["a", "c"])
    monkeypatch.setattr(module_edition, "debut_collecte", lambda docs, jour: datetime(2026, 10, 12, tzinfo=timezone.utc))
    chemin = preparer_edition(depot, jour=date(2026, 10, 14), publiee_le=PUBLICATION + timedelta(days=1))
    ia = json.loads(chemin.read_text(encoding="utf-8"))["sections"][0]
    assert [i["lien"] for i in ia["items"]] == ["https://exemple.fr/c"], "COL-06"


def test_alr02_alerte_en_tete_de_section(depot, monkeypatch, article):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    simuler_collecte(monkeypatch, article, ["a", "alerte"])
    alerte = {"date": "2026-10-12", "emise_le": "2026-10-12T15:00:00+02:00", "sujet_id": "ia",
              "item": {"id": "alerte-2026-10-12", "titre": "Annonce majeure", "resume": "R.", "pourquoi": "P.",
                       "source": "OpenAI News", "lien": "https://exemple.fr/alerte",
                       "publie_le": "2026-10-12T14:40:00+02:00", "autres_sources": []}}
    (depot.docs / "alertes").mkdir(parents=True)
    (depot.docs / "alertes" / "2026-10-12.json").write_text(json.dumps(alerte), encoding="utf-8")
    (depot.docs / "index.json").write_text(json.dumps({"mis_a_jour_le": "", "editions": [],
        "derniere_alerte": {"date": "2026-10-12", "fichier": "alertes/2026-10-12.json"}}), encoding="utf-8")

    chemin = preparer_edition(depot, jour=JOUR, publiee_le=PUBLICATION)
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    items = contenu["sections"][0]["items"]
    assert items[0]["titre"] == "Annonce majeure" and items[0]["deja_signale"] is True
    assert [i["lien"] for i in items].count("https://exemple.fr/alerte") == 1, "pas de doublon avec l'article collecté"
    assert all(not i["deja_signale"] for i in items[1:])
    assert json.loads((depot.docs / "index.json").read_text(encoding="utf-8"))["derniere_alerte"]["date"] == "2026-10-12"


def test_not07_aucune_source_lue_aucune_edition(depot, monkeypatch):
    monkeypatch.setattr(module_edition, "collecter",
                        lambda sujets: ResultatCollecte([], [], ["ia/A"], {"ia/A": "panne"}))
    with pytest.raises(EditionImpossible):
        preparer_edition(depot, jour=JOUR, publiee_le=PUBLICATION)
    assert not (depot.docs / "editions" / "2026-10-13.json").exists()


def test_cfg03_config_cassee_derniere_valide_reprise(depot, monkeypatch, article):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    simuler_collecte(monkeypatch, article, ["a"])
    preparer_edition(depot, jour=JOUR, publiee_le=PUBLICATION)        # mémorise la config valide
    depot.sujets.write_text("sujets: [cassé", encoding="utf-8")
    chemin = preparer_edition(depot, jour=JOUR, publiee_le=PUBLICATION)
    journal = json.loads(chemin.read_text(encoding="utf-8"))["journal"]
    assert journal["configuration"] == "dernière configuration valide reprise"
    assert any("sujets.yaml" in e for e in journal["erreurs"])

"""Format de l'édition et de l'index, purge à 60 jours (COL-09, section 7)."""

import json
from datetime import date, datetime, timezone

from onlybrief.config import Source, Sujet
from onlybrief.publication import Section, construire_edition, edition_precedente, publier
from onlybrief.redaction import ItemRedige

MAINTENANT = datetime(2026, 10, 13, 5, 30, tzinfo=timezone.utc)
SUJET_IA = Sujet(id="ia", nom="IA / LLM", ordre=1, max_items=5, sources=(Source("S", "https://s.fr"),))
SUJET_TECH = Sujet(id="tech", nom="Tech générale", ordre=2, max_items=5, sources=(Source("S", "https://s.fr"),))


def edition(article, jour=date(2026, 10, 13)):
    a = article(titre="Titre", lien="https://openai.com/x", source="OpenAI News", sujet_id="ia",
                publie_le=datetime(2026, 10, 12, 16, 4, tzinfo=timezone.utc))
    a.autres_sources.append("The Decoder")
    sections = [
        Section(SUJET_IA, [ItemRedige(a, "Deux lignes.", "Une ligne.")], []),
        Section(SUJET_TECH, [], ["Numerama"]),
    ]
    return construire_edition(jour, MAINTENANT, sections, False, {"erreurs": []})


def test_format_section_7_2(article):
    e = edition(article)
    assert e["date"] == "2026-10-13"
    assert e["publiee_le"] == "2026-10-13T07:30:00+02:00"
    assert e["nb_items"] == 1 and e["resumes_degrades"] is False
    ia, tech = e["sections"]
    assert ia["sujet_id"] == "ia" and ia["nom"] == "IA / LLM" and ia["sources_en_echec"] == []
    assert ia["items"][0] == {
        "id": "ia-2026-10-13-01",
        "titre": "Titre",
        "resume": "Deux lignes.",
        "pourquoi": "Une ligne.",
        "deja_signale": False,
        "source": "OpenAI News",
        "lien": "https://openai.com/x",
        "publie_le": "2026-10-12T18:04:00+02:00",
        "autres_sources": ["The Decoder"],
    }
    assert tech["items"] == [] and tech["sources_en_echec"] == ["Numerama"], "APP-05 : la section vide reste"


def test_col09_publication_index_et_purge(tmp_path, article):
    docs = tmp_path / "docs"
    vieille = docs / "editions" / "2026-08-01.json"
    vieille.parent.mkdir(parents=True)
    vieille.write_text("{}", encoding="utf-8")
    (docs / "index.json").write_text(json.dumps({
        "mis_a_jour_le": "", "editions": [{"date": "2026-08-01", "nb_items": 3, "fichier": "editions/2026-08-01.json"}],
        "derniere_alerte": {"date": "2026-10-12", "fichier": "alertes/2026-10-12.json"},
    }), encoding="utf-8")

    publier(docs, edition(article, date(2026, 10, 12)), MAINTENANT)
    publier(docs, edition(article, date(2026, 10, 13)), MAINTENANT)
    publier(docs, edition(article, date(2026, 10, 13)), MAINTENANT)   # relance : pas de doublon

    index = json.loads((docs / "index.json").read_text(encoding="utf-8"))
    assert [e["date"] for e in index["editions"]] == ["2026-10-13", "2026-10-12"], "la plus récente en haut"
    assert index["editions"][0] == {"date": "2026-10-13", "nb_items": 1, "fichier": "editions/2026-10-13.json"}
    assert index["derniere_alerte"]["date"] == "2026-10-12", "l'alerte est conservée"
    assert index["mis_a_jour_le"] == "2026-10-13T07:30:00+02:00"
    assert not vieille.exists(), "édition de plus de 60 jours supprimée"


def test_edition_precedente(tmp_path, article):
    docs = tmp_path / "docs"
    publier(docs, edition(article, date(2026, 10, 12)), MAINTENANT)
    publier(docs, edition(article, date(2026, 10, 13)), MAINTENANT)
    assert edition_precedente(docs, date(2026, 10, 13))["date"] == "2026-10-12"
    assert edition_precedente(docs, date(2026, 10, 12)) is None

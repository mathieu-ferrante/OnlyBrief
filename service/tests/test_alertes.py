"""Alertes en journée et reprise dans l'édition suivante (ALR-01, ALR-02)."""

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from onlybrief.alertes import alerte_a_reprendre, declencheurs, examiner_sujet
from onlybrief.config import Source, Sujet
from onlybrief.edition import item_depuis_alerte, suivre_echecs

INSTANT = datetime(2026, 10, 13, 13, 0, tzinfo=timezone.utc)
JOUR = date(2026, 10, 13)

SUJET = Sujet(id="ia", nom="IA / LLM", ordre=1, max_items=5, mots_cles_alerte=("nouveau modèle", "GPT"),
              sources=(Source("A", "https://a.fr"),))


class ModeleFactice:
    def __init__(self, reponse):
        self.reponse = reponse
        self.appels = []
        self.requetes = 0

    def completer(self, systeme, utilisateur, schema=None):
        self.requetes += 1
        self.appels.append((systeme, json.loads(utilisateur)))
        return self.reponse


@pytest.fixture
def recents(article):
    def fabriquer(*specs):
        return [article(titre=t, source=s, lien=f"https://{s.lower()}.fr/{i}", sujet_id="ia",
                        publie_le=INSTANT - timedelta(minutes=10 * i))
                for i, (t, s) in enumerate(specs, start=1)]
    return fabriquer


def test_alr01_declencheurs(recents):
    arts = recents(("OpenAI lance GPT-7", "A"), ("Une info", "B"), ("Autre", "B"))
    mots, nb = declencheurs(SUJET, arts)
    assert mots == ["GPT"] and nb == 2


def test_alr01_mot_cle_et_confirmation_du_modele(recents):
    arts = recents(("OpenAI lance GPT-7", "OpenAI News"), ("Billet sans rapport", "Blog"))
    modele = ModeleFactice({"alerte": True, "n": 1, "meme_fait": [], "resume": "Résumé.", "pourquoi": "Portée."})
    alerte = examiner_sujet(SUJET, arts, modele, JOUR, INSTANT)
    assert alerte["date"] == "2026-10-13" and alerte["sujet_id"] == "ia"
    assert alerte["emise_le"] == "2026-10-13T15:00:00+02:00"
    assert set(alerte["item"]) == {"id", "titre", "resume", "pourquoi", "source", "lien", "publie_le", "autres_sources"}
    assert alerte["item"]["id"] == "alerte-2026-10-13" and alerte["item"]["titre"] == "OpenAI lance GPT-7"


def test_alr01_trois_sources_sur_le_meme_fait(recents):
    arts = recents(("Panne mondiale du cloud", "A"), ("Le cloud en panne", "B"), ("Panne géante", "C"))
    modele = ModeleFactice({"alerte": True, "n": 2, "meme_fait": [1, 3], "resume": "R.", "pourquoi": "P."})
    alerte = examiner_sujet(SUJET, arts, modele, JOUR, INSTANT)
    assert alerte["item"]["source"] == "B" and alerte["item"]["autres_sources"] == ["A", "C"]


def test_alr01_deux_sources_sans_mot_cle_refuse(recents):
    arts = recents(("Panne du cloud", "A"), ("Le cloud en panne", "B"), ("Autre chose", "C"))
    modele = ModeleFactice({"alerte": True, "n": 1, "meme_fait": [2], "resume": "R.", "pourquoi": "P."})
    assert examiner_sujet(SUJET, arts, modele, JOUR, INSTANT) is None


def test_alr01_le_modele_ne_confirme_pas(recents):
    arts = recents(("OpenAI lance GPT-7", "A"))
    assert examiner_sujet(SUJET, arts, ModeleFactice({"alerte": False}), JOUR, INSTANT) is None


def test_alr01_reponse_incoherente(recents):
    arts = recents(("OpenAI lance GPT-7", "A"))
    assert examiner_sujet(SUJET, arts, ModeleFactice({"alerte": True, "n": 9}), JOUR, INSTANT) is None


def _publier_alerte(docs, emise_le):
    (docs / "alertes").mkdir(parents=True)
    (docs / "alertes" / "2026-10-13.json").write_text(json.dumps({
        "date": "2026-10-13", "emise_le": emise_le, "sujet_id": "ia",
        "item": {"id": "alerte-2026-10-13", "titre": "GPT-7", "resume": "R", "pourquoi": "P", "source": "A",
                 "lien": "https://a.fr/1", "publie_le": "2026-10-13T14:50:00+02:00", "autres_sources": ["B"]},
    }), encoding="utf-8")
    (docs / "index.json").write_text(json.dumps({
        "mis_a_jour_le": "", "editions": [],
        "derniere_alerte": {"date": "2026-10-13", "fichier": "alertes/2026-10-13.json"},
    }), encoding="utf-8")


def test_alr02_alerte_reprise_dans_l_edition_suivante(tmp_path):
    docs = tmp_path / "docs"
    _publier_alerte(docs, "2026-10-13T15:00:00+02:00")
    alerte = alerte_a_reprendre(docs, datetime.fromisoformat("2026-10-13T06:45:00+02:00"))
    item = item_depuis_alerte(alerte)
    assert item.deja_signale is True
    assert item.article.titre == "GPT-7" and item.article.autres_sources == ["B"]


def test_alr02_alerte_deja_reprise_n_est_pas_repetee(tmp_path):
    docs = tmp_path / "docs"
    _publier_alerte(docs, "2026-10-13T15:00:00+02:00")
    assert alerte_a_reprendre(docs, datetime.fromisoformat("2026-10-14T06:45:00+02:00")) is None


def test_source_en_echec_trois_jours_de_suite(tmp_path):
    chemin = tmp_path / "echecs.json"
    assert suivre_echecs(chemin, ["cs2/Steam"], date(2026, 10, 13)) == []
    assert suivre_echecs(chemin, ["cs2/Steam"], date(2026, 10, 13)) == [], "relance du même jour : pas compté deux fois"
    assert suivre_echecs(chemin, ["cs2/Steam"], date(2026, 10, 14)) == []
    assert suivre_echecs(chemin, ["cs2/Steam"], date(2026, 10, 15)) == ["cs2/Steam"]
    assert suivre_echecs(chemin, [], date(2026, 10, 16)) == []
    assert suivre_echecs(chemin, ["cs2/Steam"], date(2026, 10, 17)) == [], "le compteur repart après un succès"

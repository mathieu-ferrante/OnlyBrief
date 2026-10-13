"""Tri et rédaction par le modèle, avec repli sur le chapô RSS (COL-07, COL-08, COL-13)."""

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from onlybrief.config import Modele
from onlybrief.redaction import (
    POURQUOI_DEGRADE, ClientModele, ModeleIndisponible, construire_messages, preparer_candidats, rediger,
)

MODELE = Modele(fournisseur="gemini", nom="gemini-3.5-flash-lite")


def client_simule(reponses):
    """Client dont l'API renvoie successivement les réponses données (statut, corps)."""
    appels = []
    reponses = list(reponses)

    def traiter(requete: httpx.Request) -> httpx.Response:
        appels.append(json.loads(requete.content))
        statut, corps = reponses.pop(0)
        if isinstance(corps, dict):
            corps = {"choices": [{"message": {"content": json.dumps(corps, ensure_ascii=False)}}]}
            return httpx.Response(statut, json=corps)
        return httpx.Response(statut, text=corps)

    client = ClientModele(modele=MODELE, cle="cle-de-test", client=httpx.Client(transport=httpx.MockTransport(traiter)))
    return client, appels


@pytest.fixture
def candidats(article):
    base = datetime(2026, 10, 13, 6, 0, tzinfo=timezone.utc)
    return [article(titre=f"Article {i}", lien=f"https://exemple.fr/{i}", chapo=f"Chapô de l'article {i}.",
                    publie_le=base - timedelta(hours=i)) for i in range(1, 6)]


def test_col08_items_rediges_dans_l_ordre_du_modele(sujet_cs2, candidats):
    client, appels = client_simule([(200, {"items": [
        {"n": 3, "resume": "Résumé trois.", "pourquoi": "Important car trois."},
        {"n": 1, "resume": "Résumé un.", "pourquoi": "Important car un."},
    ]})])
    resultat = rediger(sujet_cs2, candidats, client)
    assert not resultat.degrade
    assert [i.article.titre for i in resultat.items] == ["Article 3", "Article 1"]
    assert resultat.items[0].resume == "Résumé trois." and resultat.requetes == 1
    assert appels[0]["model"] == "gemini-3.5-flash-lite"


def test_cfg05_consignes_transmises_au_modele(sujet_cs2, candidats):
    systeme, utilisateur = construire_messages(sujet_cs2, candidats)
    assert "tier 2" in systeme
    assert "au plus 2 articles" in systeme
    assert "N'ajoute aucun fait" in systeme
    assert json.loads(utilisateur)["candidats"][0]["n"] == 1


def test_col07_plafond_max_items_meme_si_le_modele_en_renvoie_trop(sujet_cs2, candidats):
    client, _ = client_simule([(200, {"items": [
        {"n": n, "resume": "R", "pourquoi": "P"} for n in (1, 2, 3, 4)
    ]})])
    assert len(rediger(sujet_cs2, candidats, client).items) == sujet_cs2.max_items


def test_items_invalides_ignores(sujet_cs2, candidats):
    client, _ = client_simule([(200, {"items": [
        {"n": 99, "resume": "hors liste", "pourquoi": "P"},
        {"n": 2, "resume": "", "pourquoi": "P"},
        {"n": 4, "resume": "Valide", "pourquoi": "P"},
        {"n": 4, "resume": "Doublon", "pourquoi": "P"},
    ]})])
    items = rediger(sujet_cs2, candidats, client).items
    assert [(i.article.titre, i.resume) for i in items] == [("Article 4", "Valide")]


def test_le_modele_peut_ne_rien_retenir(sujet_cs2, candidats):
    client, _ = client_simule([(200, {"items": []})])
    resultat = rediger(sujet_cs2, candidats, client)
    assert resultat.items == [] and not resultat.degrade


def test_col13_repli_sur_le_chapo_si_le_modele_echoue(sujet_cs2, candidats):
    client, _ = client_simule([(400, "modèle inconnu")])
    resultat = rediger(sujet_cs2, candidats, client)
    assert resultat.degrade and "400" in resultat.erreur
    assert [i.article.titre for i in resultat.items] == ["Article 1", "Article 2"], "les plus récents"
    assert resultat.items[0].resume == "Chapô de l'article 1."
    assert resultat.items[0].pourquoi == POURQUOI_DEGRADE


def test_col13_quota_atteint_nouvel_essai_puis_repli(sujet_cs2, candidats, monkeypatch):
    monkeypatch.setattr("onlybrief.redaction.time.sleep", lambda s: None)
    client, appels = client_simule([(429, "quota"), (429, "quota"), (429, "quota")])
    resultat = rediger(sujet_cs2, candidats, client)
    assert resultat.degrade and len(appels) == 3 and resultat.requetes == 3


def test_quota_momentane_puis_succes(sujet_cs2, candidats, monkeypatch):
    monkeypatch.setattr("onlybrief.redaction.time.sleep", lambda s: None)
    client, _ = client_simule([(503, "surchargé"), (200, {"items": [{"n": 1, "resume": "R", "pourquoi": "P"}]})])
    resultat = rediger(sujet_cs2, candidats, client)
    assert not resultat.degrade and len(resultat.items) == 1


def test_col13_reponse_illisible(sujet_cs2, candidats):
    client, _ = client_simule([(200, {"autre_chose": True})])
    assert rediger(sujet_cs2, candidats, client).degrade


def test_col13_sans_cle_d_api(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ModeleIndisponible, match="GEMINI_API_KEY"):
        ClientModele.depuis_environnement(MODELE)


def test_col13_sans_client_le_mode_degrade_est_signale(sujet_cs2, candidats):
    resultat = rediger(sujet_cs2, candidats, None)
    assert resultat.degrade and resultat.requetes == 0 and len(resultat.items) == 2


def test_section_vide_sans_appel(sujet_cs2):
    client, appels = client_simule([])
    resultat = rediger(sujet_cs2, [], client)
    assert resultat.items == [] and appels == []


def test_budget_d_entree_respecte(article):
    longs = [article(titre="T" * 200, lien=f"https://exemple.fr/{i}", chapo="x" * 2000) for i in range(100)]
    candidats = preparer_candidats(longs)
    assert 0 < len(candidats) <= 40

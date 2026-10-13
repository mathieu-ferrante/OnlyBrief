"""Messages FCM et dédoublonnage des envois (NOT-02, NOT-05, NOT-07, NOT-08, section 7.6)."""

from datetime import date, datetime, timezone

import httpx
import pytest

from onlybrief import notification
from onlybrief.notification import (
    Journal, NotificationImpossible, attendre_en_ligne, construire_message, envoyer_fcm, notifier, texte_alerte,
    texte_edition,
)

JOUR = date(2026, 10, 13)


def test_not02_texte_de_la_notification():
    assert texte_edition(JOUR, 12) == ("OnlyBrief", "Veille du mardi 13 octobre — 12 actualités")
    assert texte_edition(JOUR, 1)[1] == "Veille du mardi 13 octobre — 1 actualité"
    assert texte_alerte("IA / LLM", "Sortie de GPT-7") == ("Alerte · IA / LLM", "Sortie de GPT-7")


def test_section_7_6_message_edition():
    message = construire_message("edition", JOUR, "OnlyBrief", "Veille…",
                                 {"type": "edition", "date": "2026-10-13", "nb_items": 12})["message"]
    assert message["topic"] == "editions"
    assert message["notification"] == {"title": "OnlyBrief", "body": "Veille…"}
    assert message["data"] == {"type": "edition", "date": "2026-10-13", "nb_items": "12"}, "valeurs en texte"
    assert message["android"]["priority"] == "HIGH"
    assert message["android"]["notification"] == {"channel_id": "editions", "tag": "edition-2026-10-13"}
    assert message["android"]["collapse_key"] == "edition-2026-10-13"


def test_not08_alerte_sur_un_canal_separe():
    message = construire_message("alerte", JOUR, "t", "x", {"type": "alerte", "date": "2026-10-13"})["message"]
    assert message["android"]["notification"]["channel_id"] == "alertes"
    assert message["android"]["notification"]["tag"] == "alerte-2026-10-13"


def test_not05_une_seule_notification_par_edition(tmp_path, monkeypatch):
    envois = []
    monkeypatch.setattr(notification, "envoyer_fcm", lambda message: envois.append(message) or "projects/x/messages/1")
    etat = tmp_path / "notifications.json"
    assert notifier(etat, "edition", JOUR, "t", "x", {"type": "edition"}) is True
    assert notifier(etat, "edition", JOUR, "t", "x", {"type": "edition"}) is False, "nouvel essai : pas de doublon"
    assert notifier(etat, "alerte", JOUR, "t", "x", {"type": "alerte"}) is True
    assert len(envois) == 2
    assert set(Journal(etat).envoyees) == {"edition-2026-10-13", "alerte-2026-10-13"}


def test_journal_oublie_les_vieux_envois(tmp_path):
    journal = Journal(tmp_path / "n.json")
    journal.envoyees["edition-2026-01-01"] = "2026-01-01T07:30:00+01:00"
    journal.noter("edition-2026-10-13", datetime(2026, 10, 13, 5, 30, tzinfo=timezone.utc))
    assert list(journal.envoyees) == ["edition-2026-10-13"]


def test_sans_compte_de_service_rien_n_est_envoye(monkeypatch):
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT", raising=False)
    with pytest.raises(NotificationImpossible, match="absente"):
        envoyer_fcm({"message": {}})


def test_envoi_fcm(monkeypatch):
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT", '{"project_id": "onlybrief-test"}')
    monkeypatch.setattr(notification, "_jeton_acces", lambda compte: "jeton")
    requetes = []

    def fcm(requete):
        requetes.append(requete)
        return httpx.Response(200, json={"name": "projects/onlybrief-test/messages/42"})

    nom = envoyer_fcm({"message": {"topic": "editions"}}, httpx.Client(transport=httpx.MockTransport(fcm)))
    assert nom.endswith("/42")
    assert str(requetes[0].url) == "https://fcm.googleapis.com/v1/projects/onlybrief-test/messages:send"
    assert requetes[0].headers["Authorization"] == "Bearer jeton"


def test_envoi_fcm_refuse(monkeypatch):
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT", '{"project_id": "p"}')
    monkeypatch.setattr(notification, "_jeton_acces", lambda compte: "jeton")
    monkeypatch.setattr(notification.time, "sleep", lambda s: None)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403, text="interdit")))
    with pytest.raises(NotificationImpossible, match="403"):
        envoyer_fcm({"message": {}}, client)


def test_col11_attente_de_la_mise_en_ligne(monkeypatch):
    monkeypatch.setattr(notification.time, "sleep", lambda s: None)
    reponses = iter([
        httpx.Response(404),
        httpx.Response(200, json={"date": "2026-10-12"}),          # ancienne version en cache
        httpx.Response(200, json={"date": "2026-10-13"}),
    ])
    client = httpx.Client(transport=httpx.MockTransport(lambda r: next(reponses)))
    attendre_en_ligne("https://exemple.github.io/editions/2026-10-13.json", {"date": "2026-10-13"}, client=client)


def test_col11_jamais_en_ligne(monkeypatch):
    monkeypatch.setattr(notification.time, "sleep", lambda s: None)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    from datetime import timedelta
    with pytest.raises(NotificationImpossible, match="pas en ligne"):
        attendre_en_ligne("https://exemple.github.io/x.json", {}, delai_max=timedelta(0), client=client)

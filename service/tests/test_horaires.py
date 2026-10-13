"""Horaires de publication en heure de Paris, été et hiver (NOT-01, COL-01, ALR-01)."""

from datetime import date, datetime, timezone

import pytest

from onlybrief.horaires import creneau_alerte, creneau_edition, date_longue, heure_publication, iso


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_heure_publication_semaine_et_week_end():
    assert heure_publication(date(2026, 10, 13)).strftime("%H:%M %z") == "07:30 +0200"  # mardi, été
    assert heure_publication(date(2026, 10, 17)).strftime("%H:%M %z") == "10:00 +0200"  # samedi
    assert heure_publication(date(2026, 10, 26)).strftime("%H:%M %z") == "07:30 +0100"  # lundi, hiver


# Les crons de la section 9 : chaque démarrage tombe soit dans le bon créneau, soit nulle part.
@pytest.mark.parametrize("demarrage_utc, attendu", [
    # Mardi 13 octobre 2026 (été, UTC+2) : 4h45 UTC = 6h45 Paris -> publication 7h30
    (utc(2026, 10, 13, 4, 45), "2026-10-13T07:30:00+02:00"),
    (utc(2026, 10, 13, 5, 45), "2026-10-13T07:30:00+02:00"),   # cron « hiver » en été : 7h45, retard toléré
    # Lundi 26 octobre 2026 (hiver, UTC+1) : 5h45 UTC = 6h45 Paris
    (utc(2026, 10, 26, 5, 45), "2026-10-26T07:30:00+01:00"),
    (utc(2026, 10, 26, 4, 45), None),                          # cron « été » en hiver : 5h45, trop tôt
    # Samedi 24 octobre (dernier jour d'été) et dimanche 25 octobre (premier jour d'hiver)
    (utc(2026, 10, 24, 7, 15), "2026-10-24T10:00:00+02:00"),
    (utc(2026, 10, 25, 8, 15), "2026-10-25T10:00:00+01:00"),
    (utc(2026, 10, 25, 7, 15), None),                          # 8h15 Paris : trop tôt
    # Passage à l'heure d'été : dimanche 28 mars 2027, lundi 29 mars
    (utc(2027, 3, 28, 7, 15), "2027-03-28T10:00:00+02:00"),
    (utc(2027, 3, 29, 4, 45), "2027-03-29T07:30:00+02:00"),
    (utc(2027, 3, 26, 5, 45), "2027-03-26T07:30:00+01:00"),    # vendredi avant, encore en hiver
    (utc(2027, 3, 26, 4, 45), None),
])
def test_creneau_edition_ete_hiver(demarrage_utc, attendu):
    creneau = creneau_edition(demarrage_utc)
    assert (creneau.isoformat() if creneau else None) == attendu


def test_creneau_edition_retard_trop_important():
    assert creneau_edition(utc(2026, 10, 13, 7, 0)) is None   # 9h Paris, plus d'une heure de retard


def test_creneau_edition_refuse_une_heure_sans_fuseau():
    with pytest.raises(ValueError):
        creneau_edition(datetime(2026, 10, 13, 5, 0))


@pytest.mark.parametrize("instant, attendu", [
    (utc(2026, 10, 13, 7, 5), 9),      # 9h05 Paris en été
    (utc(2026, 10, 13, 8, 5), None),   # 10h05
    (utc(2026, 10, 13, 19, 0), 21),
    (utc(2026, 10, 26, 8, 0), 9),      # 9h Paris en hiver
    (utc(2026, 10, 26, 7, 0), None),   # 8h Paris en hiver
    (utc(2026, 10, 26, 21, 0), None),  # 22h
])
def test_creneau_alerte(instant, attendu):
    assert creneau_alerte(instant) == attendu


def test_date_longue_et_iso():
    assert date_longue(date(2026, 10, 13)) == "mardi 13 octobre"
    assert iso(utc(2026, 10, 13, 5, 30, 42)) == "2026-10-13T07:30:00+02:00"

"""Calcul des horaires en heure de Paris (NOT-01, COL-01, ALR-01).

GitHub Actions planifie en UTC : les workflows démarrent aux deux horaires
possibles (heure d'été et heure d'hiver) et ces fonctions décident si
l'exécution courante tombe dans le bon créneau.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")

HEURE_SEMAINE = time(7, 30)       # lundi–vendredi
HEURE_WEEK_END = time(10, 0)      # samedi–dimanche
AVANCE_DEMARRAGE = timedelta(minutes=45)
HEURES_ALERTE = (9, 11, 13, 15, 17, 19, 21)

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre")


def maintenant_paris() -> datetime:
    return datetime.now(timezone.utc).astimezone(PARIS)


def en_paris(instant: datetime) -> datetime:
    if instant.tzinfo is None:
        raise ValueError("l'instant doit porter un fuseau horaire")
    return instant.astimezone(PARIS)


def heure_publication(jour: date) -> datetime:
    """Heure de publication de l'édition du jour donné, en heure de Paris."""
    heure = HEURE_WEEK_END if jour.weekday() >= 5 else HEURE_SEMAINE
    return datetime.combine(jour, heure, tzinfo=PARIS)


def creneau_edition(instant: datetime, tolerance: timedelta = timedelta(hours=1)) -> datetime | None:
    """Renvoie l'heure de publication visée si `instant` est dans la fenêtre de préparation.

    La fenêtre va de 45 minutes avant la publication (démarrage planifié)
    jusqu'à `tolerance` après, pour absorber les retards de GitHub Actions.
    Hors fenêtre (par exemple le cron « heure d'hiver » pendant l'été),
    renvoie None : le script sort alors sans rien faire.
    """
    local = en_paris(instant)
    publication = heure_publication(local.date())
    if publication - AVANCE_DEMARRAGE <= local <= publication + tolerance:
        return publication
    return None


def creneau_alerte(instant: datetime) -> int | None:
    """Heure de vérification d'alerte (9 h, 11 h… 21 h, heure de Paris) ou None."""
    heure = en_paris(instant).hour
    return heure if heure in HEURES_ALERTE else None


def date_longue(jour: date) -> str:
    """« mardi 13 octobre » (NOT-02)."""
    return f"{JOURS[jour.weekday()]} {jour.day} {MOIS[jour.month - 1]}"


def iso(instant: datetime) -> str:
    """Horodatage ISO 8601 à la minute, avec décalage de Paris (format section 7)."""
    return en_paris(instant).replace(second=0, microsecond=0).isoformat()

"""Envoi des notifications par Firebase Cloud Messaging (COL-11, NOT-01, NOT-02, NOT-05, NOT-08).

Les messages partent vers le sujet FCM « editions », en priorité haute, avec
un bloc `notification` (affichable par Android même application arrêtée) et
un bloc `data` (section 7.6).

Une notification n'est envoyée qu'une fois par identifiant (« edition-AAAA-MM-JJ »
ou « alerte-AAAA-MM-JJ ») : l'état est conservé dans `etat/notifications.json`.
Le même identifiant sert d'étiquette Android (`tag`) : un second envoi
remplacerait la notification au lieu d'en afficher une deuxième (NOT-05).

La clé du compte de service Firebase est lue dans la variable d'environnement
FIREBASE_SERVICE_ACCOUNT (secret GitHub), jamais dans le dépôt.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from .horaires import date_longue, en_paris, maintenant_paris

log = logging.getLogger(__name__)

SUJET_FCM = "editions"
CANAL_EDITIONS = "editions"
CANAL_ALERTES = "alertes"
PORTEE_FCM = "https://www.googleapis.com/auth/firebase.messaging"
URL_SITE = os.environ.get("ONLYBRIEF_URL_SITE", "https://mathieu-ferrante.github.io/OnlyBrief/")
CONSERVATION = timedelta(days=60)


class NotificationImpossible(Exception):
    """La notification n'a pas pu être envoyée."""


def identifiant(type_message: str, jour: date) -> str:
    return f"{type_message}-{jour.isoformat()}"


def texte_edition(jour: date, nb_items: int) -> tuple[str, str]:
    """Titre et texte de la notification d'édition (NOT-02)."""
    pluriel = "s" if nb_items > 1 else ""
    return "OnlyBrief", f"Veille du {date_longue(jour)} — {nb_items} actualité{pluriel}"


def texte_alerte(nom_sujet: str, titre_item: str) -> tuple[str, str]:
    return f"Alerte · {nom_sujet}", titre_item


def construire_message(type_message: str, jour: date, titre: str, texte: str, data: dict) -> dict:
    """Message FCM HTTP v1 (section 7.6)."""
    ident = identifiant(type_message, jour)
    return {
        "message": {
            "topic": SUJET_FCM,
            "notification": {"title": titre, "body": texte},
            "data": {k: str(v) for k, v in data.items()},
            "android": {
                "priority": "HIGH",
                "collapse_key": ident,
                "ttl": "86400s",
                "notification": {
                    "channel_id": CANAL_ALERTES if type_message == "alerte" else CANAL_EDITIONS,
                    "tag": ident,
                },
            },
        }
    }


class Journal:
    """Notifications déjà envoyées (NOT-05)."""

    def __init__(self, chemin: Path):
        self.chemin = chemin
        self.envoyees: dict[str, str] = {}
        if chemin.exists():
            try:
                self.envoyees = dict(json.loads(chemin.read_text(encoding="utf-8")).get("envoyees", {}))
            except (OSError, ValueError) as exc:
                log.error("État des notifications illisible (%s) : il est réinitialisé", exc)

    def deja_envoyee(self, ident: str) -> bool:
        return ident in self.envoyees

    def noter(self, ident: str, instant: datetime) -> None:
        self.envoyees[ident] = en_paris(instant).isoformat(timespec="seconds")
        limite = (instant - CONSERVATION).date().isoformat()
        self.envoyees = {k: v for k, v in self.envoyees.items() if v[:10] >= limite}

    def sauvegarder(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        texte = json.dumps({"envoyees": dict(sorted(self.envoyees.items()))}, ensure_ascii=False, indent=2) + "\n"
        self.chemin.write_text(texte, encoding="utf-8", newline="\n")


def _jeton_acces(compte_service: dict) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    identifiants = service_account.Credentials.from_service_account_info(compte_service, scopes=[PORTEE_FCM])
    identifiants.refresh(Request())
    return identifiants.token


def envoyer_fcm(message: dict, client: httpx.Client | None = None) -> str:
    """Envoie le message ; renvoie le nom attribué par FCM."""
    brut = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not brut:
        raise NotificationImpossible("variable FIREBASE_SERVICE_ACCOUNT absente (projet Firebase pas encore configuré)")
    try:
        compte = json.loads(brut)
        projet = compte["project_id"]
    except (ValueError, KeyError) as exc:
        raise NotificationImpossible(f"FIREBASE_SERVICE_ACCOUNT illisible : {exc}") from exc
    jeton = _jeton_acces(compte)
    client = client or httpx.Client(timeout=30)
    url = f"https://fcm.googleapis.com/v1/projects/{projet}/messages:send"
    derniere = ""
    for essai in range(1, 4):
        try:
            reponse = client.post(url, json=message, headers={"Authorization": f"Bearer {jeton}"})
        except httpx.HTTPError as exc:
            derniere = f"{type(exc).__name__} : {exc}"
        else:
            if reponse.status_code == 200:
                return reponse.json().get("name", "")
            derniere = f"HTTP {reponse.status_code} : {reponse.text[:300]}"
            if reponse.status_code < 500 and reponse.status_code != 429:
                break
        time.sleep(10 * essai)
    raise NotificationImpossible(derniere)


def attendre_en_ligne(url: str, attendu: dict, delai_max: timedelta = timedelta(minutes=20),
                      client: httpx.Client | None = None, pause: float = 20.0) -> None:
    """Attend que GitHub Pages serve le fichier publié (COL-11 : « publiée et en ligne »).

    `attendu` : paires clé/valeur que le JSON en ligne doit contenir
    (par exemple la date et `publiee_le`), pour ne pas confondre avec une
    ancienne version en cache.
    """
    client = client or httpx.Client(timeout=20, follow_redirects=True, headers={"Cache-Control": "no-cache"})
    fin = time.monotonic() + delai_max.total_seconds()
    while True:
        try:
            reponse = client.get(url, params={"v": str(int(time.time()))})
            if reponse.status_code == 200:
                contenu = reponse.json()
                if all(contenu.get(k) == v for k, v in attendu.items()):
                    log.info("Fichier en ligne : %s", url)
                    return
        except (httpx.HTTPError, ValueError):
            pass
        if time.monotonic() > fin:
            raise NotificationImpossible(f"le fichier n'est pas en ligne après {delai_max} : {url}")
        log.info("En attente de GitHub Pages : %s", url)
        time.sleep(pause)


def attendre_jusqu_a(instant: datetime) -> None:
    """Attend l'heure exacte de publication (section 9 : notification envoyée à l'heure)."""
    reste = (instant - maintenant_paris()).total_seconds()
    if reste > 0:
        log.info("Attente de l'heure de publication (%s), %d s", en_paris(instant).strftime("%H:%M"), reste)
        time.sleep(reste)


def notifier(etat: Path, type_message: str, jour: date, titre: str, texte: str, data: dict) -> bool:
    """Envoie la notification si elle ne l'a pas déjà été. Renvoie True si un envoi a eu lieu."""
    journal = Journal(etat)
    ident = identifiant(type_message, jour)
    if journal.deja_envoyee(ident):
        log.info("Notification %s déjà envoyée le %s : pas de nouvel envoi (NOT-05)", ident, journal.envoyees[ident])
        return False
    nom = envoyer_fcm(construire_message(type_message, jour, titre, texte, data))
    journal.noter(ident, maintenant_paris())
    journal.sauvegarder()
    log.info("Notification envoyée : %s « %s » (%s)", ident, texte, nom)
    return True

"""Ligne de commande OnlyBrief.

    python -m onlybrief edition                 prépare et écrit l'édition du jour (essai manuel)
    python -m onlybrief edition --planifiee     idem, seulement dans le créneau de publication (GitHub Actions)
    python -m onlybrief edition --sans-modele   simule un modèle indisponible (test COL-13)
    python -m onlybrief alerte [--planifiee]    cherche une annonce majeure (ALR-01)
    python -m onlybrief notifier edition|alerte --date AAAA-MM-JJ
                                                attend la mise en ligne puis l'heure, et envoie la notification
    python -m onlybrief verifier-config         vérifie sujets.yaml sans rien collecter (CFG-03)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

from .alertes import verifier_alerte
from .config import ConfigInvalide, lire
from .edition import Chemins, EditionImpossible, preparer_edition
from .horaires import creneau_alerte, creneau_edition, maintenant_paris
from .notification import (
    URL_SITE, NotificationImpossible, attendre_en_ligne, attendre_jusqu_a, notifier, texte_alerte, texte_edition,
)

log = logging.getLogger("onlybrief")


def trouver_racine(depart: Path) -> Path:
    """Remonte jusqu'au dossier qui contient `sujets.yaml` (racine du dépôt)."""
    for dossier in (depart, *depart.parents):
        if (dossier / "sujets.yaml").exists():
            return dossier
    paquet = Path(__file__).resolve().parents[3]
    if (paquet / "sujets.yaml").exists():
        return paquet
    raise SystemExit("Impossible de trouver sujets.yaml : lancez la commande depuis le dépôt ou utilisez --racine.")


def charger_env_local(racine: Path) -> None:
    """Lit le fichier `.env` local (ignoré par git) pour les essais sur un poste.

    Une variable déjà définie dans l'environnement n'est pas remplacée.
    Sur GitHub Actions, les clés viennent des secrets du dépôt.
    """
    fichier = racine / ".env"
    if not fichier.exists():
        return
    for ligne in fichier.read_text(encoding="utf-8-sig").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


def configurer_journal(verbeux: bool) -> None:
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.DEBUG if verbeux else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    for bavard in ("httpx", "google", "urllib3"):
        logging.getLogger(bavard).setLevel(logging.WARNING)


def sortie_github(**valeurs) -> None:
    """Transmet des valeurs aux étapes suivantes du workflow GitHub Actions."""
    fichier = os.environ.get("GITHUB_OUTPUT")
    for cle, valeur in valeurs.items():
        log.debug("sortie %s=%s", cle, valeur)
    if fichier:
        with open(fichier, "a", encoding="utf-8") as f:
            for cle, valeur in valeurs.items():
                f.write(f"{cle}={valeur}\n")


def lire_json(chemin: Path) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8"))


def commande_edition(chemins: Chemins, args) -> int:
    if not args.planifiee:
        chemin = preparer_edition(chemins, jour=args.date, sans_modele=args.sans_modele)
        log.info("Terminé : %s", chemin)
        sortie_github(a_publier="true", date=lire_json(chemin)["date"])
        return 0

    creneau = creneau_edition(maintenant_paris())
    if creneau is None:
        log.info("Hors du créneau de publication (heure de Paris : %s) : rien à faire.",
                 maintenant_paris().strftime("%A %H:%M"))
        sortie_github(a_publier="false")
        return 0
    jour = creneau.date()
    existante = chemins.docs / "editions" / f"{jour.isoformat()}.json"
    if existante.exists() and (lire_json(existante).get("journal") or {}).get("planifiee"):
        log.info("L'édition planifiée du %s existe déjà : seule la notification sera vérifiée.", jour)
        sortie_github(a_publier="true", date=jour.isoformat())
        return 0
    chemin = preparer_edition(chemins, jour=jour, publiee_le=creneau, planifiee=True)
    log.info("Terminé : %s — publication prévue à %s", chemin, creneau.strftime("%H:%M"))
    sortie_github(a_publier="true", date=jour.isoformat())
    return 0


def commande_alerte(chemins: Chemins, args) -> int:
    maintenant = maintenant_paris()
    if args.planifiee and creneau_alerte(maintenant) is None:
        log.info("Pas de vérification d'alerte à %s (créneaux : 9 h à 21 h, toutes les 2 heures).",
                 maintenant.strftime("%H:%M"))
        sortie_github(a_publier="false")
        return 0
    alerte = verifier_alerte(chemins, maintenant)
    if alerte is None:
        sortie_github(a_publier="false")
        return 0
    sortie_github(a_publier="true", date=alerte.jour.isoformat())
    return 0


def commande_notifier(chemins: Chemins, args) -> int:
    jour = args.date
    try:
        if args.type == "edition":
            relatif = f"editions/{jour.isoformat()}.json"
            contenu = lire_json(chemins.docs / relatif)
            if contenu["nb_items"] == 0:
                log.warning("Édition sans actualité : aucune notification « vide » (NOT-07)")
                return 0
            attendre_en_ligne(URL_SITE + relatif, {"date": contenu["date"], "publiee_le": contenu["publiee_le"]})
            attendre_jusqu_a(datetime.fromisoformat(contenu["publiee_le"]))
            titre, texte = texte_edition(jour, contenu["nb_items"])
            data = {"type": "edition", "date": jour.isoformat(), "nb_items": str(contenu["nb_items"])}
        else:
            relatif = f"alertes/{jour.isoformat()}.json"
            contenu = lire_json(chemins.docs / relatif)
            attendre_en_ligne(URL_SITE + relatif, {"date": contenu["date"], "emise_le": contenu["emise_le"]})
            try:
                noms = {s.id: s.nom for s in lire(chemins.sujets).sujets}
            except ConfigInvalide:
                noms = {}
            titre, texte = texte_alerte(noms.get(contenu["sujet_id"], contenu["sujet_id"]), contenu["item"]["titre"])
            data = {"type": "alerte", "date": jour.isoformat()}
        notifier(chemins.notifications, args.type, jour, titre, texte, data)
    except NotificationImpossible as exc:
        if "FIREBASE_SERVICE_ACCOUNT absente" in str(exc):
            log.warning("Notification non envoyée : %s", exc)
            return 0
        log.error("Notification non envoyée : %s", exc)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(prog="onlybrief", description="Service de veille OnlyBrief")
    analyseur.add_argument("--racine", type=Path, help="racine du dépôt (par défaut : détectée)")
    analyseur.add_argument("-v", "--verbeux", action="store_true", help="journal détaillé")
    commandes = analyseur.add_subparsers(dest="commande", required=True)

    cmd = commandes.add_parser("edition", help="prépare et écrit l'édition du jour")
    cmd.add_argument("--date", type=date.fromisoformat, help="date de l'édition (AAAA-MM-JJ), essai manuel")
    cmd.add_argument("--sans-modele", action="store_true", help="simule un modèle indisponible (COL-13)")
    cmd.add_argument("--planifiee", action="store_true", help="exécution planifiée : respecte le créneau horaire")

    cmd = commandes.add_parser("alerte", help="cherche une annonce majeure")
    cmd.add_argument("--planifiee", action="store_true", help="exécution planifiée : respecte les créneaux")

    cmd = commandes.add_parser("notifier", help="envoie la notification d'une édition ou d'une alerte")
    cmd.add_argument("type", choices=["edition", "alerte"])
    cmd.add_argument("--date", type=date.fromisoformat, required=True)

    commandes.add_parser("verifier-config", help="vérifie sujets.yaml")

    args = analyseur.parse_args(argv)
    configurer_journal(args.verbeux)
    chemins = Chemins(args.racine.resolve() if args.racine else trouver_racine(Path.cwd()))
    charger_env_local(chemins.racine)

    if args.commande == "verifier-config":
        try:
            config = lire(chemins.sujets)
        except ConfigInvalide as exc:
            log.error("sujets.yaml est invalide :\n- %s", "\n- ".join(exc.erreurs))
            return 1
        log.info("sujets.yaml est valide : %d sujet(s), dont %d actif(s).", len(config.sujets), len(config.sujets_actifs))
        return 0

    try:
        if args.commande == "edition":
            return commande_edition(chemins, args)
        if args.commande == "alerte":
            return commande_alerte(chemins, args)
        return commande_notifier(chemins, args)
    except (EditionImpossible, ConfigInvalide) as exc:
        log.error("Édition non produite : %s", exc)
        sortie_github(a_publier="false")
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Ligne de commande OnlyBrief.

    python -m onlybrief edition            prépare et écrit l'édition du jour
    python -m onlybrief edition --sans-modele   idem, sans appeler le modèle (test COL-13)
    python -m onlybrief verifier-config    vérifie sujets.yaml sans rien collecter (CFG-03)
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from .config import ConfigInvalide, lire
from .edition import Chemins, EditionImpossible, preparer_edition

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
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(prog="onlybrief", description="Service de veille OnlyBrief")
    analyseur.add_argument("--racine", type=Path, help="racine du dépôt (par défaut : détectée)")
    analyseur.add_argument("-v", "--verbeux", action="store_true", help="journal détaillé")
    commandes = analyseur.add_subparsers(dest="commande", required=True)

    cmd_edition = commandes.add_parser("edition", help="prépare et écrit l'édition du jour")
    cmd_edition.add_argument("--date", type=date.fromisoformat, help="date de l'édition (AAAA-MM-JJ)")
    cmd_edition.add_argument("--sans-modele", action="store_true", help="simule un modèle indisponible (COL-13)")

    commandes.add_parser("verifier-config", help="vérifie sujets.yaml")

    args = analyseur.parse_args(argv)
    configurer_journal(args.verbeux)
    chemins = Chemins(args.racine.resolve() if args.racine else trouver_racine(Path.cwd()))

    if args.commande == "verifier-config":
        try:
            config = lire(chemins.sujets)
        except ConfigInvalide as exc:
            log.error("sujets.yaml est invalide :\n- %s", "\n- ".join(exc.erreurs))
            return 1
        log.info("sujets.yaml est valide : %d sujet(s), dont %d actif(s).", len(config.sujets), len(config.sujets_actifs))
        return 0

    try:
        chemin = preparer_edition(chemins, jour=args.date, sans_modele=args.sans_modele)
    except (EditionImpossible, ConfigInvalide) as exc:
        log.error("Édition non produite : %s", exc)
        return 1
    log.info("Terminé : %s", chemin)
    return 0


if __name__ == "__main__":
    sys.exit(main())

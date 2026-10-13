"""Préparation complète d'une édition : configuration → collecte → filtres → rédaction → publication."""

from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from . import __version__
from .collecte import collecter
from .config import charger
from .dedup import LiensCites, dedoublonner, normaliser_lien
from .filtres import filtrer
from .horaires import PARIS, heure_publication, iso, maintenant_paris
from .publication import Section, construire_edition, edition_precedente, publier
from .redaction import ClientModele, ModeleIndisponible, rediger

log = logging.getLogger(__name__)


class EditionImpossible(Exception):
    """L'édition n'a pas pu être produite : rien n'est publié (NOT-07)."""


@dataclass(frozen=True)
class Chemins:
    racine: Path

    @property
    def sujets(self) -> Path:
        return self.racine / "sujets.yaml"

    @property
    def docs(self) -> Path:
        return self.racine / "docs"

    @property
    def liens_cites(self) -> Path:
        return self.racine / "etat" / "liens_cites.json"

    @property
    def config_valide(self) -> Path:
        return self.racine / "etat" / "derniere_config_valide.yaml"


def debut_collecte(docs: Path, jour: date) -> datetime:
    """Instant à partir duquel un article est nouveau (COL-03).

    C'est l'heure de collecte de l'édition précédente ; à défaut (première
    édition), l'heure de publication de la veille.
    """
    precedente = edition_precedente(docs, jour)
    if precedente:
        repere = (precedente.get("journal") or {}).get("collecte_le") or precedente.get("publiee_le")
        if repere:
            return datetime.fromisoformat(repere)
    return heure_publication(jour - timedelta(days=1))


def preparer_edition(
    chemins: Chemins,
    jour: date | None = None,
    publiee_le: datetime | None = None,
    sans_modele: bool = False,
) -> Path:
    """Produit et écrit l'édition du jour. Renvoie le chemin du fichier écrit."""
    debut = time.monotonic()
    maintenant = maintenant_paris()
    jour = jour or maintenant.date()
    publiee_le = publiee_le or maintenant
    log.info("OnlyBrief %s — préparation de l'édition du %s", __version__, jour.isoformat())

    config, erreurs_config = charger(chemins.sujets, chemins.config_valide)
    sujets = config.sujets_actifs
    log.info("Configuration : %d sujet(s) actif(s) — %s", len(sujets), ", ".join(s.id for s in sujets))

    depuis = debut_collecte(chemins.docs, jour)
    log.info("Articles retenus s'ils sont publiés après le %s", iso(depuis))

    collecte = collecter(sujets)
    if not collecte.sources_lues:
        raise EditionImpossible("aucune source n'a pu être lue")

    client = None
    erreur_modele = ""
    if sans_modele:
        erreur_modele = "modèle désactivé (--sans-modele)"
    else:
        try:
            client = ClientModele.depuis_environnement(config.modele)
        except ModeleIndisponible as exc:
            erreur_modele = str(exc)
            log.error("Modèle indisponible : %s — repli sur les chapôs RSS (COL-13)", exc)

    memoire = LiensCites(chemins.liens_cites)
    sections: list[Section] = []
    ecartes: Counter = Counter()
    erreurs: list[str] = [f"sujets.yaml : {e}" for e in erreurs_config]
    erreurs += [f"source injoignable {cle} : {msg}" for cle, msg in collecte.erreurs.items()]
    degrade = False
    requetes = 0
    deja_traites: list[str] = []

    for sujet in sujets:
        filtrage = filtrer(collecte.articles, sujet, depuis)
        ecartes.update(filtrage.ecartes)
        candidats, doublons = dedoublonner(filtrage.retenus)
        ecartes["doublon"] += doublons
        candidats, deja_cites = memoire.filtrer(candidats, jour)
        ecartes["lien déjà cité (14 jours)"] += deja_cites
        liens_pris = {normaliser_lien(item.article.lien) for s in sections for item in s.items}
        candidats = [a for a in candidats if normaliser_lien(a.lien) not in liens_pris]

        redaction = rediger(sujet, candidats, client, deja_traites)
        deja_traites += [item.article.titre for item in redaction.items]
        requetes += redaction.requetes
        ecartes["non retenu par le tri"] += redaction.non_retenus
        if redaction.degrade:
            degrade = True
            if redaction.erreur and redaction.erreur not in erreurs:
                erreurs.append(f"modèle ({sujet.id}) : {redaction.erreur}")

        echecs = [cle.split("/", 1)[1] for cle in collecte.sources_en_echec if cle.startswith(f"{sujet.id}/")]
        sections.append(Section(sujet=sujet, items=redaction.items, sources_en_echec=echecs))
        log.info(
            "Section « %s » : %d candidat(s), %d item(s) retenu(s)%s",
            sujet.nom, len(candidats), len(redaction.items), " [résumés dégradés]" if redaction.degrade else "",
        )

    if erreur_modele and erreur_modele not in erreurs:
        erreurs.append(f"modèle : {erreur_modele}")

    journal = {
        "genere_le": iso(maintenant_paris()),
        "collecte_le": maintenant.astimezone(PARIS).isoformat(timespec="seconds"),
        "depuis": iso(depuis),
        "version_service": __version__,
        "modele": f"{config.modele.fournisseur}/{config.modele.nom}",
        "requetes_modele": requetes,
        "configuration": "dernière configuration valide reprise" if erreurs_config else "valide",
        "sources_lues": len(collecte.sources_lues),
        "sources_en_echec": len(collecte.sources_en_echec),
        "articles_collectes": len(collecte.articles),
        "ecartes": dict(sorted(ecartes.items())),
        "erreurs": erreurs,
        "duree_secondes": round(time.monotonic() - debut, 1),
    }
    edition = construire_edition(jour, publiee_le, sections, degrade, journal)
    chemin = publier(chemins.docs, edition, maintenant_paris())

    memoire.enregistrer([item["lien"] for s in edition["sections"] for item in s["items"]], jour)
    memoire.sauvegarder()

    log.info(
        "Bilan : %d items publiés, %d article(s) écarté(s), %d requête(s) au modèle, %d erreur(s)",
        edition["nb_items"], sum(ecartes.values()), requetes, len(erreurs),
    )
    for erreur in erreurs:
        log.warning("Erreur consignée : %s", erreur)
    return chemin

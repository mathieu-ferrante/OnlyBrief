"""Préparation complète d'une édition : configuration → collecte → filtres → rédaction → publication."""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path

from . import __version__
from .collecte import collecter
from .config import charger
from .alertes import alerte_a_reprendre
from .collecte import Article
from .dedup import LiensCites, dedoublonner, normaliser_lien
from .filtres import filtrer
from .horaires import PARIS, heure_publication, iso, maintenant_paris
from .publication import Section, construire_edition, edition_precedente, publier
from .redaction import ClientModele, ItemRedige, ModeleIndisponible, ResultatRedaction, rediger

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

    @property
    def echecs(self) -> Path:
        return self.racine / "etat" / "sources_en_echec.json"

    @property
    def notifications(self) -> Path:
        return self.racine / "etat" / "notifications.json"


def item_depuis_alerte(alerte: dict) -> ItemRedige:
    """L'information alertée, reprise telle quelle dans l'édition suivante (ALR-02)."""
    item = alerte["item"]
    article = Article(
        sujet_id=alerte["sujet_id"], source=item["source"], titre=item["titre"], lien=item["lien"],
        publie_le=datetime.fromisoformat(item["publie_le"]) if item.get("publie_le") else None,
        autres_sources=list(item.get("autres_sources", [])),
    )
    return ItemRedige(article=article, resume=item["resume"], pourquoi=item["pourquoi"], deja_signale=True)


def suivre_echecs(chemin: Path, en_echec: list[str], jour: date, seuil: int = 3) -> list[str]:
    """Compte les jours d'échec consécutifs par source ; renvoie celles qui atteignent le seuil (section 15)."""
    try:
        etat = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    except (OSError, ValueError):
        etat = {}
    nouveau = {}
    for cle in en_echec:
        precedent = etat.get(cle, {})
        jours = precedent.get("jours", 0)
        if precedent.get("dernier") != jour.isoformat():
            jours += 1
        nouveau[cle] = {"jours": jours, "dernier": jour.isoformat()}
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(nouveau, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return [cle for cle, v in nouveau.items() if v["jours"] >= seuil]


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
    planifiee: bool = False,
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
    alerte = alerte_a_reprendre(chemins.docs, depuis)
    if alerte:
        log.info("Alerte du %s reprise dans l'édition, marquée « déjà signalée » (ALR-02)", alerte["date"])

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
        repris: list[ItemRedige] = []
        if alerte and alerte["sujet_id"] == sujet.id:
            repris = [item_depuis_alerte(alerte)]
            liens_pris.add(normaliser_lien(repris[0].article.lien))
            deja_traites.append(repris[0].article.titre)
        candidats = [a for a in candidats if normaliser_lien(a.lien) not in liens_pris]

        place = replace(sujet, max_items=sujet.max_items - len(repris))
        if place.max_items > 0:
            redaction = rediger(place, candidats, client, deja_traites)
        else:
            redaction = ResultatRedaction(items=[], degrade=False, non_retenus=len(candidats))
        redaction.items = repris + redaction.items
        deja_traites += [item.article.titre for item in redaction.items[len(repris):]]
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
    for source in suivre_echecs(chemins.echecs, collecte.sources_en_echec, jour):
        message = f"source en échec depuis au moins 3 jours : {source} (vérifier son flux dans sujets.yaml)"
        erreurs.append(message)

    journal = {
        "genere_le": iso(maintenant_paris()),
        "collecte_le": maintenant.astimezone(PARIS).isoformat(timespec="seconds"),
        "depuis": iso(depuis),
        "version_service": __version__,
        "planifiee": planifiee,
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

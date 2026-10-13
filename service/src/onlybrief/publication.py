"""Écriture des fichiers publiés : édition datée et index (COL-09, section 7)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import Sujet
from .horaires import iso
from .redaction import ItemRedige

log = logging.getLogger(__name__)

CONSERVATION_SITE = timedelta(days=60)
TAILLE_MAX_EDITION = 100 * 1024     # NF-05


@dataclass
class Section:
    sujet: Sujet
    items: list[ItemRedige]
    sources_en_echec: list[str]


def construire_edition(
    jour: date,
    publiee_le: datetime,
    sections: list[Section],
    resumes_degrades: bool,
    journal: dict,
) -> dict:
    """Assemble l'édition au format de la section 7.2.

    Le champ `journal` (résumé d'exécution, COL-12) s'ajoute aux champs de la
    section 7.2 ; l'application peut l'ignorer.
    """
    sections_json = []
    for section in sections:
        items_json = []
        for rang, item in enumerate(section.items, start=1):
            article = item.article
            items_json.append({
                "id": f"{section.sujet.id}-{jour.isoformat()}-{rang:02d}",
                "titre": article.titre,
                "resume": item.resume,
                "pourquoi": item.pourquoi,
                "deja_signale": item.deja_signale,
                "source": article.source,
                "lien": article.lien,
                "publie_le": iso(article.publie_le) if article.publie_le else "",
                "autres_sources": list(article.autres_sources),
            })
        sections_json.append({
            "sujet_id": section.sujet.id,
            "nom": section.sujet.nom,
            "sources_en_echec": list(section.sources_en_echec),
            "items": items_json,
        })
    return {
        "date": jour.isoformat(),
        "publiee_le": iso(publiee_le),
        "nb_items": sum(len(s["items"]) for s in sections_json),
        "resumes_degrades": resumes_degrades,
        "sections": sections_json,
        "journal": journal,
    }


def ecrire_json(chemin: Path, contenu: dict) -> int:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    texte = json.dumps(contenu, ensure_ascii=False, indent=2) + "\n"
    chemin.write_text(texte, encoding="utf-8", newline="\n")
    return len(texte.encode("utf-8"))


def lire_index(docs: Path) -> dict:
    chemin = docs / "index.json"
    if not chemin.exists():
        return {"mis_a_jour_le": "", "editions": [], "derniere_alerte": None}
    return json.loads(chemin.read_text(encoding="utf-8"))


def edition_precedente(docs: Path, jour: date) -> dict | None:
    """Dernière édition publiée strictement avant `jour` (pour COL-03)."""
    for entree in lire_index(docs).get("editions", []):
        if date.fromisoformat(entree["date"]) < jour:
            chemin = docs / entree["fichier"]
            if chemin.exists():
                return json.loads(chemin.read_text(encoding="utf-8"))
    return None


def publier(docs: Path, edition: dict, maintenant: datetime) -> Path:
    """Écrit `editions/AAAA-MM-JJ.json`, met à jour `index.json` et purge au-delà de 60 jours."""
    jour = date.fromisoformat(edition["date"])
    relatif = f"editions/{jour.isoformat()}.json"
    taille = ecrire_json(docs / relatif, edition)
    if taille > TAILLE_MAX_EDITION:
        log.warning("Édition de %d Ko, au-delà de la limite de 100 Ko (NF-05)", taille // 1024)
    log.info("Édition écrite : %s (%d Ko, %d items)", relatif, max(1, taille // 1024), edition["nb_items"])

    limite = jour - CONSERVATION_SITE
    for fichier in sorted((docs / "editions").glob("*.json")):
        try:
            date_fichier = date.fromisoformat(fichier.stem)
        except ValueError:
            continue
        if date_fichier < limite:
            fichier.unlink()
            log.info("Édition de plus de 60 jours supprimée : %s", fichier.name)

    index = lire_index(docs)
    editions = [e for e in index.get("editions", []) if e["date"] != jour.isoformat()]
    editions.append({"date": jour.isoformat(), "nb_items": edition["nb_items"], "fichier": relatif})
    editions = [e for e in editions if (docs / e["fichier"]).exists()]
    editions.sort(key=lambda e: e["date"], reverse=True)
    ecrire_json(docs / "index.json", {
        "mis_a_jour_le": iso(maintenant),
        "editions": editions,
        "derniere_alerte": index.get("derniere_alerte"),
    })
    return docs / relatif

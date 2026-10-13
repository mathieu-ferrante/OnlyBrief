"""Détection d'une annonce majeure en cours de journée (ALR-01, ALR-02, NOT-08).

Toutes les 2 heures de 9 h à 21 h (heure de Paris), le service relit les
sources. Un sujet est soumis au modèle si, parmi ses articles des 2 dernières
heures :
  - au moins 3 sources différentes ont publié, ou
  - un article contient un mot-clé d'alerte du sujet.
Le modèle doit confirmer une annonce majeure ; l'alerte n'est retenue que si
l'information est reprise par au moins 3 sources ou porte un mot-clé d'alerte.
Une alerte au plus par jour.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .collecte import Article, collecter, texte_brut
from .config import Sujet, charger
from .dedup import LiensCites, dedoublonner, normaliser_lien
from .filtres import contient_un, filtrer
from .horaires import iso
from .publication import ecrire_json, lire_index
from .redaction import LONGUEUR_EXTRAIT, LONGUEUR_POURQUOI, LONGUEUR_RESUME, ClientModele, ModeleIndisponible

log = logging.getLogger(__name__)

FENETRE = timedelta(hours=2)
SEUIL_SOURCES = 3
MAX_CANDIDATS = 30

CONSIGNES_ALERTE = """\
Tu surveilles l'actualité de la rubrique « {nom} » pour une revue de presse française.
On te donne les articles parus dans les deux dernières heures.
Décide s'il y a UNE annonce majeure qui justifie d'interrompre le lecteur en pleine journée par une alerte :
un événement de premier plan pour ce domaine (par exemple : sortie d'un modèle ou produit phare,
faille de sécurité critique exploitée, décision réglementaire importante, résultat d'une finale majeure).
Une actualité ordinaire, une rumeur, une promotion, un test ou une analyse ne justifient PAS d'alerte.
En cas de doute, réponds "alerte": false.
{consignes}
Si une alerte se justifie :
- "n" : numéro de l'article le plus complet sur ce fait ;
- "meme_fait" : numéros de TOUS les autres articles qui traitent du même fait ;
- "resume" : deux lignes en français (moins de 240 caractères), sans ajouter d'information absente des articles ;
- "pourquoi" : une ligne en français (moins de 160 caractères) sur la portée de l'information.
Réponds uniquement par un objet JSON :
{{"alerte": true/false, "n": <numéro>, "meme_fait": [<numéros>], "resume": "...", "pourquoi": "..."}}
"""

SCHEMA_ALERTE = {
    "type": "object",
    "properties": {
        "alerte": {"type": "boolean"},
        "n": {"type": "integer"},
        "meme_fait": {"type": "array", "items": {"type": "integer"}},
        "resume": {"type": "string"},
        "pourquoi": {"type": "string"},
    },
    "required": ["alerte"],
}


@dataclass
class Alerte:
    jour: date
    sujet: Sujet
    contenu: dict


def declencheurs(sujet: Sujet, articles: list[Article]) -> tuple[list[str], int]:
    """Mots-clés d'alerte trouvés et nombre de sources différentes dans la fenêtre."""
    mots = []
    for a in articles:
        mot = contient_un(f"{a.titre} {a.chapo}", sujet.mots_cles_alerte)
        if mot and mot not in mots:
            mots.append(mot)
    return mots, len({a.source for a in articles})


def _deja_publie(memoire: LiensCites, lien: str) -> bool:
    """Lien déjà cité dans une édition récente, y compris celle du jour."""
    return normaliser_lien(lien) in memoire.liens


def examiner_sujet(sujet: Sujet, articles: list[Article], client: ClientModele, jour: date,
                   instant: datetime) -> dict | None:
    """Soumet un sujet au modèle ; renvoie le contenu de l'alerte (section 7.4) ou None."""
    candidats = sorted(articles, key=lambda a: a.publie_le, reverse=True)[:MAX_CANDIDATS]
    consignes = f"Consignes particulières : {sujet.consignes}" if sujet.consignes else ""
    systeme = CONSIGNES_ALERTE.format(nom=sujet.nom, consignes=consignes)
    utilisateur = json.dumps({"articles": [
        {"n": i, "titre": a.titre, "source": a.source, "date": a.publie_le.isoformat(),
         "extrait": texte_brut(a.chapo, LONGUEUR_EXTRAIT)}
        for i, a in enumerate(candidats, start=1)
    ]}, ensure_ascii=False)
    reponse = client.completer(systeme, utilisateur, SCHEMA_ALERTE)
    if not isinstance(reponse, dict) or reponse.get("alerte") is not True:
        log.info("Sujet « %s » : le modèle ne confirme pas d'annonce majeure", sujet.nom)
        return None
    n = reponse.get("n")
    if not isinstance(n, int) or not 1 <= n <= len(candidats):
        log.warning("Sujet « %s » : réponse d'alerte sans article valide (%s)", sujet.nom, reponse)
        return None
    groupe = [n] + [m for m in reponse.get("meme_fait") or [] if isinstance(m, int) and 1 <= m <= len(candidats) and m != n]
    principal = candidats[n - 1]
    sources = []
    for m in groupe:
        if candidats[m - 1].source not in sources:
            sources.append(candidats[m - 1].source)
    mot = contient_un(f"{principal.titre} {principal.chapo}", sujet.mots_cles_alerte)
    if len(sources) < SEUIL_SOURCES and not mot:
        log.info("Sujet « %s » : « %s » écarté — %d source(s) et aucun mot-clé d'alerte (ALR-01)",
                 sujet.nom, principal.titre, len(sources))
        return None
    resume = texte_brut(str(reponse.get("resume") or ""), LONGUEUR_RESUME) or texte_brut(principal.chapo, LONGUEUR_RESUME)
    pourquoi = texte_brut(str(reponse.get("pourquoi") or ""), LONGUEUR_POURQUOI)
    if not resume or not pourquoi:
        log.warning("Sujet « %s » : alerte sans résumé exploitable, écartée", sujet.nom)
        return None
    raison = f"mot-clé « {mot} »" if mot else f"{len(sources)} sources"
    log.info("ALERTE confirmée — %s : « %s » (%s)", sujet.nom, principal.titre, raison)
    return {
        "date": jour.isoformat(),
        "emise_le": iso(instant),
        "sujet_id": sujet.id,
        "item": {
            "id": f"alerte-{jour.isoformat()}",
            "titre": principal.titre,
            "resume": resume,
            "pourquoi": pourquoi,
            "source": principal.source,
            "lien": principal.lien,
            "publie_le": iso(principal.publie_le),
            "autres_sources": sources[1:],
        },
        "declencheur": raison,
    }


def verifier_alerte(chemins, instant: datetime) -> Alerte | None:
    """Passe de vérification. Écrit `alertes/AAAA-MM-JJ.json` et met à jour l'index si une alerte part."""
    jour = instant.date()
    index = lire_index(chemins.docs)
    derniere = index.get("derniere_alerte") or {}
    if derniere.get("date") == jour.isoformat():
        log.info("Une alerte a déjà été émise aujourd'hui : pas d'autre alerte (ALR-02)")
        return None

    config, _ = charger(chemins.sujets, chemins.config_valide)
    try:
        client = ClientModele.depuis_environnement(config.modele)
    except ModeleIndisponible as exc:
        log.error("Modèle indisponible : %s — aucune alerte ne peut être confirmée", exc)
        return None

    sujets = [s for s in config.sujets_actifs if s.mots_cles_alerte or len(s.sources) >= SEUIL_SOURCES]
    collecte = collecter(sujets)
    memoire = LiensCites(chemins.liens_cites)
    depuis = instant - FENETRE

    for sujet in sujets:
        recents = filtrer(collecte.articles, sujet, depuis).retenus
        recents, _ = dedoublonner(recents)
        recents = [a for a in recents if not _deja_publie(memoire, a.lien)]
        mots, nb_sources = declencheurs(sujet, recents)
        log.info("Sujet « %s » : %d article(s) récent(s), %d source(s), mots-clés d'alerte : %s",
                 sujet.nom, len(recents), nb_sources, ", ".join(mots) or "aucun")
        if not mots and nb_sources < SEUIL_SOURCES:
            continue
        try:
            contenu = examiner_sujet(sujet, recents, client, jour, instant)
        except ModeleIndisponible as exc:
            log.error("Modèle indisponible pour « %s » : %s", sujet.nom, exc)
            continue
        if contenu:
            relatif = f"alertes/{jour.isoformat()}.json"
            ecrire_json(chemins.docs / relatif, contenu)
            index = lire_index(chemins.docs)
            index["derniere_alerte"] = {"date": jour.isoformat(), "fichier": relatif}
            index["mis_a_jour_le"] = iso(instant)
            ecrire_json(chemins.docs / "index.json", index)
            log.info("Alerte écrite : %s (%d requête(s) au modèle)", relatif, client.requetes)
            return Alerte(jour=jour, sujet=sujet, contenu=contenu)
    log.info("Aucune alerte (%d requête(s) au modèle)", client.requetes)
    return None


def alerte_a_reprendre(docs, depuis: datetime) -> dict | None:
    """Dernière alerte émise depuis l'édition précédente, à reprendre dans l'édition (ALR-02)."""
    derniere = lire_index(docs).get("derniere_alerte") or {}
    chemin = docs / derniere.get("fichier", "-")
    if not derniere or not chemin.exists():
        return None
    alerte = json.loads(chemin.read_text(encoding="utf-8"))
    if datetime.fromisoformat(alerte["emise_le"]) <= depuis:
        return None
    return alerte

"""Lecture et validation de `sujets.yaml` (CFG-01 à CFG-05).

Un fichier mal formé est détecté avant toute collecte : le service reprend
alors la dernière configuration valide, conservée dans `etat/`, et consigne
l'erreur (CFG-03).
"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

LANGUES_CONNUES = {"fr", "en"}
FOURNISSEURS_CONNUS = {"gemini", "groq", "mistral"}
_ID_VALIDE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class ConfigInvalide(Exception):
    """Le fichier de configuration ne respecte pas le format attendu."""

    def __init__(self, erreurs: list[str]):
        self.erreurs = erreurs
        super().__init__("Configuration invalide :\n- " + "\n- ".join(erreurs))


@dataclass(frozen=True)
class Source:
    nom: str
    flux: str
    mots_cles_obligatoires: bool = False


@dataclass(frozen=True)
class Sujet:
    id: str
    nom: str
    ordre: int
    max_items: int
    sources: tuple[Source, ...]
    actif: bool = True
    langues: tuple[str, ...] = ("fr", "en")
    mots_cles: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    mots_cles_alerte: tuple[str, ...] = ()
    consignes: str = ""


@dataclass(frozen=True)
class Modele:
    fournisseur: str
    nom: str


@dataclass(frozen=True)
class Config:
    modele: Modele
    sujets: tuple[Sujet, ...] = field(default_factory=tuple)

    @property
    def sujets_actifs(self) -> list[Sujet]:
        """Sujets suivis, dans l'ordre d'affichage (CFG-04, APP-02)."""
        return sorted((s for s in self.sujets if s.actif), key=lambda s: s.ordre)


# ─── Validation ──────────────────────────────────────────────────────────────

def _liste_de_textes(valeur, chemin: str, erreurs: list[str]) -> tuple[str, ...]:
    if valeur is None:
        return ()
    if not isinstance(valeur, list) or not all(isinstance(v, str) and v.strip() for v in valeur):
        erreurs.append(f"{chemin} doit être une liste de textes (exemple : [\"mot 1\", \"mot 2\"])")
        return ()
    return tuple(v.strip() for v in valeur)


def _booleen(valeur, chemin: str, defaut: bool, erreurs: list[str]) -> bool:
    if valeur is None:
        return defaut
    if not isinstance(valeur, bool):
        erreurs.append(f"{chemin} doit valoir true ou false")
        return defaut
    return valeur


def _entier_positif(valeur, chemin: str, erreurs: list[str]) -> int:
    if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < 1:
        erreurs.append(f"{chemin} doit être un nombre entier supérieur ou égal à 1")
        return 1
    return valeur


def _valider_source(brut, chemin: str, erreurs: list[str]) -> Source | None:
    if not isinstance(brut, dict):
        erreurs.append(f"{chemin} doit contenir « nom » et « flux »")
        return None
    nom = brut.get("nom")
    flux = brut.get("flux")
    if not isinstance(nom, str) or not nom.strip():
        erreurs.append(f"{chemin}.nom est manquant")
    if not isinstance(flux, str) or not flux.startswith("https://"):
        erreurs.append(f"{chemin}.flux doit être une adresse commençant par https:// (NF-08)")
    obligatoires = _booleen(brut.get("mots_cles_obligatoires"), f"{chemin}.mots_cles_obligatoires", False, erreurs)
    inconnus = set(brut) - {"nom", "flux", "mots_cles_obligatoires"}
    if inconnus:
        erreurs.append(f"{chemin} : champ(s) inconnu(s) {sorted(inconnus)}")
    if isinstance(nom, str) and isinstance(flux, str):
        return Source(nom=nom.strip(), flux=flux.strip(), mots_cles_obligatoires=obligatoires)
    return None


_CHAMPS_SUJET = {
    "id", "nom", "actif", "ordre", "max_items", "langues", "mots_cles",
    "exclusions", "mots_cles_alerte", "consignes", "sources",
}


def _valider_sujet(brut, index: int, erreurs: list[str]) -> Sujet | None:
    chemin = f"sujets[{index + 1}]"
    if not isinstance(brut, dict):
        erreurs.append(f"{chemin} doit être un bloc de champs (id, nom, sources…)")
        return None
    sid = brut.get("id")
    if not isinstance(sid, str) or not _ID_VALIDE.match(sid):
        erreurs.append(f"{chemin}.id doit être un identifiant court en minuscules (lettres, chiffres, - ou _)")
        sid = f"?{index + 1}"
    chemin = f"sujet « {sid} »"
    nom = brut.get("nom")
    if not isinstance(nom, str) or not nom.strip():
        erreurs.append(f"{chemin} : le champ nom est manquant")
        nom = sid
    inconnus = set(brut) - _CHAMPS_SUJET
    if inconnus:
        erreurs.append(f"{chemin} : champ(s) inconnu(s) {sorted(inconnus)}")

    langues = _liste_de_textes(brut.get("langues", ["fr", "en"]), f"{chemin} : langues", erreurs)
    if set(langues) - LANGUES_CONNUES:
        erreurs.append(f"{chemin} : langues accepte seulement {sorted(LANGUES_CONNUES)}")

    consignes = brut.get("consignes") or ""
    if not isinstance(consignes, str):
        erreurs.append(f"{chemin} : consignes doit être un texte")
        consignes = ""

    sources_brutes = brut.get("sources")
    sources: list[Source] = []
    if not isinstance(sources_brutes, list) or not sources_brutes:
        erreurs.append(f"{chemin} : il faut au moins une source")
    else:
        for i, s in enumerate(sources_brutes):
            source = _valider_source(s, f"{chemin} : sources[{i + 1}]", erreurs)
            if source:
                sources.append(source)

    return Sujet(
        id=sid,
        nom=nom.strip(),
        actif=_booleen(brut.get("actif"), f"{chemin} : actif", True, erreurs),
        ordre=_entier_positif(brut.get("ordre"), f"{chemin} : ordre", erreurs),
        max_items=_entier_positif(brut.get("max_items"), f"{chemin} : max_items", erreurs),
        langues=langues,
        mots_cles=_liste_de_textes(brut.get("mots_cles"), f"{chemin} : mots_cles", erreurs),
        exclusions=_liste_de_textes(brut.get("exclusions"), f"{chemin} : exclusions", erreurs),
        mots_cles_alerte=_liste_de_textes(brut.get("mots_cles_alerte"), f"{chemin} : mots_cles_alerte", erreurs),
        consignes=consignes.strip(),
        sources=tuple(sources),
    )


def valider(donnees) -> Config:
    """Transforme le contenu YAML en `Config`, ou lève `ConfigInvalide` avec toutes les erreurs."""
    erreurs: list[str] = []
    if not isinstance(donnees, dict):
        raise ConfigInvalide(["le fichier doit contenir les blocs « modele » et « sujets »"])

    modele_brut = donnees.get("modele")
    modele = Modele(fournisseur="", nom="")
    if not isinstance(modele_brut, dict):
        erreurs.append("le bloc « modele » (fournisseur, nom) est manquant")
    else:
        fournisseur = modele_brut.get("fournisseur")
        nom = modele_brut.get("nom")
        if fournisseur not in FOURNISSEURS_CONNUS:
            erreurs.append(f"modele.fournisseur doit être l'un de {sorted(FOURNISSEURS_CONNUS)}")
        if not isinstance(nom, str) or not nom.strip():
            erreurs.append("modele.nom est manquant")
        else:
            modele = Modele(fournisseur=str(fournisseur), nom=nom.strip())

    sujets_bruts = donnees.get("sujets")
    sujets: list[Sujet] = []
    if not isinstance(sujets_bruts, list) or not sujets_bruts:
        erreurs.append("le bloc « sujets » doit contenir au moins un sujet")
    else:
        for i, brut in enumerate(sujets_bruts):
            sujet = _valider_sujet(brut, i, erreurs)
            if sujet:
                sujets.append(sujet)

    ids = [s.id for s in sujets]
    doublons = sorted({i for i in ids if ids.count(i) > 1})
    if doublons:
        erreurs.append(f"identifiant(s) de sujet en double : {doublons}")
    if sujets and not any(s.actif for s in sujets):
        erreurs.append("aucun sujet actif (actif: true)")

    if erreurs:
        raise ConfigInvalide(erreurs)
    return Config(modele=modele, sujets=tuple(sujets))


def lire(chemin: Path) -> Config:
    """Lit et valide un fichier `sujets.yaml`."""
    try:
        texte = chemin.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigInvalide([f"fichier illisible : {exc}"]) from exc
    try:
        donnees = yaml.safe_load(texte)
    except yaml.YAMLError as exc:
        position = getattr(exc, "problem_mark", None)
        ou = f" (ligne {position.line + 1}, colonne {position.column + 1})" if position else ""
        raise ConfigInvalide([f"syntaxe YAML incorrecte{ou} : {getattr(exc, 'problem', exc)}"]) from exc
    return valider(donnees)


def charger(chemin: Path, copie_valide: Path) -> tuple[Config, list[str]]:
    """Charge la configuration avec repli sur la dernière configuration valide (CFG-03).

    Renvoie la configuration retenue et la liste des erreurs détectées
    (vide si le fichier courant est valide). Si le fichier courant est valide,
    il est recopié dans `copie_valide`.
    """
    try:
        config = lire(chemin)
    except ConfigInvalide as exc:
        log.error("sujets.yaml refusé :\n- %s", "\n- ".join(exc.erreurs))
        if not copie_valide.exists():
            raise
        log.warning("Reprise de la dernière configuration valide : %s", copie_valide)
        return lire(copie_valide), exc.erreurs
    copie_valide.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(chemin, copie_valide)
    return config, []

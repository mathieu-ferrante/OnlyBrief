"""Validation de sujets.yaml (CFG-01 à CFG-05)."""

from pathlib import Path

import pytest
import yaml

from onlybrief.config import ConfigInvalide, charger, lire, valider

RACINE = Path(__file__).resolve().parents[2]

MINIMAL = {
    "modele": {"fournisseur": "gemini", "nom": "gemini-3.5-flash-lite"},
    "sujets": [{
        "id": "ia", "nom": "IA", "ordre": 1, "max_items": 5,
        "sources": [{"nom": "Blog", "flux": "https://exemple.fr/feed"}],
    }],
}


def copie(**modifs):
    donnees = yaml.safe_load(yaml.safe_dump(MINIMAL))
    donnees["sujets"][0].update(modifs)
    return donnees


def test_cfg01_le_fichier_du_depot_est_valide():
    config = lire(RACINE / "sujets.yaml")
    assert [s.id for s in config.sujets_actifs] == ["ia", "tech", "cs2"]
    assert config.modele.fournisseur == "gemini"


def test_cfg01_valeurs_par_defaut():
    sujet = valider(MINIMAL).sujets[0]
    assert sujet.actif is True
    assert sujet.mots_cles == () and sujet.exclusions == () and sujet.consignes == ""
    assert sujet.langues == ("fr", "en")


def test_cfg04_sujet_suspendu_et_ordre():
    donnees = copie(actif=False)
    donnees["sujets"].append({"id": "b", "nom": "B", "ordre": 2, "max_items": 3,
                              "sources": [{"nom": "S", "flux": "https://s.fr/rss"}]})
    donnees["sujets"].append({"id": "a", "nom": "A", "ordre": 1, "max_items": 3,
                              "sources": [{"nom": "S", "flux": "https://s.fr/rss"}]})
    config = valider(donnees)
    assert [s.id for s in config.sujets_actifs] == ["a", "b"]


def test_cfg05_consignes_et_mots_cles_alerte():
    sujet = valider(copie(consignes="pas en dessous du tier 2", mots_cles_alerte=["Major"])).sujets[0]
    assert sujet.consignes == "pas en dessous du tier 2"
    assert sujet.mots_cles_alerte == ("Major",)


@pytest.mark.parametrize("modifs, attendu", [
    ({"id": "IA Générative"}, "id"),
    ({"max_items": 0}, "max_items"),
    ({"max_items": "cinq"}, "max_items"),
    ({"actif": "oui"}, "actif"),
    ({"mots_cles": "LLM"}, "mots_cles"),
    ({"sources": []}, "au moins une source"),
    ({"sources": [{"nom": "S", "flux": "http://pas-https.fr"}]}, "https://"),
    ({"langues": ["de"]}, "langues"),
    ({"motscles": ["faute de frappe"]}, "inconnu"),
])
def test_cfg03_erreurs_detectees(modifs, attendu):
    with pytest.raises(ConfigInvalide) as exc:
        valider(copie(**modifs))
    assert any(attendu in e for e in exc.value.erreurs)


def test_cfg03_identifiants_en_double():
    donnees = copie()
    donnees["sujets"].append(dict(donnees["sujets"][0]))
    with pytest.raises(ConfigInvalide, match="double"):
        valider(donnees)


def test_cfg03_fournisseur_inconnu():
    donnees = copie()
    donnees["modele"]["fournisseur"] = "github-models"
    with pytest.raises(ConfigInvalide, match="fournisseur"):
        valider(donnees)


def test_cfg03_syntaxe_yaml_signalee_avec_ligne(tmp_path):
    fichier = tmp_path / "sujets.yaml"
    fichier.write_text("modele:\n  nom: x\nsujets:\n  - id: ia\n   nom: mal indenté\n", encoding="utf-8")
    with pytest.raises(ConfigInvalide, match="ligne"):
        lire(fichier)


def test_cfg03_repli_sur_derniere_config_valide(tmp_path):
    fichier = tmp_path / "sujets.yaml"
    sauvegarde = tmp_path / "etat" / "derniere_config_valide.yaml"
    fichier.write_text(yaml.safe_dump(MINIMAL, allow_unicode=True), encoding="utf-8")
    config, erreurs = charger(fichier, sauvegarde)
    assert erreurs == [] and sauvegarde.exists()

    fichier.write_text("sujets: [ceci n'est pas : valide", encoding="utf-8")
    config, erreurs = charger(fichier, sauvegarde)
    assert erreurs, "l'erreur doit être signalée"
    assert config.sujets[0].id == "ia", "la dernière configuration valide est reprise"
    assert "id: ia" in sauvegarde.read_text(encoding="utf-8"), "la sauvegarde n'est pas écrasée"


def test_cfg03_sans_sauvegarde_l_erreur_remonte(tmp_path):
    fichier = tmp_path / "sujets.yaml"
    fichier.write_text("rien: du tout", encoding="utf-8")
    with pytest.raises(ConfigInvalide):
        charger(fichier, tmp_path / "absente.yaml")

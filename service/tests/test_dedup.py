"""Déduplication et mémoire des liens sur 14 jours (COL-06)."""

from datetime import date

from onlybrief.dedup import LiensCites, dedoublonner, normaliser_lien


def test_normaliser_lien_retire_suivi_ancre_et_www():
    assert normaliser_lien("http://www.Exemple.fr/article/?utm_source=rss&id=3#commentaires") == \
        "https://exemple.fr/article?id=3"
    assert normaliser_lien("https://exemple.fr/a/") == normaliser_lien("https://exemple.fr/a")


def test_doublons_par_lien_et_par_titre(article):
    articles = [
        article(titre="Vitality remporte le Major", lien="https://hltv.org/1", source="HLTV.org"),
        article(titre="Vitality remporte le Major", lien="https://dexerto.fr/2", source="Dexerto.fr"),
        article(titre="Autre titre", lien="https://hltv.org/1?utm_medium=rss", source="HLTV.org"),
        article(titre="Une autre info", lien="https://hltv.org/3"),
    ]
    gardes, ecartes = dedoublonner(articles)
    assert [a.lien for a in gardes] == ["https://hltv.org/1", "https://hltv.org/3"]
    assert ecartes == 2
    assert gardes[0].autres_sources == ["Dexerto.fr"]


def test_col06_lien_cite_il_y_a_moins_de_14_jours(tmp_path, article):
    memoire = LiensCites(tmp_path / "liens_cites.json")
    memoire.enregistrer(["https://exemple.fr/a"], date(2026, 10, 1))
    memoire.sauvegarder()

    relue = LiensCites(tmp_path / "liens_cites.json")
    assert relue.deja_cite("https://www.exemple.fr/a/?utm_source=x", date(2026, 10, 15))
    assert not relue.deja_cite("https://exemple.fr/a", date(2026, 10, 16)), "au-delà de 14 jours, le lien est oublié"
    gardes, ecartes = relue.filtrer([article(lien="https://exemple.fr/a"), article(lien="https://exemple.fr/b")],
                                    date(2026, 10, 2))
    assert [a.lien for a in gardes] == ["https://exemple.fr/b"] and ecartes == 1


def test_col06_relancer_l_edition_du_jour_ne_la_vide_pas(tmp_path):
    memoire = LiensCites(tmp_path / "liens_cites.json")
    memoire.enregistrer(["https://exemple.fr/a"], date(2026, 10, 13))
    assert not memoire.deja_cite("https://exemple.fr/a", date(2026, 10, 13))
    memoire.enregistrer(["https://exemple.fr/b"], date(2026, 10, 13))
    assert set(memoire.liens) == {"https://exemple.fr/b"}, "l'édition du jour est remplacée, pas cumulée"


def test_col06_purge_des_liens_anciens(tmp_path):
    memoire = LiensCites(tmp_path / "liens_cites.json")
    memoire.enregistrer(["https://exemple.fr/vieux"], date(2026, 9, 1))
    memoire.enregistrer(["https://exemple.fr/neuf"], date(2026, 10, 13))
    assert set(memoire.liens) == {"https://exemple.fr/neuf"}


def test_etat_illisible_reinitialise(tmp_path):
    chemin = tmp_path / "liens_cites.json"
    chemin.write_text("{pas du json", encoding="utf-8")
    assert LiensCites(chemin).liens == {}

"""Lecture des flux RSS / Atom ; une source injoignable ne bloque rien (COL-02, COL-10)."""

import httpx

from onlybrief.collecte import collecter, texte_brut
from onlybrief.config import Source, Sujet

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Test</title>
<item><title>Vitality &amp; le Major</title><link>https://exemple.fr/1</link>
<pubDate>Tue, 13 Oct 2026 05:00:00 GMT</pubDate>
<description>&lt;p&gt;Un &lt;b&gt;chap\xc3\xb4&lt;/b&gt; en HTML.&lt;/p&gt;</description></item>
<item><title>Sans lien</title></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Blog</title>
<entry><title>Un billet</title><link href="https://blog.fr/billet"/>
<updated>2026-10-12T18:04:00+02:00</updated><summary>R\xc3\xa9sum\xc3\xa9</summary></entry>
</feed>"""


def sujet(*sources):
    return Sujet(id="t", nom="Test", ordre=1, max_items=5, sources=tuple(sources))


def transport(requete: httpx.Request) -> httpx.Response:
    if requete.url.host == "rss.fr":
        return httpx.Response(200, content=RSS)
    if requete.url.host == "atom.fr":
        return httpx.Response(200, content=ATOM)
    if requete.url.host == "panne.fr":
        raise httpx.ConnectError("connexion refusée")
    return httpx.Response(404)


def test_col02_rss_et_atom():
    client = httpx.Client(transport=httpx.MockTransport(transport))
    resultat = collecter([sujet(Source("RSS", "https://rss.fr/feed"), Source("Atom", "https://atom.fr/feed"))], client)
    assert [a.titre for a in resultat.articles] == ["Vitality & le Major", "Un billet"]
    rss, atom = resultat.articles
    assert rss.chapo == "Un chapô en HTML."
    assert rss.publie_le.isoformat() == "2026-10-13T05:00:00+00:00"
    assert atom.publie_le.isoformat() == "2026-10-12T16:04:00+00:00"
    assert atom.lien == "https://blog.fr/billet" and atom.source == "Atom"


def test_col10_source_injoignable_ou_404_signalee_sans_bloquer():
    client = httpx.Client(transport=httpx.MockTransport(transport))
    resultat = collecter([sujet(Source("Panne", "https://panne.fr/feed"), Source("Absent", "https://absent.fr/feed"),
                                Source("RSS", "https://rss.fr/feed"))], client)
    assert resultat.sources_en_echec == ["t/Panne", "t/Absent"]
    assert resultat.sources_lues == ["t/RSS"]
    assert len(resultat.articles) == 1
    assert "ConnectError" in resultat.erreurs["t/Panne"] and "404" in resultat.erreurs["t/Absent"]


def test_col10_contenu_qui_n_est_pas_un_flux():
    def html(requete):
        return httpx.Response(200, text="<html><body>Domaine à vendre</body></html>")
    client = httpx.Client(transport=httpx.MockTransport(html))
    resultat = collecter([sujet(Source("Parqué", "https://parque.fr/rss"))], client)
    assert resultat.sources_en_echec == ["t/Parqué"]


def test_texte_brut_tronque_proprement():
    texte = texte_brut("<p>" + "mot " * 200 + "</p>", 50)
    assert len(texte) <= 51 and texte.endswith("…") and "<" not in texte

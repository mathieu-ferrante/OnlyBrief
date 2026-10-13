package io.github.mathieuferrante.onlybrief.donnees

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Lecture des fichiers publiés (section 7). */
class LecteurTest {

    private val edition = """
        {
          "date": "2026-10-13",
          "publiee_le": "2026-10-13T07:30:00+02:00",
          "nb_items": 1,
          "resumes_degrades": false,
          "sections": [
            { "sujet_id": "ia", "nom": "IA / LLM", "sources_en_echec": [],
              "items": [ { "id": "ia-2026-10-13-01", "titre": "Titre", "resume": "Deux lignes.",
                           "pourquoi": "Une ligne.", "deja_signale": false, "source": "OpenAI News",
                           "lien": "https://openai.com/x", "publie_le": "2026-10-12T18:04:00+02:00",
                           "autres_sources": ["The Decoder"] } ] },
            { "sujet_id": "tech", "nom": "Tech générale", "sources_en_echec": ["Numerama"], "items": [] }
          ],
          "journal": { "champ": "inconnu de l'application" }
        }
    """.trimIndent()

    @Test
    fun lectureEditionSection72() {
        val e = Lecteur.edition(edition)
        assertEquals("2026-10-13", e.date)
        assertEquals(1, e.nbItems)
        assertEquals(listOf("ia", "tech"), e.sections.map { it.sujetId })
        val item = e.sections[0].items[0]
        assertEquals("Une ligne.", item.pourquoi)
        assertEquals(listOf("The Decoder"), item.autresSources)
        assertFalse(item.dejaSignale)
        assertTrue("APP-05 : section vide conservée", e.sections[1].items.isEmpty())
        assertEquals(listOf("Numerama"), e.sections[1].sourcesEnEchec)
    }

    @Test
    fun lectureIndexEtAlerte() {
        val index = Lecteur.index(
            """{"mis_a_jour_le":"2026-10-13T07:30:00+02:00","editions":[{"date":"2026-10-13","nb_items":12,"fichier":"editions/2026-10-13.json"}],"derniere_alerte":null}"""
        )
        assertEquals("editions/2026-10-13.json", index.editions.single().fichier)
        assertNull(index.derniereAlerte)
        val alerte = Lecteur.alerte(
            """{"date":"2026-10-13","emise_le":"2026-10-13T15:02:00+02:00","sujet_id":"ia","declencheur":"3 sources",
               "item":{"id":"alerte-2026-10-13","titre":"T","resume":"R","pourquoi":"P","source":"S","lien":"https://x","publie_le":"2026-10-13T14:50:00+02:00","autres_sources":["A","B"]}}"""
        )
        assertEquals(listOf("A", "B"), alerte.item.autresSources)
    }

    @Test
    fun lectureVersion() {
        val v = Lecteur.version("""{ "version": "1.0.0", "code": 10000, "apk": "https://github.com/x/onlybrief-1.0.0.apk" }""")
        assertEquals(10000, v.code)
    }

    @Test
    fun lectureDesEditionsReellementPubliees() {
        val fichiers = File("../docs/editions").listFiles { f -> f.name.endsWith(".json") }.orEmpty()
        fichiers.forEach { f ->
            val e = Lecteur.edition(f.readText())
            assertEquals(f.nameWithoutExtension, e.date)
            assertEquals(e.nbItems, e.sections.sumOf { it.items.size })
            e.sections.flatMap { it.items }.forEach { assertTrue("pourquoi présent : ${it.id}", it.pourquoi.isNotBlank()) }
        }
    }
}

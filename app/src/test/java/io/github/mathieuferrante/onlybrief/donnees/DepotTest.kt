package io.github.mathieuferrante.onlybrief.donnees

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException
import java.time.LocalDate

/** Stockage, purge et hors ligne (APP-07, APP-08, APP-09, APP-16, NF-06). */
class DepotTest {

    /** Base en mémoire, mêmes règles que les requêtes Room. */
    private class BaseMemoire : EditionsDao {
        val editions = MutableStateFlow<Map<String, EditionStockee>>(emptyMap())
        val alertes = MutableStateFlow<Map<String, AlerteStockee>>(emptyMap())
        override suspend fun enregistrer(edition: EditionStockee) { editions.value = editions.value + (edition.date to edition) }
        override suspend fun lire(date: String) = editions.value[date]
        override fun observer(date: String): Flow<EditionStockee?> = editions.map { it[date] }
        override fun observerDerniere(): Flow<EditionStockee?> = editions.map { m -> m.keys.maxOrNull()?.let { m[it] } }
        override fun observerHistorique(): Flow<List<ResumeEdition>> =
            editions.map { m -> m.values.sortedByDescending { it.date }.map { ResumeEdition(it.date, it.nbItems) } }
        override suspend fun dates() = editions.value.keys.toList()
        override suspend fun purger(garder: Int) {
            val gardees = editions.value.keys.sortedDescending().take(garder).toSet()
            editions.value = editions.value.filterKeys { it in gardees }
        }
        override suspend fun enregistrerAlerte(alerte: AlerteStockee) { alertes.value = alertes.value + (alerte.date to alerte) }
        override suspend fun lireAlerte(date: String) = alertes.value[date]
        override fun observerDerniereAlerte(): Flow<AlerteStockee?> = alertes.map { m -> m.keys.maxOrNull()?.let { m[it] } }
        override suspend fun purgerAlertes(garder: Int) {
            val gardees = alertes.value.keys.sortedDescending().take(garder).toSet()
            alertes.value = alertes.value.filterKeys { it in gardees }
        }
    }

    private class SiteFactice : Telechargeur {
        val fichiers = mutableMapOf<String, String>()
        val lus = mutableListOf<String>()
        var horsLigne = false
        override suspend fun lire(chemin: String): String {
            if (horsLigne) throw IOException("mode avion")
            lus += chemin
            return fichiers[chemin] ?: throw IOException("404 $chemin")
        }
    }

    private fun edition(date: String) =
        """{"date":"$date","publiee_le":"${date}T07:30:00+02:00","nb_items":1,"resumes_degrades":false,"sections":[{"sujet_id":"ia","nom":"IA","items":[]}]}"""

    private fun publier(site: SiteFactice, dates: List<String>, alerte: String? = null) {
        dates.forEach { site.fichiers["editions/$it.json"] = edition(it) }
        val entrees = dates.sortedDescending().joinToString(",") { """{"date":"$it","nb_items":1,"fichier":"editions/$it.json"}""" }
        val derniere = alerte?.let { """{"date":"$it","fichier":"alertes/$it.json"}""" } ?: "null"
        site.fichiers["index.json"] = """{"mis_a_jour_le":"","editions":[$entrees],"derniere_alerte":$derniere}"""
    }

    private fun jours(n: Int) = (1..n).map { LocalDate.of(2026, 9, 1).plusDays(it.toLong()).toString() }

    @Test
    fun telechargementPuisLectureHorsLigne() = runTest {
        val site = SiteFactice()
        val depot = Depot(BaseMemoire(), site)
        publier(site, listOf("2026-10-12", "2026-10-13"))
        assertEquals(ResultatActualisation.Succes(2), depot.actualiser())
        assertEquals("2026-10-13", depot.derniereEdition.first()?.date)

        site.horsLigne = true
        assertTrue(depot.actualiser() is ResultatActualisation.Echec)
        assertEquals("APP-08 : lisible hors ligne", "2026-10-12", depot.edition("2026-10-12").first()?.date)
        assertEquals(listOf("2026-10-13", "2026-10-12"), depot.historique.first().map { it.date })
    }

    @Test
    fun seuleLaPlusRecenteEstRelue() = runTest {
        val site = SiteFactice()
        val depot = Depot(BaseMemoire(), site)
        publier(site, listOf("2026-10-12", "2026-10-13"))
        depot.actualiser()
        site.lus.clear()
        depot.actualiser()
        assertEquals(listOf("index.json", "editions/2026-10-13.json"), site.lus)
    }

    @Test
    fun trenteDernieresEditionsConservees() = runTest {
        val site = SiteFactice()
        val depot = Depot(BaseMemoire(), site)
        val toutes = jours(45)
        publier(site, toutes.take(20)); depot.actualiser()
        publier(site, toutes); depot.actualiser()
        val historique = depot.historique.first()
        assertEquals(30, historique.size)
        assertEquals(toutes.last(), historique.first().date)
        assertEquals(toutes[15], historique.last().date)
    }

    @Test
    fun uneEditionIllisibleNeBloquePasLesAutres() = runTest {
        val site = SiteFactice()
        val depot = Depot(BaseMemoire(), site)
        publier(site, listOf("2026-10-12", "2026-10-13"))
        site.fichiers["editions/2026-10-12.json"] = "{ pas du json"
        assertTrue(depot.actualiser() is ResultatActualisation.Succes)
        assertNotNull(depot.edition("2026-10-13").first())
        assertNull(depot.edition("2026-10-12").first())
    }

    @Test
    fun alerteAfficheeJusquALEditionSuivante() = runTest {
        val site = SiteFactice()
        val depot = Depot(BaseMemoire(), site)
        publier(site, listOf("2026-10-13"), alerte = "2026-10-13")
        site.fichiers["alertes/2026-10-13.json"] =
            """{"date":"2026-10-13","emise_le":"2026-10-13T15:02:00+02:00","sujet_id":"ia","item":{"id":"alerte-2026-10-13","titre":"T","lien":"https://x"}}"""
        depot.actualiser()
        assertEquals("T", depot.alerteActive.first()?.item?.titre)

        publier(site, listOf("2026-10-13", "2026-10-14"), alerte = "2026-10-13")
        depot.actualiser()
        assertNull("APP-16 : l'édition du lendemain remplace le bandeau", depot.alerteActive.first())
    }
}

package io.github.mathieuferrante.onlybrief.donnees

import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.time.LocalDate

/** Requêtes Room réelles, à lancer sur téléphone ou émulateur (NF-06, APP-07). */
@RunWith(AndroidJUnit4::class)
class BaseTest {
    private lateinit var base: BaseOnlyBrief

    @Before
    fun ouvrir() {
        base = Room.inMemoryDatabaseBuilder(InstrumentationRegistry.getInstrumentation().targetContext, BaseOnlyBrief::class.java).build()
    }

    @After
    fun fermer() = base.close()

    @Test
    fun purgeEtHistorique() = runTest {
        val dao = base.editions()
        val dates = (0 until 35).map { LocalDate.of(2026, 10, 1).plusDays(it.toLong()).toString() }
        dates.forEach { dao.enregistrer(EditionStockee(it, "", 1, "{}")) }
        dao.purger(30)
        val historique = dao.observerHistorique().first().map { it.date }
        assertEquals(dates.takeLast(30).reversed(), historique)
    }
}

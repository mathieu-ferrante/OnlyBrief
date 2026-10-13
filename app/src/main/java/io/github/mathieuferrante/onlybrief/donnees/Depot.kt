package io.github.mathieuferrante.onlybrief.donnees

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerializationException
import okhttp3.CacheControl
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.time.OffsetDateTime
import java.util.concurrent.TimeUnit

/** Lecture d'un fichier publié sur GitHub Pages. */
fun interface Telechargeur {
    @Throws(IOException::class)
    suspend fun lire(chemin: String): String
}

class TelechargeurHttp(private val urlSite: String) : Telechargeur {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    override suspend fun lire(chemin: String): String = withContext(Dispatchers.IO) {
        val requete = Request.Builder()
            .url(urlSite + chemin)
            .cacheControl(CacheControl.FORCE_NETWORK)
            .build()
        client.newCall(requete).execute().use { reponse ->
            if (!reponse.isSuccessful) throw IOException("HTTP ${reponse.code} pour $chemin")
            reponse.body?.string() ?: throw IOException("réponse vide pour $chemin")
        }
    }
}

sealed interface ResultatActualisation {
    data class Succes(val nouvelles: Int) : ResultatActualisation
    data class Echec(val message: String) : ResultatActualisation
}

/**
 * Point d'accès unique aux éditions : lecture locale (Room) et téléchargement
 * depuis GitHub Pages. Les écrans n'affichent que ce qui est stocké, ce qui
 * garantit la lecture hors ligne (APP-08) et un affichage rapide (NF-02).
 */
class Depot(
    private val dao: EditionsDao,
    private val reseau: Telechargeur,
    private val garder: Int = EDITIONS_CONSERVEES,
) {
    private val verrou = Mutex()

    val derniereEdition: Flow<Edition?> = dao.observerDerniere().map { it?.let(::decoder) }
    val historique: Flow<List<ResumeEdition>> = dao.observerHistorique()

    fun edition(date: String): Flow<Edition?> = dao.observer(date).map { it?.let(::decoder) }

    /** APP-16 : l'alerte reste affichée jusqu'à l'édition suivante. */
    val alerteActive: Flow<Alerte?> = combine(dao.observerDerniereAlerte(), dao.observerDerniere()) { alerte, edition ->
        val a = alerte?.let { runCatching { Lecteur.alerte(it.contenu) }.getOrNull() } ?: return@combine null
        if (edition == null || plusRecent(a.emiseLe, edition.publieeLe)) a else null
    }

    /** Vérifie l'index, télécharge les éditions manquantes et l'alerte du jour (APP-09, NOT-04). */
    suspend fun actualiser(): ResultatActualisation = verrou.withLock {
        try {
            val index = Lecteur.index(reseau.lire("index.json"))
            var nouvelles = 0
            val aGarder = index.editions.sortedByDescending { it.date }.take(garder)
            aGarder.forEachIndexed { rang, entree ->
                val locale = dao.lire(entree.date)
                // La plus récente est toujours relue : le service peut l'avoir reconstruite.
                if (locale == null || rang == 0) {
                    val texte = reseau.lire(entree.fichier)
                    val edition = runCatching { Lecteur.edition(texte) }.getOrNull() ?: return@forEachIndexed
                    if (locale == null) nouvelles++
                    if (locale?.contenu != texte) {
                        dao.enregistrer(EditionStockee(edition.date, edition.publieeLe, edition.nbItems, texte))
                    }
                }
            }
            index.derniereAlerte?.let { entree ->
                if (dao.lireAlerte(entree.date) == null) {
                    val texte = reseau.lire(entree.fichier)
                    runCatching { Lecteur.alerte(texte) }.getOrNull()?.let {
                        dao.enregistrerAlerte(AlerteStockee(it.date, it.emiseLe, texte))
                    }
                }
            }
            dao.purger(garder)
            dao.purgerAlertes(ALERTES_CONSERVEES)
            ResultatActualisation.Succes(nouvelles)
        } catch (e: IOException) {
            ResultatActualisation.Echec("Pas de connexion au site des éditions")
        } catch (e: SerializationException) {
            ResultatActualisation.Echec("Index des éditions illisible")
        }
    }

    /** APP-15 : version publiée de l'application, ou null si inaccessible. */
    suspend fun versionPubliee(): Version? = try {
        Lecteur.version(reseau.lire("version.json"))
    } catch (e: IOException) {
        null
    } catch (e: SerializationException) {
        null
    }

    companion object {
        const val EDITIONS_CONSERVEES = 30
        const val ALERTES_CONSERVEES = 10

        private fun decoder(stockee: EditionStockee): Edition? = runCatching { Lecteur.edition(stockee.contenu) }.getOrNull()

        fun plusRecent(a: String, b: String): Boolean = try {
            OffsetDateTime.parse(a).isAfter(OffsetDateTime.parse(b))
        } catch (e: Exception) {
            a > b
        }
    }
}

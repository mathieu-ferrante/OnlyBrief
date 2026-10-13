package io.github.mathieuferrante.onlybrief.donnees

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

/**
 * Stockage local (section 9 : Room). Chaque édition est conservée telle que
 * publiée (JSON complet), ce qui permet la lecture hors ligne (APP-08, NF-03)
 * et rend l'application indépendante des évolutions du service.
 */
@Entity(tableName = "editions")
data class EditionStockee(
    @PrimaryKey val date: String,
    val publieeLe: String,
    val nbItems: Int,
    val contenu: String,
)

@Entity(tableName = "alertes")
data class AlerteStockee(
    @PrimaryKey val date: String,
    val emiseLe: String,
    val contenu: String,
)

/** Ligne de l'historique (APP-07). */
data class ResumeEdition(val date: String, val nbItems: Int)

@Dao
interface EditionsDao {
    @Upsert
    suspend fun enregistrer(edition: EditionStockee)

    @Query("SELECT * FROM editions WHERE date = :date")
    suspend fun lire(date: String): EditionStockee?

    @Query("SELECT * FROM editions WHERE date = :date")
    fun observer(date: String): Flow<EditionStockee?>

    @Query("SELECT * FROM editions ORDER BY date DESC LIMIT 1")
    fun observerDerniere(): Flow<EditionStockee?>

    @Query("SELECT date, nbItems FROM editions ORDER BY date DESC")
    fun observerHistorique(): Flow<List<ResumeEdition>>

    @Query("SELECT date FROM editions")
    suspend fun dates(): List<String>

    /** NF-06 : ne garder que les `garder` éditions les plus récentes. */
    @Query("DELETE FROM editions WHERE date NOT IN (SELECT date FROM editions ORDER BY date DESC LIMIT :garder)")
    suspend fun purger(garder: Int)

    @Upsert
    suspend fun enregistrerAlerte(alerte: AlerteStockee)

    @Query("SELECT * FROM alertes WHERE date = :date")
    suspend fun lireAlerte(date: String): AlerteStockee?

    @Query("SELECT * FROM alertes ORDER BY date DESC LIMIT 1")
    fun observerDerniereAlerte(): Flow<AlerteStockee?>

    @Query("DELETE FROM alertes WHERE date NOT IN (SELECT date FROM alertes ORDER BY date DESC LIMIT :garder)")
    suspend fun purgerAlertes(garder: Int)
}

@Database(entities = [EditionStockee::class, AlerteStockee::class], version = 1, exportSchema = true)
abstract class BaseOnlyBrief : RoomDatabase() {
    abstract fun editions(): EditionsDao

    companion object {
        fun ouvrir(context: Context): BaseOnlyBrief =
            Room.databaseBuilder(context, BaseOnlyBrief::class.java, "onlybrief.db").build()
    }
}

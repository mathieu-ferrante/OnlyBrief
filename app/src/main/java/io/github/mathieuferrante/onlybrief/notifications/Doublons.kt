package io.github.mathieuferrante.onlybrief.notifications

import android.content.Context

/**
 * NOT-05 : un même message (même type, même date) n'est affiché qu'une fois,
 * même si le service le renvoie. L'étiquette Android (`tag`) identique
 * complète ce garde-fou lorsque le système affiche lui-même la notification.
 */
object Doublons {
    private const val FICHIER = "notifications_recues"
    private const val CLE = "identifiants"
    private const val MAXIMUM = 60

    @Synchronized
    fun premiereFois(context: Context, identifiant: String): Boolean {
        val prefs = context.getSharedPreferences(FICHIER, Context.MODE_PRIVATE)
        val vus = prefs.getString(CLE, "").orEmpty().split(",").filter { it.isNotBlank() }
        if (identifiant in vus) return false
        val nouveaux = (vus + identifiant).takeLast(MAXIMUM)
        prefs.edit().putString(CLE, nouveaux.joinToString(",")).apply()
        return true
    }
}

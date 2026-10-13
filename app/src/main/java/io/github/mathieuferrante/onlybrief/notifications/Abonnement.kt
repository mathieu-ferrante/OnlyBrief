package io.github.mathieuferrante.onlybrief.notifications

import android.content.Context
import android.util.Log
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import io.github.mathieuferrante.onlybrief.BuildConfig

/**
 * Abonnement au sujet FCM « editions » : seule donnée envoyée depuis le
 * téléphone (NF-09). Sans configuration Firebase, l'application fonctionne
 * sans notifications.
 */
object Abonnement {
    const val SUJET = "editions"

    fun disponible(context: Context): Boolean =
        BuildConfig.AVEC_FIREBASE && FirebaseApp.getApps(context).isNotEmpty()

    fun abonner(context: Context) {
        if (!disponible(context)) {
            Log.i("OnlyBrief", "Firebase non configuré : notifications désactivées")
            return
        }
        FirebaseMessaging.getInstance().subscribeToTopic(SUJET)
            .addOnFailureListener { Log.w("OnlyBrief", "Abonnement au sujet impossible", it) }
    }
}

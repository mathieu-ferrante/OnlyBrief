package io.github.mathieuferrante.onlybrief

import android.app.Application
import io.github.mathieuferrante.onlybrief.donnees.BaseOnlyBrief
import io.github.mathieuferrante.onlybrief.donnees.Depot
import io.github.mathieuferrante.onlybrief.donnees.TelechargeurHttp
import io.github.mathieuferrante.onlybrief.notifications.Abonnement
import io.github.mathieuferrante.onlybrief.notifications.Canaux
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

class OnlyBriefApp : Application() {
    val base by lazy { BaseOnlyBrief.ouvrir(this) }
    val depot by lazy { Depot(base.editions(), TelechargeurHttp(BuildConfig.URL_SITE)) }

    /** Tâches courtes lancées hors écran (téléchargement à la réception d'une notification). */
    val portee = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        Canaux.creer(this)
        Abonnement.abonner(this)
    }
}

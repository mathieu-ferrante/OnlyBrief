package io.github.mathieuferrante.onlybrief.notifications

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import io.github.mathieuferrante.onlybrief.R

/** NOT-08 : deux canaux Android distincts, « Éditions » et « Alertes ». */
object Canaux {
    const val EDITIONS = "editions"
    const val ALERTES = "alertes"

    fun creer(context: Context) {
        val gestionnaire = context.getSystemService(NotificationManager::class.java)
        gestionnaire.createNotificationChannels(
            listOf(
                NotificationChannel(EDITIONS, context.getString(R.string.canal_editions), NotificationManager.IMPORTANCE_DEFAULT)
                    .apply { description = context.getString(R.string.canal_editions_description) },
                NotificationChannel(ALERTES, context.getString(R.string.canal_alertes), NotificationManager.IMPORTANCE_HIGH)
                    .apply { description = context.getString(R.string.canal_alertes_description) },
            )
        )
    }

    fun pour(type: String?): String = if (type == "alerte") ALERTES else EDITIONS
}

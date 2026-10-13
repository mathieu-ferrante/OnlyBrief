package io.github.mathieuferrante.onlybrief.notifications

import android.Manifest
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import io.github.mathieuferrante.onlybrief.MainActivity
import io.github.mathieuferrante.onlybrief.OnlyBriefApp
import io.github.mathieuferrante.onlybrief.R
import kotlinx.coroutines.launch

/**
 * Réception des messages FCM.
 *
 * Application en arrière-plan : Android affiche lui-même le bloc `notification`
 * (fiable même avec les restrictions de HyperOS) et ce service n'est pas appelé ;
 * l'édition est téléchargée à l'ouverture.
 * Application au premier plan : ce service affiche la notification et télécharge
 * l'édition tout de suite (NOT-04).
 */
class ServiceMessages : FirebaseMessagingService() {

    override fun onMessageReceived(message: RemoteMessage) {
        val type = message.data["type"] ?: return
        val date = message.data["date"] ?: return
        val identifiant = "$type-$date"
        if (!Doublons.premiereFois(this, identifiant)) return   // NOT-05
        val titre = message.notification?.title ?: "OnlyBrief"
        val texte = message.notification?.body ?: ""
        afficher(this, identifiant, type, date, titre, texte)
        (application as OnlyBriefApp).let { app -> app.portee.launch { app.depot.actualiser() } }
    }

    override fun onNewToken(token: String) {
        Abonnement.abonner(this)
    }

    companion object {
        const val EXTRA_TYPE = "type"
        const val EXTRA_DATE = "date"

        fun afficher(context: Context, identifiant: String, type: String, date: String, titre: String, texte: String) {
            if (Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
            ) return
            val ouverture = Intent(context, MainActivity::class.java)
                .putExtra(EXTRA_TYPE, type)
                .putExtra(EXTRA_DATE, date)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            val intention = PendingIntent.getActivity(
                context, identifiant.hashCode(), ouverture,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            val notification = NotificationCompat.Builder(context, Canaux.pour(type))
                .setSmallIcon(R.drawable.ic_notification)
                .setColor(ContextCompat.getColor(context, R.color.bleu))
                .setContentTitle(titre)
                .setContentText(texte)
                .setStyle(NotificationCompat.BigTextStyle().bigText(texte))
                .setContentIntent(intention)
                .setAutoCancel(true)
                .build()
            NotificationManagerCompat.from(context).notify(identifiant, 0, notification)
        }
    }
}

package io.github.mathieuferrante.onlybrief.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import io.github.mathieuferrante.onlybrief.BuildConfig
import io.github.mathieuferrante.onlybrief.donnees.Depot
import io.github.mathieuferrante.onlybrief.donnees.Version
import io.github.mathieuferrante.onlybrief.notifications.Abonnement

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun EcranAvecRetour(titre: String, onRetour: () -> Unit, contenu: @Composable (PaddingValues) -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(titre) },
                navigationIcon = {
                    IconButton(onClick = onRetour) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Retour") }
                },
            )
        },
        content = contenu,
    )
}

/** Détail d'un item : tout le contenu, les autres sources et le bouton vers l'article. */
@Composable
fun EcranDetail(depot: Depot, date: String, itemId: String, onRetour: () -> Unit) {
    val edition by remember(date) { depot.edition(date) }.collectAsState(initial = null)
    val trouve = edition?.sections?.firstNotNullOfOrNull { s -> s.items.firstOrNull { it.id == itemId }?.let { s to it } }
    val context = LocalContext.current
    EcranAvecRetour("Détail", onRetour) { marges ->
        Column(
            Modifier.fillMaxSize().padding(marges).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (trouve == null) {
                Text("Actualité introuvable.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                return@Column
            }
            val (section, item) = trouve
            Text(section.nom, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            if (item.dejaSignale) Pastille("Déjà signalée")
            Text(item.titre, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text(item.resume, style = MaterialTheme.typography.bodyLarge)
            LignePourquoi(item.pourquoi)
            LigneMeta("Source : ${item.source}")
            LigneMeta("Publié : ${Format.heurePublication(item.publieLe, "")}")
            if (item.autresSources.isNotEmpty()) LigneMeta("Également traité par : ${item.autresSources.joinToString(", ")}")
            LigneMeta("Édition du ${Format.jourComplet(date)}")
            Button(onClick = { ouvrirLien(context, item.lien) }, modifier = Modifier.fillMaxWidth()) {
                Text("Lire l'article")
            }
        }
    }
}

/** APP-07 : éditions passées, la plus récente en haut. */
@Composable
fun EcranHistorique(depot: Depot, onOuvrir: (String) -> Unit, onRetour: () -> Unit) {
    val editions by depot.historique.collectAsState(initial = emptyList())
    EcranAvecRetour("Historique", onRetour) { marges ->
        if (editions.isEmpty()) {
            Text(
                "Aucune édition enregistrée.",
                Modifier.padding(marges).padding(24.dp),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            LazyColumn(Modifier.fillMaxSize().padding(marges)) {
                items(editions, key = { it.date }) { e ->
                    Column(
                        Modifier.fillMaxWidth().clickable { onOuvrir(e.date) }.padding(horizontal = 16.dp, vertical = 14.dp)
                    ) {
                        Text(Format.jourComplet(e.date).replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.titleMedium)
                        Text(Format.nombre(e.nbItems), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    HorizontalDivider()
                }
                item {
                    Text(
                        "Les ${Depot.EDITIONS_CONSERVEES} dernières éditions sont conservées sur le téléphone et lisibles sans connexion.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(16.dp),
                    )
                }
            }
        }
    }
}

/** Réglages : version (APP-15), état des notifications et conseils HyperOS. */
@Composable
fun EcranReglages(depot: Depot, onRetour: () -> Unit) {
    val context = LocalContext.current
    var versionPubliee by remember { mutableStateOf<Version?>(null) }
    var verifiee by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        versionPubliee = depot.versionPubliee()
        verifiee = true
    }
    val notificationsAutorisees = Build.VERSION.SDK_INT < 33 ||
        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    EcranAvecRetour("Réglages", onRetour) { marges ->
        Column(
            Modifier.fillMaxSize().padding(marges).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Version", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("OnlyBrief ${BuildConfig.VERSION_NAME}")
                    val v = versionPubliee
                    when {
                        !verifiee -> LigneMeta("Recherche d'une mise à jour…")
                        v == null -> LigneMeta("Impossible de vérifier les mises à jour (pas de connexion ?)")
                        v.code > BuildConfig.VERSION_CODE -> {
                            Text("Une version plus récente est disponible : ${v.version}", color = MaterialTheme.colorScheme.primary)
                            if (v.apk.isNotBlank()) Button(onClick = { ouvrirLien(context, v.apk) }) { Text("Télécharger la version ${v.version}") }
                        }
                        else -> LigneMeta("Vous avez la dernière version.")
                    }
                }
            }
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Notifications", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text(
                        when {
                            !Abonnement.disponible(context) -> "Service de notification non configuré dans cette version."
                            notificationsAutorisees -> "Autorisées : édition à 7 h 30 en semaine, 10 h le week-end, et au plus une alerte par jour."
                            else -> "Refusées : vous ne serez pas prévenu des nouvelles éditions."
                        }
                    )
                    OutlinedButton(onClick = {
                        context.startActivity(
                            Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
                        )
                    }) { Text("Réglages des notifications") }
                }
            }
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Recevoir les notifications à l'heure (HyperOS)", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("Dans les paramètres du téléphone, sur la fiche de l'application OnlyBrief :")
                    Text("• activez « Démarrage automatique » ;")
                    Text("• dans « Économiseur de batterie », choisissez « Aucune restriction ».")
                    OutlinedButton(onClick = {
                        context.startActivity(
                            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, android.net.Uri.fromParts("package", context.packageName, null))
                        )
                    }) { Text("Ouvrir la fiche de l'application") }
                }
            }
            Text(
                "OnlyBrief ne crée aucun compte et n'envoie aucune donnée depuis le téléphone, hormis l'abonnement aux notifications.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

package io.github.mathieuferrante.onlybrief

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import io.github.mathieuferrante.onlybrief.donnees.Depot
import io.github.mathieuferrante.onlybrief.notifications.ServiceMessages
import io.github.mathieuferrante.onlybrief.ui.EcranDetail
import io.github.mathieuferrante.onlybrief.ui.EcranEdition
import io.github.mathieuferrante.onlybrief.ui.EcranHistorique
import io.github.mathieuferrante.onlybrief.ui.EcranReglages
import io.github.mathieuferrante.onlybrief.ui.theme.OnlyBriefTheme
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch

/** Cible demandée par une notification (NOT-03). */
data class Cible(val type: String, val date: String)

class MainActivity : ComponentActivity() {
    private val cible = MutableStateFlow<Cible?>(null)
    private val depot: Depot get() = (application as OnlyBriefApp).depot

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (savedInstanceState == null) lireIntention(intent)
        setContent {
            OnlyBriefTheme {
                DemandeNotifications()
                Navigation(depot, cible.collectAsState().value) { cible.value = null }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        lireIntention(intent)
    }

    override fun onResume() {
        super.onResume()
        // NOT-04 : à défaut d'avoir été téléchargée à la réception, l'édition l'est à l'ouverture.
        lifecycleScope.launch { depot.actualiser() }
    }

    private fun lireIntention(intent: Intent?) {
        val type = intent?.getStringExtra(ServiceMessages.EXTRA_TYPE) ?: return
        val date = intent.getStringExtra(ServiceMessages.EXTRA_DATE) ?: return
        cible.value = Cible(type, date)
        intent.removeExtra(ServiceMessages.EXTRA_TYPE)
    }
}

/** NOT-06 : au premier lancement, demander l'autorisation d'afficher des notifications (Android 13+). */
@Composable
private fun DemandeNotifications() {
    if (Build.VERSION.SDK_INT < 33) return
    val context = androidx.compose.ui.platform.LocalContext.current
    val lanceur = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
    LaunchedEffect(Unit) {
        val prefs = context.getSharedPreferences("premier_lancement", Context.MODE_PRIVATE)
        val accordee = ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        if (!accordee && !prefs.getBoolean("notifications_demandees", false)) {
            prefs.edit().putBoolean("notifications_demandees", true).apply()
            lanceur.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
}

@Composable
private fun Navigation(depot: Depot, cible: Cible?, onCibleTraitee: () -> Unit) {
    val nav = rememberNavController()

    LaunchedEffect(cible) {
        if (cible == null) return@LaunchedEffect
        // Une alerte s'affiche en bandeau sur l'édition du jour (APP-16) ; une édition s'ouvre à sa date.
        val route = if (cible.type == "edition") "edition?date=${cible.date}" else "edition"
        nav.navigate(route) { popUpTo("edition") { inclusive = true } }
        onCibleTraitee()
    }

    NavHost(nav, startDestination = "edition") {
        composable(
            "edition?date={date}",
            arguments = listOf(navArgument("date") { type = NavType.StringType; nullable = true; defaultValue = null }),
        ) { entree ->
            val date = entree.arguments?.getString("date")
            EcranEdition(
                depot = depot,
                date = date,
                onDetail = { d, id -> nav.navigate("detail/$d/$id") },
                onHistorique = { nav.navigate("historique") },
                onReglages = { nav.navigate("reglages") },
                onRetour = if (nav.previousBackStackEntry != null) ({ nav.popBackStack() }) else null,
            )
        }
        composable("detail/{date}/{item}") { entree ->
            EcranDetail(depot, entree.arguments!!.getString("date")!!, entree.arguments!!.getString("item")!!) { nav.popBackStack() }
        }
        composable("historique") {
            EcranHistorique(depot, onOuvrir = { nav.navigate("edition?date=$it") }, onRetour = { nav.popBackStack() })
        }
        composable("reglages") {
            EcranReglages(depot) { nav.popBackStack() }
        }
    }
}

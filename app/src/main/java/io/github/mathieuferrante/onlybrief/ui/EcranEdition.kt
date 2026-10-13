package io.github.mathieuferrante.onlybrief.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import io.github.mathieuferrante.onlybrief.donnees.Alerte
import io.github.mathieuferrante.onlybrief.donnees.Depot
import io.github.mathieuferrante.onlybrief.donnees.Edition
import io.github.mathieuferrante.onlybrief.donnees.Item
import io.github.mathieuferrante.onlybrief.donnees.ResultatActualisation
import io.github.mathieuferrante.onlybrief.donnees.Section
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.launch

/**
 * Édition du jour (APP-01) ou édition passée (APP-07) : sections repliables
 * (APP-02), items (APP-03, APP-04), section vide (APP-05), sources en échec
 * (APP-06), tirer pour actualiser (APP-09), bandeau d'alerte (APP-16).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EcranEdition(
    depot: Depot,
    date: String?,
    onDetail: (date: String, itemId: String) -> Unit,
    onHistorique: () -> Unit,
    onReglages: () -> Unit,
    onRetour: (() -> Unit)?,
) {
    val flux = remember(date) { if (date == null) depot.derniereEdition else depot.edition(date) }
    val edition by flux.collectAsState(initial = null)
    val derniere by depot.derniereEdition.collectAsState(initial = null)
    val alerte by (if (date == null) depot.alerteActive else flowOf(null)).collectAsState(initial = null)
    var actualisation by remember { mutableStateOf(false) }
    var chargementInitial by remember { mutableStateOf(true) }
    val messages = remember { SnackbarHostState() }
    val portee = rememberCoroutineScope()

    fun actualiser(manuel: Boolean) {
        portee.launch {
            actualisation = manuel
            val resultat = depot.actualiser()
            actualisation = false
            chargementInitial = false
            if (manuel) {
                messages.showSnackbar(
                    when (resultat) {
                        is ResultatActualisation.Succes ->
                            if (resultat.nouvelles > 0) "Nouvelle édition téléchargée" else "Vous êtes à jour"
                        is ResultatActualisation.Echec -> "${resultat.message} : les éditions enregistrées restent lisibles"
                    }
                )
            }
        }
    }

    // Une édition annoncée par notification mais pas encore téléchargée (NOT-03, NOT-04).
    LaunchedEffect(date) { actualiser(manuel = false) }

    val estDerniere = date == null || date == derniere?.date
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("OnlyBrief", fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary) },
                navigationIcon = {
                    if (onRetour != null) IconButton(onClick = onRetour) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Retour")
                    }
                },
                actions = {
                    IconButton(onClick = onHistorique) { Icon(Icons.AutoMirrored.Filled.List, contentDescription = "Historique") }
                    IconButton(onClick = onReglages) { Icon(Icons.Default.Settings, contentDescription = "Réglages") }
                },
            )
        },
        snackbarHost = { SnackbarHost(messages) },
    ) { marges ->
        PullToRefreshBox(
            isRefreshing = actualisation,
            onRefresh = { actualiser(manuel = true) },
            modifier = Modifier.fillMaxSize().padding(marges),
        ) {
            val e = edition
            if (e == null) {
                EtatVide(chargement = chargementInitial || date != null)
            } else {
                ContenuEdition(e, if (estDerniere) alerte else null, estDerniere, onDetail)
            }
        }
    }
}

@Composable
private fun EtatVide(chargement: Boolean) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(24.dp)) {
        item {
            Text(
                if (chargement) "Téléchargement de l'édition…"
                else "Aucune édition enregistrée pour l'instant.\nTirez vers le bas pour vérifier si une édition est disponible.",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ContenuEdition(edition: Edition, alerte: Alerte?, estDerniere: Boolean, onDetail: (String, String) -> Unit) {
    val ouvertes = rememberSaveable(edition.date) { mutableStateOf(edition.sections.map { it.sujetId }.toSet()) }
    val context = LocalContext.current
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item(key = "titre") {
            Column {
                Text(Format.titreEdition(edition.date), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text(
                    Format.nombre(edition.nbItems) + if (!estDerniere) " · édition passée" else "",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        if (alerte != null) {
            item(key = "alerte") {
                Card(
                    onClick = { ouvrirLien(context, alerte.item.lien) },
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer,
                        contentColor = MaterialTheme.colorScheme.onTertiaryContainer,
                    ),
                ) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Alerte", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
                        Text(alerte.item.titre, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        Text(alerte.item.resume, style = MaterialTheme.typography.bodyMedium)
                        Text("Pourquoi c'est important : ${alerte.item.pourquoi}", style = MaterialTheme.typography.bodyMedium)
                        Text(
                            listOf(alerte.item.source, Format.heurePublication(alerte.emiseLe, alerte.date))
                                .filter { it.isNotBlank() }.joinToString(" · "),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        }
        if (edition.resumesDegrades) {
            item(key = "degrade") {
                Bandeau(
                    "Résumés automatiques indisponibles pour une partie de l'édition : l'extrait fourni par la source est affiché à la place.",
                    MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        items(edition.sections, key = { it.sujetId }) { section ->
            CarteSection(
                section = section,
                dateEdition = edition.date,
                ouverte = section.sujetId in ouvertes.value,
                onBasculer = {
                    ouvertes.value = if (section.sujetId in ouvertes.value) ouvertes.value - section.sujetId
                    else ouvertes.value + section.sujetId
                },
                onOuvrir = { ouvrirLien(context, it.lien) },
                onDetail = { onDetail(edition.date, it.id) },
            )
        }
    }
}

@Composable
private fun CarteSection(
    section: Section,
    dateEdition: String,
    ouverte: Boolean,
    onBasculer: () -> Unit,
    onOuvrir: (Item) -> Unit,
    onDetail: (Item) -> Unit,
) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Row(
            Modifier
                .fillMaxWidth()
                .clickable(role = Role.Button, onClickLabel = if (ouverte) "Replier" else "Déplier", onClick = onBasculer)
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(section.nom, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            Text("${section.items.size}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.width(8.dp))
            Icon(
                if (ouverte) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        AnimatedVisibility(ouverte) {
            Column {
                if (section.items.isEmpty()) {
                    HorizontalDivider()
                    Text(
                        "Rien de notable aujourd'hui",
                        style = MaterialTheme.typography.bodyMedium,
                        fontStyle = FontStyle.Italic,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(16.dp),
                    )
                }
                section.items.forEach { item ->
                    HorizontalDivider()
                    LigneItem(item, dateEdition, onOuvrir = { onOuvrir(item) }, onDetail = { onDetail(item) })
                }
                if (section.sourcesEnEchec.isNotEmpty()) {
                    HorizontalDivider()
                    Text(
                        "Source injoignable lors de la collecte : " + section.sourcesEnEchec.joinToString(", "),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun LigneItem(item: Item, dateEdition: String, onOuvrir: () -> Unit, onDetail: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClickLabel = "Ouvrir l'article dans le navigateur", onClick = onOuvrir)
            .padding(start = 16.dp, top = 12.dp, bottom = 12.dp, end = 4.dp),
    ) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            if (item.dejaSignale) Pastille("Déjà signalée")
            Text(item.titre, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(item.resume, style = MaterialTheme.typography.bodyMedium)
            LignePourquoi(item.pourquoi)
            LigneMeta(
                listOf(item.source, Format.heurePublication(item.publieLe, dateEdition))
                    .filter { it.isNotBlank() }.joinToString(" · ")
            )
        }
        Box(Modifier.padding(top = 0.dp)) {
            IconButton(onClick = onDetail) {
                Icon(Icons.Default.Info, contentDescription = "Détail de l'actualité", tint = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

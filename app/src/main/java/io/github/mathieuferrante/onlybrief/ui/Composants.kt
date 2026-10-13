package io.github.mathieuferrante.onlybrief.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp

/** APP-04 : ouvre l'article dans le navigateur du téléphone. */
fun ouvrirLien(context: Context, lien: String) {
    try {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(lien)))
    } catch (e: Exception) {
        Toast.makeText(context, "Aucun navigateur pour ouvrir ce lien", Toast.LENGTH_SHORT).show()
    }
}

@Composable
fun Bandeau(texte: String, fond: Color, couleurTexte: Color, modifier: Modifier = Modifier, titre: String? = null) {
    Surface(color = fond, contentColor = couleurTexte, shape = RoundedCornerShape(12.dp), modifier = modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            if (titre != null) Text(titre, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
            Text(texte, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
fun LignePourquoi(pourquoi: String) {
    Surface(
        color = MaterialTheme.colorScheme.secondaryContainer,
        contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
        shape = RoundedCornerShape(topEnd = 8.dp, bottomEnd = 8.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            buildAnnotatedString {
                withStyle(SpanStyle(fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)) {
                    append("Pourquoi c'est important : ")
                }
                append(pourquoi)
            },
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
        )
    }
}

@Composable
fun Pastille(texte: String) {
    Surface(
        color = MaterialTheme.colorScheme.tertiaryContainer,
        contentColor = MaterialTheme.colorScheme.onTertiaryContainer,
        shape = RoundedCornerShape(6.dp),
    ) {
        Text(texte, style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
    }
}

@Composable
fun LigneMeta(texte: String, modifier: Modifier = Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        Text(texte, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

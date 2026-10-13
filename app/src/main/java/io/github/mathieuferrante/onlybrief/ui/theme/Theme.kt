package io.github.mathieuferrante.onlybrief.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Couleur principale bleue (section 11, identité). Contrastes vérifiés AA (NF-10).
private val Clair = lightColorScheme(
    primary = Color(0xFF1D5FD1),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE7FD),
    onPrimaryContainer = Color(0xFF0B2A63),
    secondaryContainer = Color(0xFFE6EFFF),
    onSecondaryContainer = Color(0xFF123E8C),
    tertiaryContainer = Color(0xFFFFE9C7),
    onTertiaryContainer = Color(0xFF5C3600),
    background = Color(0xFFF5F7FB),
    surface = Color(0xFFFFFFFF),
    surfaceVariant = Color(0xFFE8ECF3),
    onSurfaceVariant = Color(0xFF475266),
)

private val Sombre = darkColorScheme(
    primary = Color(0xFF8FB5FF),
    onPrimary = Color(0xFF0B2A63),
    primaryContainer = Color(0xFF1C3B74),
    onPrimaryContainer = Color(0xFFDCE7FD),
    secondaryContainer = Color(0xFF1D2A42),
    onSecondaryContainer = Color(0xFFC9D9FA),
    tertiaryContainer = Color(0xFF4A3410),
    onTertiaryContainer = Color(0xFFFFDDA8),
    background = Color(0xFF10151D),
    surface = Color(0xFF19202B),
    surfaceVariant = Color(0xFF242C39),
    onSurfaceVariant = Color(0xFFAAB4C5),
)

/** Suit le thème clair ou sombre du téléphone ; la taille de police du système est respectée (NF-10). */
@Composable
fun OnlyBriefTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (isSystemInDarkTheme()) Sombre else Clair, content = content)
}

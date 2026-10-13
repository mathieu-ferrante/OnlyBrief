package io.github.mathieuferrante.onlybrief.ui

import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Mise en forme des dates en français. */
object Format {
    private val jourLong = DateTimeFormatter.ofPattern("EEEE d MMMM", Locale.FRENCH)
    private val jourAnnee = DateTimeFormatter.ofPattern("EEEE d MMMM yyyy", Locale.FRENCH)
    private val heure = DateTimeFormatter.ofPattern("HH:mm", Locale.FRENCH)
    private val jourHeure = DateTimeFormatter.ofPattern("EEE d MMM, HH:mm", Locale.FRENCH)

    /** « mardi 13 octobre » */
    fun jour(date: String): String = runCatching { LocalDate.parse(date).format(jourLong) }.getOrDefault(date)

    /** « mardi 13 octobre 2026 » */
    fun jourComplet(date: String): String = runCatching { LocalDate.parse(date).format(jourAnnee) }.getOrDefault(date)

    /** « Veille du mardi 13 octobre » (NOT-02, APP-01) */
    fun titreEdition(date: String): String = "Veille du ${jour(date)}"

    fun nombre(nb: Int): String = if (nb > 1) "$nb actualités" else "$nb actualité"

    /** Heure de publication d'un article : « 18:04 » le jour même, sinon « lun. 12 oct., 18:04 ». */
    fun heurePublication(instant: String, dateEdition: String): String = runCatching {
        val local = OffsetDateTime.parse(instant).atZoneSameInstant(ZoneId.systemDefault())
        if (local.toLocalDate().toString() == dateEdition) local.format(heure) else local.format(jourHeure)
    }.getOrDefault("")
}

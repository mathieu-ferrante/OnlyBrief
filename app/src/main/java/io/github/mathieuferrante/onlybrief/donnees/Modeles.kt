package io.github.mathieuferrante.onlybrief.donnees

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/*
 * Fichiers publiés par le service (section 7 du cahier des charges).
 * Les champs inconnus sont ignorés : le service peut ajouter des informations
 * (par exemple « journal ») sans nouvelle version de l'application.
 */

val JsonOnlyBrief = Json {
    ignoreUnknownKeys = true
    coerceInputValues = true
    explicitNulls = false
}

@Serializable
data class Index(
    @SerialName("mis_a_jour_le") val misAJourLe: String = "",
    val editions: List<EntreeIndex> = emptyList(),
    @SerialName("derniere_alerte") val derniereAlerte: EntreeAlerte? = null,
)

@Serializable
data class EntreeIndex(
    val date: String,
    @SerialName("nb_items") val nbItems: Int = 0,
    val fichier: String,
)

@Serializable
data class EntreeAlerte(val date: String, val fichier: String)

@Serializable
data class Edition(
    val date: String,
    @SerialName("publiee_le") val publieeLe: String = "",
    @SerialName("nb_items") val nbItems: Int = 0,
    @SerialName("resumes_degrades") val resumesDegrades: Boolean = false,
    val sections: List<Section> = emptyList(),
)

@Serializable
data class Section(
    @SerialName("sujet_id") val sujetId: String,
    val nom: String,
    @SerialName("sources_en_echec") val sourcesEnEchec: List<String> = emptyList(),
    val items: List<Item> = emptyList(),
)

@Serializable
data class Item(
    val id: String,
    val titre: String,
    val resume: String = "",
    val pourquoi: String = "",
    @SerialName("deja_signale") val dejaSignale: Boolean = false,
    val source: String = "",
    val lien: String,
    @SerialName("publie_le") val publieLe: String = "",
    @SerialName("autres_sources") val autresSources: List<String> = emptyList(),
)

@Serializable
data class Alerte(
    val date: String,
    @SerialName("emise_le") val emiseLe: String,
    @SerialName("sujet_id") val sujetId: String = "",
    val item: Item,
)

@Serializable
data class Version(
    val version: String,
    val code: Int,
    val apk: String = "",
)

object Lecteur {
    fun index(texte: String): Index = JsonOnlyBrief.decodeFromString(texte)
    fun edition(texte: String): Edition = JsonOnlyBrief.decodeFromString(texte)
    fun alerte(texte: String): Alerte = JsonOnlyBrief.decodeFromString(texte)
    fun version(texte: String): Version = JsonOnlyBrief.decodeFromString(texte)
}

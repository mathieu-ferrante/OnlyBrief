# Modèles JSON (kotlinx.serialization) : les règles sont fournies par la bibliothèque.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keep,includedescriptorclasses class io.github.mathieuferrante.onlybrief.donnees.**$$serializer { *; }
-keepclassmembers class io.github.mathieuferrante.onlybrief.donnees.** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}

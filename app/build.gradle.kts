import java.util.Properties

// Application Android OnlyBrief — projet Gradle à un seul module (section 9).
plugins {
    id("com.android.application") version "8.7.0"
    id("org.jetbrains.kotlin.android") version "2.0.21"
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21"
    id("org.jetbrains.kotlin.plugin.serialization") version "2.0.21"
    id("com.google.devtools.ksp") version "2.0.21-1.0.27"
    id("com.google.gms.google-services") version "4.4.2" apply false
}

// Firebase (notifications) n'est branché que si google-services.json est présent :
// sans lui, l'application se construit et fonctionne, sans notifications.
val avecFirebase = file("google-services.json").exists()
if (avecFirebase) apply(plugin = "com.google.gms.google-services")

// Signature de la version publiée : variables d'environnement (GitHub Actions)
// ou fichier local signature.properties (jamais commité).
val signature = Properties().apply {
    val fichier = file("signature.properties")
    if (fichier.exists()) fichier.inputStream().use { load(it) }
}
fun reglage(cle: String, variable: String): String? = System.getenv(variable) ?: signature.getProperty(cle)

android {
    namespace = "io.github.mathieuferrante.onlybrief"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.mathieuferrante.onlybrief"
        minSdk = 26
        targetSdk = 35
        versionCode = (findProperty("onlybrief.versionCode") as String).toInt()
        versionName = findProperty("onlybrief.versionName") as String
        buildConfigField("String", "URL_SITE", "\"https://mathieu-ferrante.github.io/OnlyBrief/\"")
        buildConfigField("boolean", "AVEC_FIREBASE", avecFirebase.toString())
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        val magasin = reglage("magasin", "ONLYBRIEF_KEYSTORE_FILE")
        if (magasin != null) {
            create("publication") {
                storeFile = file(magasin)
                storePassword = reglage("motDePasseMagasin", "ONLYBRIEF_KEYSTORE_PASSWORD")
                keyAlias = reglage("alias", "ONLYBRIEF_KEY_ALIAS")
                keyPassword = reglage("motDePasseCle", "ONLYBRIEF_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("publication")
        }
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-essai"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
    testOptions { unitTests.isReturnDefaultValues = true }
}

ksp { arg("room.schemaLocation", "$projectDir/schemas") }

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.01.00")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.navigation:navigation-compose:2.8.4")

    implementation("androidx.room:room-runtime:2.7.0")
    implementation("androidx.room:room-ktx:2.7.0")
    ksp("androidx.room:room-compiler:2.7.0")

    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")

    implementation(platform("com.google.firebase:firebase-bom:33.7.0"))
    implementation("com.google.firebase:firebase-messaging")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.room:room-testing:2.7.0")
    androidTestImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
}

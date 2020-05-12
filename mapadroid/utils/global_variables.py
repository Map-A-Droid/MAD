# This file is to specify any globals / magic-numbers used throughout MAD

# MAD APK related elements
CHUNK_MAX_SIZE = 1024 * 1024 * 8  # 8MiB
MAD_APK_USAGE_POGO = 0
MAD_APK_USAGE_RGC = 1
MAD_APK_USAGE_PD = 2
MAD_APK_USAGE = {
    'pogo': MAD_APK_USAGE_POGO,
    'rgc': MAD_APK_USAGE_RGC,
    'pogodroid': MAD_APK_USAGE_PD,
    'com.nianticlabs.pokemongo': MAD_APK_USAGE_POGO,
    'de.grennith.rgc.remotegpscontroller': MAD_APK_USAGE_RGC,
    'com.mad.pogodroid': MAD_APK_USAGE_PD,
}
MAD_APK_ARCH_NOARCH = 0
MAD_APK_ARCH_ARMEABI_V7A = 1
MAD_APK_ARCH_ARM64_V8A = 2
MAD_APK_ARCH = {
    'noarch': MAD_APK_ARCH_NOARCH,
    'armeabi-v7a': MAD_APK_ARCH_ARMEABI_V7A,
    'arm64-v8a': MAD_APK_ARCH_ARM64_V8A,
}
MAD_APK_ALLOWED_EXTENSIONS = set(['apk'])
URL_POGO_APK = 'https://www.apkmirror.com/wp-content/themes/APKMirror/download.php?id=%s'
URL_POGO_APK_ARMEABI_V7A = 'https://www.apkmirror.com/apk/niantic-inc/pokemon-go/variant-%7B%22arches_slug%22%3A%5B%22armeabi-v7a%22%5D%7D/'
URL_POGO_APK_ARM64_V8A = 'https://www.apkmirror.com/apk/niantic-inc/pokemon-go/variant-%7B%22arches_slug%22%3A%5B%22arm64-v8a%22%5D%7D/'
URL_RGC_APK = 'https://raw.githubusercontent.com/Map-A-Droid/MAD/master/APK/RemoteGpsController.apk'
URL_PD_APK = 'https://www.maddev.de/apk/PogoDroid.apk'

ADDRESSES_GITHUB = 'https://raw.githubusercontent.com/Map-A-Droid/MAD/master/configs/addresses.json'

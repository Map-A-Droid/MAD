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
# Configured devices can be found @
# https://github.com/NoMore201/googleplay-api/blob/664c399f8196e1eb7d2fcda4af34e5dc1fca0f20/gpapi/device.properties
MAD_APK_SEARCH = {
    MAD_APK_ARCH_ARMEABI_V7A: 'hammerhead',  # Nexus 5
    MAD_APK_ARCH_ARM64_V8A: 'angler'  # Nexus 6p
}
MAD_APK_ALLOWED_EXTENSIONS = set(['apk', 'zip'])
URL_RGC_APK = 'https://raw.githubusercontent.com/Map-A-Droid/MAD/master/APK/RemoteGpsController.apk'
URL_PD_APK = 'https://www.maddev.de/apk/PogoDroid.apk'

ADDRESSES_GITHUB = 'https://raw.githubusercontent.com/Map-A-Droid/MAD/master/configs/addresses.json'

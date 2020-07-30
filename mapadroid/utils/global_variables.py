# This file is to specify any globals / magic-numbers used throughout MAD

# MAD APK related elements
CHUNK_MAX_SIZE = 1024 * 1024 * 8  # 8MiB
# Configured devices can be found @
# https://github.com/NoMore201/googleplay-api/blob/664c399f8196e1eb7d2fcda4af34e5dc1fca0f20/gpapi/device.properties
MAD_APK_ALLOWED_EXTENSIONS = set(['apk', 'zip'])
URL_RGC_APK = 'https://raw.githubusercontent.com/Map-A-Droid/MAD/master/APK/RemoteGpsController.apk'
URL_PD_APK = 'https://www.maddev.de/apk/PogoDroid.apk'

ADDRESSES_GITHUB = 'https://raw.githubusercontent.com/Map-A-Droid/MAD/master/configs/addresses.json'

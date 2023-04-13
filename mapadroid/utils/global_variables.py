# This file is to specify any globals / magic-numbers used throughout MAD

# MAD APK related elements
CHUNK_MAX_SIZE = 1024 * 1024 * 8  # 8MiB
MAD_APK_ALLOWED_EXTENSIONS = {'apk', 'zip'}
URL_RGC_APK = 'https://raw.githubusercontent.com/Map-A-Droid/MAD/async/APK/RemoteGpsController.apk'
URL_PD_APK = 'https://www.maddev.eu/apk/PogoDroid_async.apk'
BACKEND_SUPPORTED_VERSIONS = "https://auth.maddev.eu/thirdparty/supported_versions"

VERSIONCODES_URL = 'https://raw.githubusercontent.com/Map-A-Droid/MAD/master/configs/version_codes.json'

MAINTENANCE_COOLDOWN_HOURS = 24
# Min level 8 since incidents will only be tracked from level 8 onwards
MIN_LEVEL_RAID = 8
# IV are the same for all at 30 and above
MIN_LEVEL_IV = 30
# Speed can be 60 km/h up to distances of 3km
QUEST_WALK_SPEED_CALCULATED = 16.67

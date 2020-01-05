# This file is to specify any globals / magic-numbers used throughout MAD
CHUNK_MAX_SIZE = 1024 * 1024 * 8 # 8MiB
MAD_APK_USAGE_POGO = 0
MAD_APK_USAGE_RGC = 1
MAD_APK_USAGE_PD = 2
MAD_APK_USAGE = {
    'pogo': MAD_APK_USAGE_POGO,
    'rgc': MAD_APK_USAGE_RGC,
    'pogodroid': MAD_APK_USAGE_PD,
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
from enum import Enum


class APK_Arch(Enum):
    noarch = 0
    armeabi_v7a = 1
    arm64_v8a = 2


class APK_Package(Enum):
    pd = 'com.mad.pogodroid'
    pogo = 'com.nianticlabs.pokemongo'
    rgc = 'de.grennith.rgc.remotegpscontroller'


class APK_Type(Enum):
    pogo = 0
    rgc = 1
    pd = 2


class Device_Codename(Enum):
    armeabi_v7a = 'hammerhead'
    arm64_v8a = 'angler'

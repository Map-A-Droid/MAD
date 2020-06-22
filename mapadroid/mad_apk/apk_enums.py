from enum import Enum, IntEnum


class APK_Arch(IntEnum):
    noarch: int = 0
    armeabi_v7a: int = 1
    arm64_v8a: int = 2


class APK_Package(Enum):
    pd = 'com.mad.pogodroid'
    pogo = 'com.nianticlabs.pokemongo'
    rgc = 'de.grennith.rgc.remotegpscontroller'


class APK_Type(IntEnum):
    pogo: int = 0
    rgc: int = 1
    pd: int = 2


class Device_Codename(Enum):
    armeabi_v7a: str = 'hammerhead'
    arm64_v8a: str = 'angler'

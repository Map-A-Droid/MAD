from enum import Enum, IntEnum


class APKArch(IntEnum):
    noarch: int = 0
    armeabi_v7a: int = 1
    arm64_v8a: int = 2


class APKPackage(Enum):
    pd = 'com.mad.pogodroid'
    pogo = 'com.nianticlabs.pokemongo'
    rgc = 'de.grennith.rgc.remotegpscontroller'


class APKType(IntEnum):
    pogo: int = 0
    rgc: int = 1
    pd: int = 2


class DeviceCodename(Enum):
    armeabi_v7a: str = 'hammerhead'
    arm64_v8a: str = 'angler'

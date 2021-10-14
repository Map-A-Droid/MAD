from enum import Enum, IntEnum


class APKArch(IntEnum):
    noarch = 0
    armeabi_v7a = 1
    arm64_v8a = 2


class APKPackage(Enum):
    pd = 'com.mad.pogodroid'
    pogo = 'com.nianticlabs.pokemongo'
    rgc = 'de.grennith.rgc.remotegpscontroller'


class APKType(IntEnum):
    pogo = 0
    rgc = 1
    pd = 2


class DeviceCodename(Enum):
    armeabi_v7a = 'hammerhead'
    arm64_v8a = 'angler'

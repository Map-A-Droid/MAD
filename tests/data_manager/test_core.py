import pytest

from mapadroid.data_manager import dm_exceptions, modules


def test_get_resource_class(data_manager):
    assert data_manager.get_resource_def("area_nomode") == modules.Area
    assert data_manager.get_resource_def("area", mode="idle") == modules.area_idle.AreaIdle
    assert data_manager.get_resource_def("area", mode="iv_mitm") == modules.area_iv_mitm.AreaIVMITM
    assert data_manager.get_resource_def("area", mode="mon_mitm") == modules.area_mon_mitm.AreaMonMITM
    assert data_manager.get_resource_def("area", mode="pokestops") == modules.area_pokestops.AreaPokestops
    assert data_manager.get_resource_def("area", mode="raids_mitm") == modules.area_raids_mitm.AreaRaidsMITM
    assert data_manager.get_resource_def("device") == modules.Device
    assert data_manager.get_resource_def("devicepool") == modules.DevicePool
    assert data_manager.get_resource_def("geofence") == modules.GeoFence
    assert data_manager.get_resource_def("monivlist") == modules.MonIVList
    assert data_manager.get_resource_def("pogoauth") == modules.PogoAuth
    assert data_manager.get_resource_def("routecalc") == modules.RouteCalc
    assert data_manager.get_resource_def("walker") == modules.Walker
    assert data_manager.get_resource_def("walkerarea") == modules.WalkerArea
    assert data_manager.get_resource_def("area_nomode") == modules.Area


def test_get_resource_invalid(data_manager):
    with pytest.raises(dm_exceptions.UnknownIdentifier):
        data_manager.get_resource("device", 1)

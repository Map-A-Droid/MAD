import copy

import pytest

from mapadroid.data_manager.modules import PogoAuth, Walker, area_pokestops
from mapadroid.data_manager.modules.resource import ResourceTracker


def get_resource_tracker(data_manager, resource, section, populate_defaults=False, initial_data=None):
    defaults = {}
    if populate_defaults:
        for field, default_value in resource.configuration[section].items():
            try:
                defaults[field] = default_value['settings']['empty']
            except KeyError:
                continue
    elif initial_data:
        defaults = initial_data
    return ResourceTracker(copy.deepcopy(resource.configuration[section]), data_manager, initialdata=defaults)


@pytest.mark.usefixtures("data_manager")
def test_check_known_key(data_manager):
    tracker = get_resource_tracker(data_manager, PogoAuth, "fields")
    assert not tracker.check_known_key("asdf")
    assert "asdf" in tracker.issues["unknown"]
    assert tracker.check_known_key("username")
    assert "username" not in tracker.issues["unknown"]


@pytest.mark.usefixtures("data_manager")
def test_get_lookups(data_manager):
    tracker = get_resource_tracker(data_manager, PogoAuth, "fields")
    expected = {
        "expected": str,
        "required": True,
        "resource": None,
        "has_empty": False,
        "empty": None
    }
    assert tracker.get_lookups("login_type") == expected
    tracker = get_resource_tracker(data_manager, PogoAuth, "fields")
    expected = {
        "expected": int,
        "required": False,
        "resource": "device",
        "has_empty": True,
        "empty": None
    }
    assert tracker.get_lookups("device_id") == expected
    tracker = get_resource_tracker(data_manager, area_pokestops.AreaPokestops, "fields")
    expected = {
        "expected": str,
        "required": True,
        "resource": None,
        "has_empty": False,
        "empty": None
    }
    assert tracker.get_lookups("name") == expected
    tracker = get_resource_tracker(data_manager, area_pokestops.AreaPokestops, "fields")
    expected = {
        "expected": bool,
        "required": True,
        "resource": None,
        "has_empty": True,
        "empty": False
    }
    assert tracker.get_lookups("init") == expected
    tracker = get_resource_tracker(data_manager, Walker, "fields")
    expected = {
        "expected": list,
        "required": True,
        "has_empty": True,
        "empty": [],
        "resource": "walkerarea"
    }
    assert tracker.get_lookups("setup") == expected


def test_format_value():
    assert ResourceTracker.format_value("True", bool)
    assert not ResourceTracker.format_value("False", bool)
    with pytest.raises(ValueError):
        assert ResourceTracker.format_value("something", bool)
    with pytest.raises(ValueError):
        assert ResourceTracker.format_value(None, bool)
    assert ResourceTracker.format_value("1", bool)
    assert ResourceTracker.format_value(1, bool)
    assert not ResourceTracker.format_value("0", bool)
    assert not ResourceTracker.format_value(0, bool)
    assert ResourceTracker.format_value(0, float) == 0.0
    assert ResourceTracker.format_value(0.0, float) == 0.0
    assert ResourceTracker.format_value("0", float) == 0.0
    assert ResourceTracker.format_value(1.1, float) == 1.1
    assert ResourceTracker.format_value("1.1", float) == 1.1
    assert ResourceTracker.format_value(0, int) == 0
    assert ResourceTracker.format_value(0.0, int) == 0
    assert ResourceTracker.format_value("0", int) == 0
    assert ResourceTracker.format_value(1.1, int) == 1
    assert ResourceTracker.format_value("1", int) == 1
    assert ResourceTracker.format_value("test", str) == "test"
    assert ResourceTracker.format_value("test ", str) == "test"
    assert ResourceTracker.format_value(" test ", str) == "test"


@pytest.mark.usefixtures("data_manager")
def test_process_format_value(data_manager):
    tracker = get_resource_tracker(data_manager, PogoAuth, "fields")
    lookups = {
        "expected": str,
        "required": True,
        "has_empty": False,
        "empty": None
    }
    assert tracker.process_format_value(lookups, "login_type", "ptc") == "ptc"
    lookups = {
        "expected": str,
        "required": True,
        "has_empty": False,
        "empty": None
    }
    assert tracker.process_format_value(lookups, "login_type", "ptc2") == "ptc2"
    lookups = {
        "expected": str,
        "required": True,
        "has_empty": True,
        "empty": "empty val"
    }
    assert tracker.process_format_value(lookups, "login_type", None) == lookups["empty"]
    lookups = {
        "expected": str,
        "required": False,
        "has_empty": False,
        "empty": None
    }
    assert tracker.process_format_value(lookups, "login_type", None) is None
    lookups = {
        "expected": bool,
        "required": True,
        "has_empty": False,
        "empty": None
    }
    with pytest.raises(ValueError):
        tracker.process_format_value(lookups, "login_type", "f")
    assert tracker.issues["invalid"][0][0] == "login_type"
    with pytest.raises(ValueError):
        tracker.process_format_value(lookups, "login_type", None)
    assert tracker.issues["invalid"][1][0] == "login_type"
    tracker = get_resource_tracker(data_manager, Walker, "fields")
    lookups = {
        "expected": list,
        "required": True,
        "has_empty": True,
        "empty": []
    }
    assert tracker.process_format_value(lookups, "setup", None) == []


@pytest.mark.usefixtures("data_manager")
def test_check_required(data_manager):
    tracker = get_resource_tracker(data_manager, PogoAuth, "fields")
    lookups = {
        "required": True,
        "has_empty": True,
        "empty": 1
    }
    assert tracker.check_required(lookups, "test", "True")
    lookups = {
        "required": False,
        "has_empty": True,
        "empty": 1
    }
    assert tracker.check_required(lookups, "test", "True")
    lookups = {
        "required": True,
        "has_empty": False,
    }
    assert not tracker.check_required(lookups, "test", "")
    assert "test" in tracker.issues["missing"]
    lookups = {
        "required": False,
        "has_empty": True,
        "empty": 1
    }
    assert tracker.check_required(lookups, "test", None)


@pytest.mark.usefixtures("data_manager")
def test_check_dependencies(data_manager):
    tracker = get_resource_tracker(data_manager, area_pokestops.AreaPokestops, "fields")
    routecalc = {
        "routecalc_id": 1,
        "routefile": "[]",
        "recalc_status": 0
    }
    lookups = {
        "resource": "routecalc"
    }
    data_manager.dbc.autofetch_row.return_value = routecalc
    tracker.check_dependencies(lookups, "routecalc", 1)
    tracker.check_dependencies(lookups, "routecalc", [1, 2])
    data_manager.dbc.autofetch_row.return_value = None
    tracker.check_dependencies(lookups, "routecalc", 1)
    assert tracker.issues["invalid_uri"][0] == ("routecalc", "routecalc", 1)
    tracker = get_resource_tracker(data_manager, area_pokestops.AreaPokestops, "fields")
    tracker.check_dependencies(lookups, "routecalc", [1, 2])
    assert tracker.issues["invalid_uri"][0] == ("routecalc", "routecalc", 1)
    assert tracker.issues["invalid_uri"][1] == ("routecalc", "routecalc", 2)


@pytest.mark.usefixtures("data_manager")
@pytest.mark.parametrize("populate_defaults", [True, False])
def test_driver_pogoauth(data_manager, populate_defaults):
    tracker = get_resource_tracker(data_manager, PogoAuth, "fields", populate_defaults=populate_defaults)
    expected = sorted(PogoAuth.configuration["fields"].keys())
    expected.remove("device_id")
    assert expected == sorted(tracker.issues["missing"])
    tracker["login_type"] = "ptc"
    expected.remove("login_type")
    assert expected == sorted(tracker.issues["missing"])
    tracker["username"] = "ptc"
    expected.remove("username")
    assert expected == sorted(tracker.issues["missing"])
    tracker["password"] = "ptc"
    expected.remove("password")
    assert expected == sorted(tracker.issues["missing"])


@pytest.mark.usefixtures("data_manager")
def test_driver(data_manager):
    tracker = get_resource_tracker(data_manager, Walker, "fields", populate_defaults=True)
    assert "setup" not in tracker.issues["missing"]
    tracker["setup"] = None
    assert "setup" not in tracker.issues["missing"]
    assert tracker["setup"] == []


@pytest.mark.usefixtures("data_manager")
def test_load(data_manager):
    routecalc = {
        "login_type": "ptc",
        "username": "test_user",
        "password": "test_pwd",
        "device_id": None,
    }
    tracker = get_resource_tracker(data_manager, PogoAuth, "fields", initial_data=routecalc)
    assert len(tracker.issues["invalid"]) == 0
    assert len(tracker.issues["missing"]) == 0
    assert len(tracker.issues["invalid_uri"]) == 0
    assert len(tracker.issues["unknown"]) == 0

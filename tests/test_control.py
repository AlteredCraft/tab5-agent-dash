from dash.control import action


def test_no_action_when_nothing_changed():
    assert action({"restart": 100, "off": 0}, {"restart": 100, "off": 0}) is None
    assert action({}, {}) is None


def test_newer_request_triggers_its_action():
    assert action({"restart": 100, "off": 0}, {"restart": 150, "off": 0}) == "restart"
    assert action({"restart": 100, "off": 0}, {"restart": 100, "off": 160}) == "off"


def test_power_off_wins_over_restart():
    assert action({}, {"restart": 5, "off": 6}) == "off"


def test_restarted_collector_triggers_nothing():
    assert action({"restart": 100, "off": 90}, {"restart": 0, "off": 0}) is None
    assert action({"restart": 100}, {}) is None

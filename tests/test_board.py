import pytest
import serial

from tools import deploy
from tools.board import Board, BoardError


class FakeSerial:
    """Answers the raw REPL request only from the `ready_on`-th connection attempt."""

    attempts = 0

    def __init__(self, ready_on):
        self.ready_on = ready_on
        self.pending = b""

    def write(self, data):
        if data == b"\r\x01":
            FakeSerial.attempts += 1
            if FakeSerial.attempts >= self.ready_on:
                self.pending = b"raw REPL; CTRL-B to exit\r\n>"

    def read(self, size):
        data, self.pending = self.pending, b""
        return data

    def close(self):
        pass


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    FakeSerial.attempts = 0
    monkeypatch.setattr(Board, "QUIET", 0.01)
    monkeypatch.setattr("tools.board.time.sleep", lambda seconds: None)


def test_board_keeps_trying_while_the_device_starts_up():
    Board("port", wait=30, open_serial=lambda *a, **k: FakeSerial(ready_on=3))
    assert FakeSerial.attempts == 3


def test_board_retries_when_the_port_is_not_there_yet():
    calls = []

    def open_serial(*args, **kwargs):
        calls.append(1)
        if len(calls) < 3:
            raise serial.SerialException("no such port")
        return FakeSerial(ready_on=1)

    Board("port", wait=30, open_serial=open_serial)
    assert len(calls) == 3


def test_board_gives_up_with_advice():
    with pytest.raises(BoardError) as error:
        Board("/dev/cu.test", wait=0, open_serial=lambda *a, **k: FakeSerial(ready_on=99))
    message = str(error.value)
    assert "/dev/cu.test" in message and "make ports" in message


def test_deploy_rejects_a_bad_wifi_file_before_touching_the_device(tmp_path, monkeypatch):
    monkeypatch.setattr(deploy, "Board", lambda port, **kwargs: pytest.fail("connected to the device"))
    wifi = tmp_path / "wifi.env"
    wifi.write_text("WIFI_NAME=home\n")
    monkeypatch.setattr("sys.argv", ["deploy", "--wifi-env", str(wifi), "--url", "http://mac.local:8787/usage.json"])
    with pytest.raises(SystemExit) as stopped:
        deploy.main()
    assert "WIFI_NAME=... and WIFI_PASSWORD=..." in str(stopped.value)

    monkeypatch.setattr("sys.argv", ["deploy", "--wifi-env", str(tmp_path / "missing.env"), "--url", "http://x/"])
    with pytest.raises(SystemExit) as stopped:
        deploy.main()
    assert "not found" in str(stopped.value)


def test_deploy_reports_an_unreachable_board_without_a_traceback(monkeypatch):
    def refuse(port, **kwargs):
        raise BoardError("The Tab5 on %s did not answer" % port)

    monkeypatch.setattr(deploy, "Board", refuse)
    monkeypatch.setattr(deploy, "ask_over_wifi", lambda action: False)
    monkeypatch.setattr("sys.argv", ["deploy", "--port", "/dev/cu.test"])
    with pytest.raises(SystemExit) as stopped:
        deploy.main()
    assert str(stopped.value) == "The Tab5 on /dev/cu.test did not answer"


def test_deploy_asks_for_a_restart_over_wifi_when_usb_is_silent(monkeypatch, capsys):
    attempts, asked = [], []

    def board(port, wait):
        attempts.append(wait)
        if len(attempts) == 1:
            raise BoardError("silent")
        return "connected"

    monkeypatch.setattr(deploy, "Board", board)
    monkeypatch.setattr(deploy, "ask_over_wifi", lambda action: asked.append(action) or True)
    assert deploy.connect("/dev/cu.test") == "connected"
    assert asked == ["restart"] and len(attempts) == 2
    assert "restart over Wi-Fi" in capsys.readouterr().out

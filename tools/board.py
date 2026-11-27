"""Talk to the Tab5's MicroPython raw REPL over USB.

mpremote does not work with UIFlow2: the firmware drops USB on a soft reset
and prints from background timers during the handshake. This never soft
resets and ignores stray output.
"""

import binascii
import os
import time
import urllib.request

import serial

CHUNK = 3072


class BoardError(Exception):
    pass


def ask_over_wifi(action, collector_port=8787):
    """Ask the running collector to pass "restart" or "off" to the Tab5 on its
    next poll. Returns False when no collector is running here."""
    request = urllib.request.Request("http://127.0.0.1:%d/control/%s" % (collector_port, action), method="POST")
    try:
        urllib.request.urlopen(request, timeout=3).close()
        return True
    except OSError:
        return False


class Board:
    QUIET = 0.6

    def __init__(self, port, wait=30, open_serial=serial.Serial):
        """Connect and enter the raw REPL, retrying for `wait` seconds: the
        Tab5 ignores the interrupt while it starts up, and its USB port comes
        and goes around a restart."""
        if open_serial is serial.Serial and not os.path.exists(port):
            raise BoardError("There is no serial port %s. `make ports` lists the ones the Mac can see." % port)
        deadline = time.time() + wait
        self._conn = None
        while True:
            try:
                if self._conn is None:
                    self._conn = open_serial(port, 115200, timeout=0.1)
                if self._enter_raw_repl():
                    return
            except (serial.SerialException, OSError):
                self._drop()
            if time.time() >= deadline:
                self._drop()
                raise BoardError(
                    "The Tab5 on %s did not answer within %d seconds.\n"
                    "  - Press the reset button on the Tab5, or switch it off and on, with USB connected.\n"
                    "  - Close any other program using the port (a serial monitor, the UIFlow web editor).\n"
                    "  - Check `make ports`: with several boards attached, pass PORT=..." % (port, wait)
                )
            time.sleep(1)

    def _enter_raw_repl(self):
        self._conn.write(b"\r\x03")
        time.sleep(0.3)
        self._conn.write(b"\x03")
        self._drain()
        self._conn.write(b"\r\x01")
        return b"raw REPL" in self._drain()

    def _drop(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except (serial.SerialException, OSError):
                pass
            self._conn = None

    def _drain(self, quiet=None, limit=15):
        quiet = self.QUIET if quiet is None else quiet
        data = b""
        last = start = time.time()
        while time.time() - last < quiet and time.time() - start < limit:
            chunk = self._conn.read(4096)
            if chunk:
                data += chunk
                last = time.time()
        return data

    def run(self, code, timeout=60):
        """Execute code and return what it printed. Raises BoardError on a traceback."""
        data = code.encode()
        for i in range(0, len(data), 512):
            self._conn.write(data[i : i + 512])
            time.sleep(0.01)
        self._conn.write(b"\x04")
        received = b""
        start = time.time()
        while received.count(b"\x04") < 2:
            if time.time() - start > timeout:
                raise BoardError("timed out; output so far: %r" % received[-300:])
            received += self._conn.read(4096)
        stdout, _, rest = received.partition(b"\x04")
        stderr = rest.partition(b"\x04")[0]
        self._conn.read_until(b">")
        if stderr.strip():
            raise BoardError(stderr.decode(errors="replace"))
        return stdout.split(b"OK", 1)[-1].decode(errors="replace")

    def write_file(self, path, data):
        self.run("import binascii\n_f = open(%r, 'wb')" % path)
        for i in range(0, len(data), CHUNK):
            encoded = binascii.b2a_base64(data[i : i + CHUNK]).decode().strip()
            self.run("_f.write(binascii.a2b_base64(%r))" % encoded)
        self.run("_f.close()")

    def close(self):
        self._conn.write(b"\x02")
        self._conn.close()

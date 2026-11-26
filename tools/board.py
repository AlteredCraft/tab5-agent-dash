"""Talk to the Tab5's MicroPython raw REPL over USB.

mpremote does not work with UIFlow2: the firmware drops USB on a soft reset
and prints from background timers during the handshake. This never soft
resets and ignores stray output.
"""

import binascii
import time

import serial

CHUNK = 3072


class BoardError(Exception):
    pass


class Board:
    def __init__(self, port):
        self._conn = serial.Serial(port, 115200, timeout=0.1)
        self._conn.write(b"\r\x03")
        time.sleep(0.3)
        self._conn.write(b"\x03")
        self._drain()
        self._conn.write(b"\r\x01")
        if b"raw REPL" not in self._drain():
            raise BoardError("the board did not enter the raw REPL; it may still be starting up")

    def _drain(self, quiet=0.6, limit=15):
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

"""A tiny synthesiser for the theme-selection sounds, shared by the device and the Mac.

A theme's SOUND is a tuple of notes, each (start_ms, length_ms, from_hz, to_hz, wave, level):
the pitch slides linearly from from_hz to to_hz, wave is one of WAVES, and level is
0-100. Each note rises in 3 ms and then decays to silence by its end. wav() mixes the
notes into a 16-bit mono WAV, which the device plays with M5.Speaker.playWav.

The inner loop keeps every value below 2**30, MicroPython's small-integer range:
floats and larger integers are allocated on the heap.
"""

import struct
from array import array
from math import exp, log, pi, sin

RATE = 16000
TABLE_BITS = 8
TABLE_SIZE = 1 << TABLE_BITS
PEAK = 32767
ATTACK_MS = 3
ENV_BITS = 15
ENV_ONE = 1 << ENV_BITS
PHASE_BITS = 16
# The decay is applied every 16 samples: applied every sample, the multiplier is so
# close to 1 that rounding down ends long notes early.
ENV_STRIDE = 16

WAVES = {
    "sine": tuple(int(PEAK * sin(2 * pi * i / TABLE_SIZE)) for i in range(TABLE_SIZE)),
    "triangle": tuple(
        int(PEAK * (4 * i / TABLE_SIZE - 1 if i < TABLE_SIZE // 2 else 3 - 4 * i / TABLE_SIZE)) for i in range(TABLE_SIZE)
    ),
    "square": tuple(PEAK if i < TABLE_SIZE // 2 else -PEAK for i in range(TABLE_SIZE)),
    "noise": None,
}


def _note(mix, start_ms, length_ms, from_hz, to_hz, wave, level):
    start = RATE * start_ms // 1000
    count = min(RATE * length_ms // 1000, len(mix) - start)
    if count <= 0:
        return
    attack = max(1, RATE * ATTACK_MS // 1000)
    # Phase is a fixed-point index into the table; step is added each sample.
    scale = TABLE_SIZE << PHASE_BITS
    step = scale * from_hz // RATE
    slide = (scale * to_hz // RATE - step) // count
    # Exponential decay to about -60 dB over the note, as a multiplier per ENV_STRIDE samples.
    decay = int(ENV_ONE * exp(log(0.001) * ENV_STRIDE / max(1, count - attack)))
    stride = ENV_STRIDE - 1
    table = WAVES[wave]
    mask = TABLE_SIZE - 1
    wrap = scale - 1
    noise = 1
    phase = 0
    env = 0
    for i in range(count):
        if table is None:
            noise = (noise * 75 + 74) % 65537
            value = noise - 32768
        else:
            value = table[(phase >> PHASE_BITS) & mask]
        if i < attack:
            env = ENV_ONE * i // attack
        elif not i & stride:
            env = env * decay >> ENV_BITS
        mix[start + i] += (value * env >> ENV_BITS) * level // 100
        phase = (phase + step) & wrap
        step += slide


def wav(notes):
    """The notes mixed into the bytes of a 16-bit mono WAV file at RATE."""
    length_ms = max(note[0] + note[1] for note in notes)
    mix = array("i", [0] * (RATE * length_ms // 1000))
    for note in notes:
        _note(mix, *note)
    samples = array("h", (max(-PEAK, min(PEAK, value)) for value in mix))
    data = bytes(samples)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(data), b"WAVE",
        b"fmt ", 16, 1, 1, RATE, RATE * 2, 2, 16,
        b"data", len(data),
    )
    return header + data


_cache = {}


def for_theme(theme):
    """The theme's WAV bytes, built on first use. Keep the result alive while it plays:
    the speaker reads the buffer in the background."""
    data = _cache.get(theme.NAME)
    if data is None:
        data = _cache[theme.NAME] = wav(theme.SOUND)
    return data

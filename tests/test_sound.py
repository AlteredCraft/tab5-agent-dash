import io
import wave
from array import array

import pytest

from dash import sound
from dash.themes import THEMES


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.NAME)
def test_theme_sound_is_a_short_audible_wav(theme):
    with wave.open(io.BytesIO(sound.wav(theme.SOUND))) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, sound.RATE)
        assert 0.1 < w.getnframes() / sound.RATE < 1.5
        samples = array("h", w.readframes(w.getnframes()))
    peak = max(abs(s) for s in samples)
    assert 4000 < peak < sound.PEAK, "audible without clipping"
    assert abs(samples[-1]) < 200, "ends near silence, without a click"


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.NAME)
def test_theme_sound_notes_are_valid(theme):
    for start, length, from_hz, to_hz, wave_name, level in theme.SOUND:
        assert start >= 0 and length > 0
        assert wave_name in sound.WAVES
        assert 0 < level <= 100
        assert 0 <= from_hz < sound.RATE // 2 and 0 <= to_hz < sound.RATE // 2


def test_sweep_reaches_its_target_pitch():
    data = sound.wav(((0, 500, 400, 1600, "square", 100),))
    samples = array("h", data[44:])
    # 300-350 ms in, the pitch slides from 1120 to 1240 Hz.
    window = samples[4800:5600]
    crossings = sum((a < 0) != (b < 0) for a, b in zip(window, window[1:]))
    assert crossings / 2 / (len(window) / sound.RATE) == pytest.approx(1180, rel=0.05)


def test_sounds_are_distinct_and_cached():
    assert len({sound.wav(t.SOUND) for t in THEMES}) == len(THEMES)
    assert sound.for_theme(THEMES[0]) is sound.for_theme(THEMES[0])

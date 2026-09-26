#!/usr/bin/env python3
"""
generate_sounds.py
==================

Synthesizes every drum sample used by the game and writes them to ../sounds/
as 16-bit mono WAV files.

Why synthesize instead of downloading?
--------------------------------------
Because every sample is generated mathematically from sine waves and random
noise by this script, the audio is 100% original work. There is no third-party
recording involved, so there are no copyright or licensing concerns at all.
The generated files are dedicated to the public domain (CC0 1.0) — see
sounds/LICENSE.md.

Usage:
    python3 tools/generate_sounds.py

Only the Python standard library is required (no numpy needed).
"""

import math
import os
import random
import struct
import wave

SAMPLE_RATE = 44100  # CD-quality sample rate
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sounds")

# A fixed seed makes the noise-based sounds reproducible between runs.
random.seed(42)


# ---------------------------------------------------------------------------
# Small DSP helpers
# ---------------------------------------------------------------------------

def n_samples(seconds):
    """Convert a duration in seconds to a number of samples."""
    return int(SAMPLE_RATE * seconds)


def exp_env(i, decay):
    """Exponential decay envelope. `decay` = time (s) to fall to ~37%."""
    return math.exp(-(i / SAMPLE_RATE) / decay)


def white_noise():
    """One sample of uniform white noise in [-1, 1]."""
    return random.uniform(-1.0, 1.0)


class OnePoleHighPass:
    """Very simple high-pass filter — used to make noise sound 'metallic'."""

    def __init__(self, cutoff_hz):
        rc = 1.0 / (2 * math.pi * cutoff_hz)
        dt = 1.0 / SAMPLE_RATE
        self.a = rc / (rc + dt)
        self.prev_x = 0.0
        self.prev_y = 0.0

    def process(self, x):
        y = self.a * (self.prev_y + x - self.prev_x)
        self.prev_x, self.prev_y = x, y
        return y


class OnePoleLowPass:
    """Very simple low-pass filter — used to soften noise bursts."""

    def __init__(self, cutoff_hz):
        rc = 1.0 / (2 * math.pi * cutoff_hz)
        dt = 1.0 / SAMPLE_RATE
        self.a = dt / (rc + dt)
        self.y = 0.0

    def process(self, x):
        self.y += self.a * (x - self.y)
        return self.y


def pitch_sweep(duration, f_start, f_end, sweep_time, amp_decay):
    """
    Sine wave whose pitch glides exponentially from f_start to f_end.
    This is the classic recipe for kicks and toms.
    """
    out, phase = [], 0.0
    for i in range(n_samples(duration)):
        t = i / SAMPLE_RATE
        freq = f_end + (f_start - f_end) * math.exp(-t / sweep_time)
        phase += 2 * math.pi * freq / SAMPLE_RATE
        out.append(math.sin(phase) * exp_env(i, amp_decay))
    return out


def metallic(duration, decay, hp_cutoff, partials=None):
    """
    Cymbal-like tone: a cluster of detuned square-ish oscillators
    (like the famous 808 hi-hat) mixed with high-passed noise.
    """
    partials = partials or [205.3, 304.4, 369.6, 522.7, 540.0, 800.0]
    hp1, hp2 = OnePoleHighPass(hp_cutoff), OnePoleHighPass(hp_cutoff)
    out = []
    for i in range(n_samples(duration)):
        t = i / SAMPLE_RATE
        tone = sum(1.0 if math.sin(2 * math.pi * f * 1.7 * t) > 0 else -1.0
                   for f in partials) / len(partials)
        sig = 0.55 * tone + 0.45 * white_noise()
        sig = hp2.process(hp1.process(sig))  # two passes = steeper filter
        out.append(sig * exp_env(i, decay))
    return out


def mix(*tracks):
    """Sum several sample lists (of possibly different length)."""
    length = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(length)]


def scale(track, gain):
    return [s * gain for s in track]


def fade_out(track, ms=8):
    """Short linear fade at the end to avoid audible clicks."""
    n = min(len(track), int(SAMPLE_RATE * ms / 1000))
    for k in range(n):
        track[-1 - k] *= k / n
    return track


def normalize(track, peak=0.9):
    m = max(abs(s) for s in track) or 1.0
    return [s / m * peak for s in track]


def write_wav(name, track):
    """Normalize, de-click and save a sample list as a 16-bit mono WAV."""
    track = fade_out(normalize(track))
    path = os.path.join(OUT_DIR, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"".join(struct.pack("<h", int(s * 32767)) for s in track))
    print(f"  wrote {path}  ({len(track) / SAMPLE_RATE:.2f}s)")


# ---------------------------------------------------------------------------
# Individual instruments
# ---------------------------------------------------------------------------

def kick():
    body = pitch_sweep(0.6, 150, 45, 0.04, 0.18)
    # tiny noise "click" for the beater attack
    click = [white_noise() * exp_env(i, 0.003) for i in range(n_samples(0.02))]
    return mix(body, scale(click, 0.3))


def boom():
    """Long, deep 808-style sub bass."""
    return pitch_sweep(1.4, 90, 38, 0.08, 0.5)


def snare():
    tone = mix(pitch_sweep(0.3, 330, 180, 0.02, 0.06),
               scale(pitch_sweep(0.3, 480, 330, 0.02, 0.04), 0.5))
    hp = OnePoleHighPass(1200)
    noise = [hp.process(white_noise()) * exp_env(i, 0.09) for i in range(n_samples(0.35))]
    return mix(scale(tone, 0.6), noise)


def clap():
    """Several quick noise bursts, like multiple hands clapping."""
    hp, lp = OnePoleHighPass(900), OnePoleLowPass(5000)
    out = []
    burst_starts = [0.0, 0.011, 0.023, 0.034]  # seconds
    for i in range(n_samples(0.4)):
        t = i / SAMPLE_RATE
        env = 0.0
        for k, s in enumerate(burst_starts):
            if t >= s:
                d = 0.1 if k == len(burst_starts) - 1 else 0.008  # last one rings
                env += math.exp(-(t - s) / d)
        out.append(lp.process(hp.process(white_noise())) * env)
    return out


def hihat():
    return metallic(0.12, 0.025, 7000)


def openhat():
    return metallic(0.7, 0.22, 6500)


def ride():
    bell_partials = [523.0, 787.0, 1250.0]
    body = metallic(1.5, 0.5, 5000, partials=[180.0, 263.0, 331.0, 421.0, 583.0, 720.0])
    bell = [sum(math.sin(2 * math.pi * f * i / SAMPLE_RATE) for f in bell_partials)
            / len(bell_partials) * exp_env(i, 0.35) for i in range(n_samples(1.5))]
    return mix(scale(body, 0.7), scale(bell, 0.25))


def tom():
    body = pitch_sweep(0.6, 220, 110, 0.06, 0.18)
    click = [white_noise() * exp_env(i, 0.004) for i in range(n_samples(0.02))]
    return mix(body, scale(click, 0.2))


def tink():
    """Bright, short cowbell / wood-block style 'tink'."""
    out = []
    for i in range(n_samples(0.25)):
        t = i / SAMPLE_RATE
        s = (math.sin(2 * math.pi * 1760 * t) * 0.6 +
             math.sin(2 * math.pi * 2637 * t) * 0.4)
        out.append(s * exp_env(i, 0.04))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

INSTRUMENTS = {
    "clap.wav": clap,
    "hihat.wav": hihat,
    "kick.wav": kick,
    "openhat.wav": openhat,
    "boom.wav": boom,
    "ride.wav": ride,
    "snare.wav": snare,
    "tom.wav": tom,
    "tink.wav": tink,
}

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Synthesizing drum samples...")
    for filename, fn in INSTRUMENTS.items():
        write_wav(filename, fn())
    print("Done.")

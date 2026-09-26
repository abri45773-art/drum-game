/* ==============================================================
   Drum Kit — Game logic
   --------------------------------------------------------------
   How it works:
   1. On load we find every .pad element and read its data-key
      (keyboard key) and data-sound (file name in /sounds).
   2. Sounds are played through the Web Audio API, which gives very
      low latency and lets the same sample overlap itself when you
      hit a pad quickly (drum rolls!).
   3. If Web Audio can't load the files (e.g. the page was opened
      directly from disk via file://, where fetch() is blocked), we
      fall back to plain HTML <audio> elements.
   4. Pads react to mouse, touch and pen via Pointer Events, and to
      the physical keyboard via keydown.
   ============================================================== */

(() => {
  "use strict";

  // ---------- Configuration ----------
  const SOUND_DIR = "sounds/";
  const SOUND_EXT = ".wav";
  const FLASH_MS = 110; // how long a pad stays "lit" after a hit

  // ---------- DOM references ----------
  const pads = Array.from(document.querySelectorAll(".pad"));
  const volumeSlider = document.getElementById("volume");
  const hitCountEl = document.getElementById("hit-count");
  const announcer = document.getElementById("announcer");

  // Quick lookup: keyboard key → pad element, e.g. { a: <button>, ... }
  const padsByKey = Object.fromEntries(pads.map((pad) => [pad.dataset.key, pad]));

  // ---------- State ----------
  let hitCount = 0;
  let volume = parseFloat(volumeSlider.value);

  // =============================================================
  //  AUDIO ENGINE
  // =============================================================

  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  const audioCtx = AudioCtx ? new AudioCtx() : null;

  // Master gain node = global volume control for the Web Audio path.
  const masterGain = audioCtx ? audioCtx.createGain() : null;
  if (masterGain) {
    masterGain.gain.value = volume;
    masterGain.connect(audioCtx.destination);
  }

  /** Decoded AudioBuffers, keyed by sound name ("kick", "snare", ...). */
  const buffers = {};

  /** Fallback <audio> elements, keyed by sound name. */
  const fallbackAudio = {};

  /**
   * Load a single sample into an AudioBuffer.
   * Falls back to an <audio> element if fetching/decoding fails.
   * @param {string} name - sound name, e.g. "kick"
   */
  async function loadSound(name) {
    const url = SOUND_DIR + name + SOUND_EXT;

    if (audioCtx) {
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.arrayBuffer();
        // Promise form of decodeAudioData isn't in old Safari → wrap it.
        buffers[name] = await new Promise((resolve, reject) =>
          audioCtx.decodeAudioData(data, resolve, reject)
        );
        return;
      } catch (err) {
        console.warn(`Web Audio couldn't load "${url}", using <audio> fallback.`, err);
      }
    }

    // Fallback path: a preloaded HTMLAudioElement.
    const audio = new Audio(url);
    audio.preload = "auto";
    fallbackAudio[name] = audio;
  }

  /**
   * Play a sound by name. Uses Web Audio if the buffer is ready,
   * otherwise the <audio> fallback.
   * @param {string} name
   */
  function playSound(name) {
    // Browsers keep the AudioContext "suspended" until a user gesture;
    // every hit is a gesture, so resume here if needed.
    if (audioCtx && audioCtx.state === "suspended") {
      audioCtx.resume();
    }

    const buffer = buffers[name];
    if (buffer) {
      // A BufferSource is single-use and cheap — create one per hit.
      // This is what allows the same sound to overlap itself.
      const source = audioCtx.createBufferSource();
      source.buffer = buffer;
      source.connect(masterGain);
      source.start(0);
      return;
    }

    const audio = fallbackAudio[name];
    if (audio) {
      // Clone so rapid hits overlap instead of restarting one another.
      const clone = audio.cloneNode();
      clone.volume = volume;
      clone.play().catch(() => {
        /* autoplay blocked or file missing — ignore silently */
      });
    }
  }

  // =============================================================
  //  VISUAL FEEDBACK
  // =============================================================

  /**
   * Flash the pad and spawn a ripple from the hit point.
   * @param {HTMLElement} pad
   * @param {number} [x] - ripple origin, px from the pad's left edge
   * @param {number} [y] - ripple origin, px from the pad's top edge
   */
  function animatePad(pad, x, y) {
    // --- Glow / press effect ---
    pad.classList.add("playing");
    clearTimeout(pad._flashTimer);
    pad._flashTimer = setTimeout(() => pad.classList.remove("playing"), FLASH_MS);

    // --- Ripple ---
    const ripple = document.createElement("span");
    ripple.className = "ripple";
    // Keyboard hits have no coordinates → ripple from the centre.
    ripple.style.left = (x ?? pad.clientWidth / 2) + "px";
    ripple.style.top = (y ?? pad.clientHeight / 2) + "px";
    ripple.addEventListener("animationend", () => ripple.remove());
    pad.appendChild(ripple);
  }

  /** Increment the on-screen hit counter. */
  function updateCounter() {
    hitCount += 1;
    hitCountEl.textContent = hitCount;
  }

  // =============================================================
  //  TRIGGERING
  // =============================================================

  /**
   * Central "hit" function used by every input method.
   * @param {HTMLElement} pad
   * @param {number} [x]
   * @param {number} [y]
   */
  function hitPad(pad, x, y) {
    if (!pad) return;
    playSound(pad.dataset.sound);
    animatePad(pad, x, y);
    updateCounter();
    announcer.textContent = pad.querySelector(".sound").textContent;
  }

  // ---------- Mouse / touch / pen ----------
  // pointerdown fires immediately on touch (no 300 ms click delay),
  // which makes the pads feel much more responsive on phones.
  pads.forEach((pad) => {
    pad.addEventListener("pointerdown", (event) => {
      event.preventDefault(); // avoid focus flicker / text selection
      const rect = pad.getBoundingClientRect();
      hitPad(pad, event.clientX - rect.left, event.clientY - rect.top);
    });

    // Keyboard users who Tab to a pad and press Enter/Space trigger a
    // "click" with detail === 0 (no pointer). Handle that for a11y.
    pad.addEventListener("click", (event) => {
      if (event.detail === 0) hitPad(pad);
    });
  });

  // ---------- Physical keyboard ----------
  window.addEventListener("keydown", (event) => {
    // Ignore auto-repeat when a key is held down, and modifier combos
    // like Ctrl+S so we don't hijack browser shortcuts.
    if (event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;

    const pad = padsByKey[event.key.toLowerCase()];
    if (pad) hitPad(pad);
  });

  // ---------- Volume ----------
  volumeSlider.addEventListener("input", () => {
    volume = parseFloat(volumeSlider.value);
    if (masterGain) {
      // setTargetAtTime avoids zipper noise when dragging the slider.
      masterGain.gain.setTargetAtTime(volume, audioCtx.currentTime, 0.01);
    }
  });

  // =============================================================
  //  INIT — preload every sample referenced by a pad
  // =============================================================
  const soundNames = [...new Set(pads.map((pad) => pad.dataset.sound))];
  Promise.all(soundNames.map(loadSound)).then(() => {
    console.info(`Drum kit ready: ${soundNames.length} sounds loaded.`);
  });
})();

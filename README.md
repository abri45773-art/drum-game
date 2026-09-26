# drum-game

musik drum — a simple, responsive drum kit you can play in the browser with your
mouse, finger, or keyboard.

| Key | Sound    | Key | Sound | Key | Sound |
|-----|----------|-----|-------|-----|-------|
| A   | Clap     | F   | Open Hat | J | Snare |
| S   | Hi-Hat   | G   | Boom  | K   | Tom   |
| D   | Kick     | H   | Ride  | L   | Tink  |

## Features

- 9 colourful drum pads with glow + ripple animation on every hit
- Play with **mouse, touch, pen** (Pointer Events, no tap delay) or the **keyboard**
- Low-latency playback via the Web Audio API; rapid hits overlap for rolls
- Automatic `<audio>` fallback if Web Audio can't load the files
- Master volume slider and hit counter
- Responsive: 3×3 grid on phones, 5 + 4 layout on tablets/desktops
- Accessible: real `<button>`s, focus rings, screen-reader announcements,
  `prefers-reduced-motion` support

## Run it

The page is plain HTML/CSS/JS — no build step. Serve the folder with any static
server so the browser can `fetch()` the samples:

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

(Opening `index.html` directly from disk also works; it just uses the
`<audio>` fallback.)

## Project structure

```
index.html              markup for the pads & controls
style.css               layout, pad styling, animations, responsive rules
script.js               audio engine, input handling, visual feedback
sounds/*.wav            drum samples (CC0 public domain)
sounds/LICENSE.md       sound licence details
tools/generate_sounds.py  script that synthesizes the samples
```

## Sounds & licensing

All drum samples are **original sounds synthesized by
`tools/generate_sounds.py`** (sine/square waves + noise, standard library only),
so there are no copyright issues. They're released under **CC0 1.0 (public
domain)** — see [`sounds/LICENSE.md`](sounds/LICENSE.md).

To regenerate or tweak them:

```bash
python3 tools/generate_sounds.py
```

Want recorded drums instead? Drop CC0 / royalty-free samples (e.g. from
Freesound filtered by "Creative Commons 0") into `sounds/` using the same file
names.

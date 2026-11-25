# Hawks War Room Studio

Turns Jesse's raw episode recordings into approval-ready files. Every night, Claude checks `~/Documents/07 Seahawks/01 Drop Videos Here`. If anything new is there, it builds the following in `02 Ready for Review/<episode>/`:

- `podcast-full.mp4`: the full episode, edited. Dead air, "ums" and retakes are cut. Small zoom-ins smooth the jump cuts, audio is cleaned and leveled to -16 LUFS, and motion graphics appear where they're relevant (matchup, Thing cards, call cards, stat and comparison cards, name labels, crew cards, postgame verdict stamps).
- `reels/`: 3 to 6 vertical clips with word-by-word captions, a hook card and an end card.
- `thumbnails/`: 3 options.
- `youtube.md`: title options, description and chapters. `podcast-full.srt`: captions.
- `review.html`: one page to watch and approve everything, including flagged items and a list of every cut.

An episode can be several files: the main recording, friends' clips or voice memos, a second location. Drop them all in the same folder. Voice memos get a full-screen "From the crew" card.

This folder is not part of the website: `seahawks/.vercelignore` excludes it.

## Setup (once, on the Mac)

1. Clone this repo to `~/Documents/07 Seahawks/Studio/site`.
2. Run `seahawks/studio/setup-mac.sh`. It creates the folders and installs ffmpeg, Node, the Python packages and the graphics renderer.
3. In the Claude desktop app, create a scheduled task. Run it nightly at a time when the Mac is usually on and awake, with access to `~/Documents/07 Seahawks`:

   > Run the Hawks War Room nightly studio job. Follow the "Nightly run" section of `~/Documents/07 Seahawks/Studio/site/seahawks/studio/PLAYBOOK.md` exactly, after reading `seahawks/CLAUDE.md` in the same repo. If there is nothing new, end quietly without notifying me.

## How it splits the work

- `studio.py` does the mechanical work: moving files, transcribing (faster-whisper), detecting silences, finding faces (OpenCV), encoding (ffmpeg), rendering graphics (`graphics/graphics.html` through Playwright), and building the review page.
- Claude makes the judgment calls by writing `plan.json`: the episode ID, the cut list, clip placement, graphics, reels, thumbnails and titles. The rules are in `PLAYBOOK.md`.

## Commands

```
.venv/bin/python studio.py status
.venv/bin/python studio.py inbox --episode 2026-w12-pre
.venv/bin/python studio.py render 2026-w12-pre [--only longform|reels|thumbs]
.venv/bin/python studio.py approve 2026-w12-pre
```

## Settings (`config.json`)

- `whisper_model`: `medium.en` by default. `small.en` is faster but less accurate on names.
- `video_args`: on Apple Silicon, `["-c:v", "h264_videotoolbox", "-b:v", "12M"]` encodes much faster than the libx264 default.
- `pause_max` / `pause_keep`: pauses longer than `pause_max` seconds get shortened to `pause_keep`.
- `vocab.txt`: names Whisper should spell correctly. Add each week's opponent names.

## Test

`python3 tests/make_sample.py /tmp/hwr-test` builds a synthetic three-source episode (a video, a voice memo, a vertical clip) and runs the whole pipeline on it, skipping Whisper. It needs `espeak-ng`.

## Recording tips

- Record landscape (16:9), with your face roughly centered and some headroom. That gives the reels room to crop 9:16 around you.
- A clap at the start doesn't matter; the edit trims the head. Just start talking.
- Say "cut that" after a flub. Claude removes it.
- Introduce friends' clips by name ("here's Matt on the line of scrimmage") so the edit places them and labels them correctly.

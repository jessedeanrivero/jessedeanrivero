# Hawks War Room Studio: Playbook for Claude

This is what Claude does when the nightly scheduled task fires, and when Jesse sends notes on an episode. Read `seahawks/CLAUDE.md` first: its editorial and accuracy rules apply to everything here, including on-screen graphics.

The script (`studio.py`) does the mechanical work. **Claude's job is the judgment**: the episode ID, the cut list, where friends' clips go, graphics, reels, thumbnails and titles. All of it goes into `plan.json`.

Run every command from this folder using the virtual environment: `.venv/bin/python studio.py ...`.

## Folders (`~/Documents/07 Seahawks`)

| Folder | What lives there |
|---|---|
| `01 Drop Videos Here` | Jesse drops every file for an episode here: main recording, friends' clips, voice memos, second-location footage. |
| `02 Ready for Review/<episode>` | Everything Claude made, plus `review.html`. Nothing here is published. |
| `03 Approved/<episode>` | Approved episodes, moved here by `studio.py approve`. |
| `04 Raw Footage/<episode>` | Original files, moved here on approval. Never delete these. |
| `05 Prep Packs` | Pregame research and crew questions, for Jesse to read before recording. |
| `06 Music & Brand` | Intro/outro music and art Jesse owns. Use only what's in here. |
| `Studio` | These tools (a clone of the website repo). |

## Nightly run

1. `git -C <repo> pull --ff-only` so the tools and prep packs are current. If it fails, note it and carry on.
2. `.venv/bin/python studio.py status`. If the drop folder has nothing new and no episode says `needs-plan`, **stop** and report "Nothing new tonight." Don't notify Jesse for a no-op.
3. **Pick the episode ID** for whatever is in the drop folder: `<season>-w<week>-pre` or `-post`, for example `2026-w12-pre`.
   - Check the official Seahawks schedule. Never derive the week from games played, because byes break that.
   - Compare the files' recording times (shown by `inbox`, or `ffprobe`) with kickoff. Recorded before the next game's kickoff means `-pre` for that game. Recorded after a game ended, before the next week's game, means `-post` for the game just played.
   - If an episode with that ID already exists and isn't approved, reuse it: new files are added as more sources (D, E...).
   - If you truly can't tell, use `YYYY-MM-DD-episode` and flag it.
4. `.venv/bin/python studio.py inbox --episode <ID>`. This moves the files into the episode's `raw/` folder, transcribes everything, and writes `plan.draft.json`. It's slow: about real time on the Mac's CPU.
5. Read `transcript.txt`, `plan.draft.json`, and the context: the prep pack (`seahawks/episodes/<week-id>/prep.md` in the repo, if there is one), the current game page under `seahawks/g/`, and, for a postgame, the original preview's 10 calls.
6. Write `plan.json` (format below). Start from the draft.
7. `.venv/bin/python studio.py render <ID>`. Fix any `plan.json problems` it reports and rerun.
8. Open the output frames you're unsure of (`ffmpeg -ss <t> -i podcast-full.mp4 -frames:v 1 check.png`) and look at them, at minimum each graphic and each reel's first frame. Fix and re-render as needed.
9. Report to Jesse in a few lines: the episode ID, edited length, number of reels, anything in `flags`, and the path to `review.html`. A pregame episode must be approved before kickoff, so say how long remains.

## Writing `plan.json`

Times are **source times**: a source letter plus seconds into that file, exactly as `transcript.txt` shows them (`[A 12:40 | 760.2s]`). The script maps them onto the edited timeline.

```json
{
  "episode": "2026-w12-pre",
  "kind": "pregame",
  "faces": {"A": [0.5, 0.42]},
  "crew": {"B": {"name": "Matt M.", "question": "Who wins the line of scrimmage?"}},
  "zoom": true,
  "bug": true,
  "keep": [["A", 0.0, 312.4], ["B", 0.0, 21.5], ["A", 313.1, 640.0]],
  "title_options": ["...", "...", "..."],
  "description": "...",
  "chapters": [{"src": "A", "t": 95.2, "title": "Thing 1: Protect Darnold early"}],
  "graphics": [{"src": "A", "t": 97.0, "dur": 5, "type": "call", "data": {"num": 1, "call": "No sacks on the opening drive."}}],
  "reels": [{"src": "A", "start": 600.0, "end": 645.5, "id": "hot-take", "hook": "Seattle wins by *a touchdown*", "why": "..."}],
  "thumbnails": [{"src": "A", "t": 615.0, "text": "Can Seattle *win in Santa Clara*?", "tag": "WEEK 12 · AT 49ERS"}],
  "flags": [{"src": "A", "t": 410.0, "note": "Jesse said 150 rush yards allowed per game; the prep pack says 151.2. Not shown on screen."}]
}
```

### keep (the edit)
- The draft already removes long pauses and "um/uh". Your job is everything a person would notice:
  - **False starts and retakes:** when Jesse restarts a sentence or says "let me say that again," keep only the final clean take.
  - Anything he says to cut ("cut that," "don't use that").
  - Dead air at the very start and end, and fumbling with the camera.
- Never cut in a way that changes his meaning, drops a call, or removes a caveat he attached to a call.
- **Order.** Main recordings play in recording order. Put each friend's clip right after Jesse introduces it or asks the question it answers ("let's hear from Matt"). If he never introduces it, group the crew clips together where they fit best and flag it. Second-location footage goes where its topic fits; otherwise at the end.
- Every piece is `[source, start, end]`, with start before end, inside the file.

### crew (friends' audio-only clips)
- Audio-only sources show a full-screen "From the crew" card. Set `name` from how Jesse introduces them (first name and last initial, the same style as the prediction leaderboard) or from the filename. If you can't tell, leave it empty and flag it. `question` is the prep-pack question they answered, if it's clear.
- Friends' **video** clips play as video. Add a `crew` lower-third graphic when they first appear.

### Graphics
Types: `matchup`, `thing`, `call`, `stat`, `compare`, `name`, `crew`, `verdict`, plus `hook` and `endcard`, which reels add automatically.

| type | data | use |
|---|---|---|
| `matchup` | `kicker`, `left{name,record}`, `right{name,record}`, `meta[]` | Once, near the top. Seattle on the left. |
| `thing` | `num`, `title` | When Jesse starts each of the 10 Things. |
| `call` | `num`, `call`, optional `verdict` | When he states the call, in his words, condensed. In postgame episodes add `verdict`. |
| `stat` | `value`, `label`, `note`, `source` | One verified number he's talking about. |
| `compare` | `title`, `rows[{label,value,display,color}]`, `source` | Two or three verified numbers side by side. `color: "opp"` for the opponent. |
| `name` | `name`, `role` | First mention of a player or coach who matters to the point. |
| `crew` | `name`, `question` | A friend's video clip begins. |
| `verdict` | `verdict` (`called`/`partly`/`missed`/`none`), `line` | Postgame grading of each call. |

Rules:
- **Every number on screen must come from a verified source**: the prep pack, the official box score, or a source `CLAUDE.md` accepts. Put the source in `source`. If Jesse misstates a number, don't put his number on screen and don't "correct" him on screen. Add a `flags` entry so he can decide.
- Records, dates and kickoff times are verified the same way. Never guess them.
- **No team logos, NFL marks or player photos.** Text, numbers and colors only.
- Use `*word*` to highlight a word in lime in `call`, `hook`, `verdict.line` and thumbnail `text`.
- Pacing: about one graphic every 30 to 90 seconds, each 4 to 6 seconds, and never two at once. Lower thirds (`thing`, `call`, `name`, `crew`) and right-side cards (`stat`, `compare`) shouldn't overlap in time.
- Keep `call` text under about 90 characters, and `thing` titles under 4 words if possible.

### Reels (3 to 6)
- Pick moments that work with no context: a bold specific call, a strong opinion with a reason, a funny line, a sharp piece of analysis, a friend's great take (video sources only).
- 20 to 60 seconds. Start on the strongest line, not on a wind-up. End on a complete thought.
- `hook`: 8 words or fewer, the claim itself, with a `*highlight*`. `why`: one sentence on why this moment works, which shows on the review page.
- Don't make two reels from the same point.

### Thumbnails (3 options)
- Frames where Jesse is mid-expression and looking at the camera. Check the frame before choosing it.
- `text` of 6 words or fewer. Three options with different angles: the matchup, the boldest call, a question.

### Titles, description, chapters
- Three title options, under 70 characters, specific to this game. No clickbait he wouldn't say.
- Description: two or three sentences in his voice, then `Full breakdown: https://www.hawkswarroom.com/g/<week-id>` (the preview page for pregame, the `-recap` page for postgame).
- Chapters: one per Thing to Watch, plus the opening, crew clips and the final call. At least 10 seconds apart.

### Postgame episodes
- The 10 calls come from the **original preview**, word for word. Never reword them to fit the result.
- When Jesse grades a call on the show, use his verdict: We called it, Partly right, Missed it, or Not enough evidence. If he doesn't grade one, don't add a `verdict` for it; flag it instead.

## When Jesse sends notes

Edit `plan.json` to match each note, then re-render only what changed: `studio.py render <ID> --only longform`, `--only reels`, or `--only thumbs`. The review page always rebuilds. Reply with what changed.

## When Jesse approves ("approve 2026-w12-pre")

1. `.venv/bin/python studio.py approve <ID>`. This copies the transcript, plan, YouTube text and captions into `seahawks/episodes/<ID>/` in the repo, moves the raw files to `04 Raw Footage`, and moves the episode to `03 Approved`.
2. In the repo: create the branch `episodes/<ID>`, commit `seahawks/episodes/<ID>/`, and push. **Never push to `main`.** The website only goes live when Jesse asks.
3. Tell Jesse the blog material is pushed and that the blog post can now be built from it.
4. Upload to YouTube only if Jesse asks, and as private or unlisted drafts.

## The blog (Claude Code, in the website repo)

The pregame page or postgame recap is built from `seahawks/episodes/<ID>/transcript.txt`, following `seahawks/CLAUDE.md`:
- Jesse's War Room Note and takes use **his words from the transcript**, lightly cleaned. Never put words in his mouth.
- The 10 Things and calls are published as he stated them on the episode. They're locked once the preview is live before kickoff.
- Embed the YouTube episode once it's uploaded.
- Crew quotes from voice clips get the person's name only if Jesse identified them on the show.

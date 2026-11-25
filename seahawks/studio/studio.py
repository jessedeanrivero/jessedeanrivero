#!/usr/bin/env python3
"""Hawks War Room studio: turns raw episode recordings into approval-ready files.

Commands:
  studio.py status                        list episodes and where each one stands
  studio.py inbox --episode ID            move everything in the drop folder into episode ID,
                                          transcribe it, and draft a cut list (plan.draft.json)
  studio.py transcribe ID [--source B]    (re)transcribe one episode or one source
  studio.py autocut ID                    rebuild plan.draft.json
  studio.py render ID [--only longform|reels|thumbs|review]
  studio.py approve ID                    copy blog material to the repo, file the episode away

An episode can have several source files: the main recording, friends' clips (video or voice
memo), a second location. They get letters A, B, C... in recording order. Claude writes plan.json
from plan.draft.json (see PLAYBOOK.md); this script only executes it.
"""
import argparse, concurrent.futures as cf, datetime as dt, html, json, os, re, shutil, statistics, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIDEO_EXT = {'.mp4', '.mov', '.m4v', '.mkv'}
AUDIO_EXT = {'.m4a', '.mp3', '.wav', '.aac', '.caf'}
FILLERS = re.compile(r"^(u+m+|u+h+|uhm+|erm+|hmm+|mm+|ah+)[,.!?]*$", re.I)
FPS = 30
W, H = 1920, 1080


# ---------- config & helpers ----------
def load_config():
    cfg = {
        'root': '~/Documents/07 Seahawks',
        'inbox': '{root}/01 Drop Videos Here',
        'outbox': '{root}/02 Ready for Review',
        'approved': '{root}/03 Approved',
        'raw': '{root}/04 Raw Footage',
        'repo': '',
        'whisper_model': 'medium.en',
        'workers': 4,
        'video_args': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18'],
        'settle_minutes': 10,  # ignore files changed more recently than this (still copying/syncing)
        'pause_max': 0.6,      # silences longer than this get shortened...
        'pause_keep': 0.3,     # ...down to this
        'silence_db': -35,
        'cut_fillers': True,
        'zoom': 1.12,
        'loudness': -16,
        'reel_loudness': -14,
    }
    p = HERE / 'config.json'
    if p.exists():
        cfg.update(json.loads(p.read_text()))
    root = os.path.expanduser(cfg['root'])
    for k in ('root', 'inbox', 'outbox', 'approved', 'raw', 'repo'):
        if cfg[k]:
            cfg[k] = Path(os.path.expanduser(str(cfg[k]).replace('{root}', root)))
    return cfg


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"command failed: {' '.join(map(str, cmd))}\n{r.stderr[-3000:]}")
    return r


def probe(path):
    r = run(['ffprobe', '-v', 'error', '-show_entries',
             'stream=codec_type,width,height,disposition:format=duration:format_tags=creation_time,com.apple.quicktime.creationdate',
             '-of', 'json', str(path)])
    j = json.loads(r.stdout)
    v = next((s for s in j['streams'] if s['codec_type'] == 'video' and s.get('width')
              and not s.get('disposition', {}).get('attached_pic')), None)
    tags = j.get('format', {}).get('tags', {})
    rec = tags.get('com.apple.quicktime.creationdate') or tags.get('creation_time')
    try:
        rec = dt.datetime.fromisoformat(rec.replace('Z', '+00:00')).astimezone().strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        rec = dt.datetime.fromtimestamp(Path(path).stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    return {'w': int(v['width']) if v else 0, 'h': int(v['height']) if v else 0, 'video': bool(v),
            'dur': float(j['format']['duration']), 'recorded': rec,
            'audio': any(s['codec_type'] == 'audio' for s in j['streams'])}


def fmt_ts(t, ms=False):
    t = max(0, t)
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    if ms:
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')
    return f"{h}:{m:02d}:{int(s):02d}" if h else f"{m}:{int(s):02d}"


def snap(t):
    return round(t * FPS) / FPS


def episode_dir(cfg, ep):
    p = Path(os.path.expanduser(ep))
    if p.is_dir():
        return p.resolve()
    for base in (cfg['outbox'], cfg['approved']):
        if (base / ep).is_dir():
            return base / ep
    sys.exit(f"no episode folder named {ep}")


def load_state(ep):
    p = ep / 'state.json'
    return json.loads(p.read_text()) if p.exists() else {}


def save_state(ep, **kw):
    st = load_state(ep)
    st.update(kw, updated=time.strftime('%Y-%m-%d %H:%M'))
    (ep / 'state.json').write_text(json.dumps(st, indent=2))
    return st


def sources_of(ep):
    """{'A': {'name', 'video', 'w', 'h', 'dur', 'recorded', 'gain_db', 'path'}, ...}"""
    out = {}
    for k, v in load_state(ep).get('sources', {}).items():
        p = ep / 'raw' / v['name']
        if not p.exists():
            sys.exit(f"source file missing: {p}")
        out[k] = {**v, 'path': p}
    if not out:
        sys.exit(f"{ep.name}: no source files recorded in state.json")
    return out


def load_transcripts(ep):
    p = ep / 'transcript.json'
    return json.loads(p.read_text()).get('sources', {}) if p.exists() else {}


# ---------- timeline ----------
def norm_keep(keep):
    return [(str(k[0]), float(k[1]), float(k[2])) for k in keep]


class Timeline:
    """Maps (source letter, source time) to edited output time. keep = [(src, a, b), ...] in play order."""
    def __init__(self, keep):
        self.segs, o = [], 0.0
        for src, a, b in keep:
            self.segs.append((src, a, b, o))
            o += b - a
        self.total = o

    def out(self, src, t):
        """Output time of a source moment; a moment that was cut maps to the next kept moment of that source."""
        best = None
        for s, a, b, o in self.segs:
            if s != src:
                continue
            if a <= t <= b:
                return o + (t - a)
            if t < a and (best is None or a < best[0]):
                best = (a, o)
        return best[1] if best else self.total


def clip_keep(keep, src, start, end):
    out = []
    for s, a, b in keep:
        if s == src:
            a2, b2 = max(a, start), min(b, end)
            if b2 - a2 >= 0.2:
                out.append((s, snap(a2), snap(b2)))
    return out


def mapped_words(trs, keep):
    """Transcript words in output order and output time, fillers removed."""
    out, o = [], 0.0
    for s, a, b in keep:
        for w in trs.get(s, {}).get('words', []):
            mid = (w['s'] + w['e']) / 2
            if a <= mid <= b and not FILLERS.match(w['w']):
                out.append({'w': w['w'], 's': o + max(w['s'], a) - a, 'e': o + min(w['e'], b) - a})
        o += b - a
    return out


# ---------- ingest & transcription ----------
def inbox(cfg, episode):
    for k in ('inbox', 'outbox', 'approved', 'raw'):
        cfg[k].mkdir(parents=True, exist_ok=True)
    files, waiting = [], []
    for f in sorted(cfg['inbox'].iterdir()):
        if f.name.startswith('.') or f.suffix.lower() not in VIDEO_EXT | AUDIO_EXT:
            continue
        (waiting if time.time() - f.stat().st_mtime < cfg['settle_minutes'] * 60 else files).append(f)
    for f in waiting:
        print(f"{f.name}: changed in the last {cfg['settle_minutes']} min (still copying?), leaving it for next run")
    if not files:
        print("drop folder: nothing new")
        return
    if not episode:
        sys.exit(f"{len(files)} new file(s) waiting; rerun with --episode ID (e.g. 2026-w12-pre)")
    ep = cfg['outbox'] / episode
    (ep / 'raw').mkdir(parents=True, exist_ok=True)
    st = load_state(ep)
    sources = st.get('sources', {})
    infos = sorted(((f, probe(f)) for f in files), key=lambda x: x[1]['recorded'])
    new = []
    for f, info in infos:
        if not info['audio']:
            print(f"{f.name}: no audio track, skipped (left in the drop folder)")
            continue
        letter = chr(ord('A') + len(sources))
        dest = ep / 'raw' / f.name
        if dest.exists():
            dest = ep / 'raw' / f"{f.stem}-{letter}{f.suffix}"
        shutil.move(str(f), str(dest))
        sources[letter] = {'name': dest.name, **info}
        new.append(letter)
        print(f"{letter}: {dest.name} ({'video' if info['video'] else 'audio only'}, {fmt_ts(info['dur'])}, recorded {info['recorded']})")
    if not new:
        return
    save_state(ep, status='ingesting', sources=sources)
    for letter in new:
        transcribe(cfg, ep, letter)
    autocut(cfg, ep)


def transcribe(cfg, ep, only=None):
    srcs = sources_of(ep)
    trs = load_transcripts(ep)
    from faster_whisper import WhisperModel  # imported late so other commands work without it
    vocab = (HERE / 'vocab.txt').read_text().strip() if (HERE / 'vocab.txt').exists() else ''
    # a filler-heavy prompt nudges Whisper to keep "um"/"uh" instead of silently dropping them
    prompt = ("Umm, so, uh, let me think, like, hmm. Okay. " + vocab)[:800]
    model = WhisperModel(cfg['whisper_model'], device='auto', compute_type='int8')
    for letter, s in srcs.items():
        if only and letter not in (only if isinstance(only, (list, tuple)) else [only]):
            continue
        wav = ep / 'work' / f"audio16k-{letter}.wav"
        wav.parent.mkdir(exist_ok=True)
        run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(s['path']), '-vn', '-ac', '1', '-ar', '16000', str(wav)])
        print(f"{letter}: transcribing {fmt_ts(s['dur'])} of audio...")
        segments, _ = model.transcribe(str(wav), language='en', word_timestamps=True, initial_prompt=prompt,
                                       condition_on_previous_text=False)
        words, segs = [], []
        for sg in segments:
            segs.append({'s': round(sg.start, 3), 'e': round(sg.end, 3), 'text': sg.text.strip()})
            for w in sg.words or []:
                words.append({'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3)})
        trs[letter] = {'words': words, 'segments': segs}
        write_transcripts(ep, trs)


def write_transcripts(ep, trs):
    (ep / 'transcript.json').write_text(json.dumps({'sources': trs}, indent=1))
    srcs = load_state(ep).get('sources', {})
    out = []
    for letter in sorted(trs):
        s = srcs.get(letter, {})
        out.append(f"=== {letter} · {s.get('name', '?')} · {'video' if s.get('video') else 'audio only'} · "
                   f"{fmt_ts(s.get('dur', 0))} · recorded {s.get('recorded', '?')} ===")
        out += [f"[{letter} {fmt_ts(g['s'])} | {g['s']:.1f}s] {g['text']}" for g in trs[letter]['segments']]
        out.append('')
    (ep / 'transcript.txt').write_text('\n'.join(out))


# ---------- autocut ----------
def detect_silences(cfg, path):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(path), '-vn', '-af',
                        f"silencedetect=noise={cfg['silence_db']}dB:d={cfg['pause_max']}", '-f', 'null', '-'],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', r.stderr)]
    ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', r.stderr)]
    return list(zip(starts, ends))


def loudness_of(path):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(path), '-vn', '-af', 'loudnorm=print_format=json',
                        '-f', 'null', '-'], capture_output=True, text=True)
    try:
        return float(json.loads(r.stderr[r.stderr.rindex('{'):r.stderr.rindex('}') + 1])['input_i'])
    except Exception:
        return None


def face_center(path, t0=0, t1=None, samples=15):
    """Median face centre (x, y as 0-1 fractions). Falls back to a typical seated framing."""
    try:
        import cv2
    except ImportError:
        return [0.5, 0.42]
    cap = cv2.VideoCapture(str(path))
    if t1 is None:
        t1 = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1)
    det = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    xs, ys = [], []
    for i in range(samples):
        cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * (t0 + (t1 - t0) * (i + 0.5) / samples))
        ok, frame = cap.read()
        if not ok:
            continue
        fh, fw = frame.shape[:2]
        small = cv2.resize(frame, (fw * 480 // fh, 480))
        faces = det.detectMultiScale(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.1, 6, minSize=(50, 50))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            xs.append((x + w / 2) / small.shape[1])
            ys.append((y + h / 2) / small.shape[0])
    cap.release()
    if not xs:
        return [0.5, 0.42]
    return [round(statistics.median(xs), 3), round(statistics.median(ys), 3)]


def autocut_source(cfg, s, words):
    cuts = [(a + cfg['pause_keep'] / 2, b - cfg['pause_keep'] / 2) for a, b in detect_silences(cfg, s['path'])]
    if cfg['cut_fillers']:
        cuts += [(w['s'] - 0.03, w['e'] + 0.03) for w in words if FILLERS.match(w['w'])]
    head = max(0.0, (words[0]['s'] if words else 0) - 0.35)
    tail = min(s['dur'], (words[-1]['e'] if words else s['dur']) + 0.6)
    merged = []
    for a, b in sorted(cuts):
        if merged and a <= merged[-1][1] + 0.05:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    keep, t = [], head
    for a, b in merged:
        if b - a < 0.12 or b <= head or a >= tail:
            continue
        if a > t:
            keep.append((t, a))
        t = max(t, b)
    if tail > t:
        keep.append((t, tail))
    return [(snap(a), snap(b)) for a, b in keep if b - a >= 0.25]


def autocut(cfg, ep):
    srcs = sources_of(ep)
    trs = load_transcripts(ep)
    st = load_state(ep)
    keep, faces, crew = [], {}, {}
    for letter, s in srcs.items():
        words = trs.get(letter, {}).get('words', [])
        keep += [[letter, a, b] for a, b in autocut_source(cfg, s, words)]
        if s['video']:
            faces[letter] = face_center(s['path'])
        else:
            crew[letter] = {'name': '', 'question': ''}
        if s.get('gain_db') is None:
            li = loudness_of(s['path'])
            st['sources'][letter]['gain_db'] = round(cfg['loudness'] - li, 1) if li and li > -60 else 0.0
    save_state(ep, sources=st['sources'])
    stem = ep.name
    plan = {
        'episode': stem,
        'kind': 'postgame' if stem.endswith('-post') else 'pregame',
        'faces': faces,
        'crew': crew,
        'zoom': True,
        'bug': True,
        'keep': keep,
        'title_options': [],
        'description': '',
        'chapters': [],
        'graphics': [],
        'reels': [],
        'thumbnails': [],
        'flags': [],
    }
    (ep / 'plan.draft.json').write_text(json.dumps(plan, indent=1))
    total = sum(s['dur'] for s in srcs.values())
    kept = sum(b - a for _, a, b in keep)
    save_state(ep, status='needs-plan')
    print(f"{stem}: {len(srcs)} source(s), draft keeps {fmt_ts(kept)} of {fmt_ts(total)}; "
          f"next: Claude writes plan.json, then `studio.py render {stem}`")


# ---------- rendering ----------
def render_graphics(jobs, workdir, name='gfx-jobs.json'):
    if not jobs:
        return
    jf = workdir / name
    jf.write_text(json.dumps(jobs))
    r = subprocess.run(['node', str(HERE / 'graphics' / 'render.cjs'), str(jf)], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("graphics render failed:\n" + r.stderr[-3000:])


def fit_filter(s, ow, oh, crop=None):
    """Scale a source into ow x oh. Sources with a different shape get a blurred fill instead of black bars."""
    pre = f"fps={FPS}" + (f",{crop}" if crop else '')
    iw, ih = s['w'], s['h']
    same_shape = abs((iw / ih) - (ow / oh)) < 0.05 if crop is None else True
    if same_shape:
        return pre + f",scale={ow}:{oh}:force_original_aspect_ratio=increase,crop={ow}:{oh},setsar=1"
    return (pre + f",split[bg][fg];[bg]scale={ow}:{oh}:force_original_aspect_ratio=increase,crop={ow}:{oh},"
            f"boxblur=30:3,eq=brightness=-0.15[b];[fg]scale={ow}:{oh}:force_original_aspect_ratio=decrease[f];"
            f"[b][f]overlay=(W-w)/2:(H-h)/2,setsar=1")


def encode_segments(cfg, srcs, segs, outdir, label, ow, oh, vf_for, card_for=None):
    """segs: [(src, a, b, extra)]. Each becomes an exact-length intermediate so concatenation stays in sync."""
    outdir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for i, (src, a, b, extra) in enumerate(segs):
        s = srcs[src]
        n = max(1, round((b - a) * FPS))
        d = n / FPS
        out = outdir / f"{label}{i:04d}.mov"
        af = (f"volume={s.get('gain_db') or 0}dB,aresample=48000,afade=t=in:d=0.01,"
              f"afade=t=out:st={max(0, d - 0.012):.3f}:d=0.012,apad,atrim=0:{d:.4f}")
        if s['video']:
            inputs = ['-ss', f"{a:.4f}", '-t', f"{d + 0.3:.4f}", '-i', str(s['path'])]
            vmap, amap, vf = '0:v:0', '0:a:0', vf_for(src, extra)
        else:
            inputs = ['-loop', '1', '-framerate', str(FPS), '-i', str(card_for(src)),
                      '-ss', f"{a:.4f}", '-t', f"{d + 0.3:.4f}", '-i', str(s['path'])]
            vmap, amap, vf = '0:v:0', '1:a:0', f"fps={FPS},scale={ow}:{oh},setsar=1"
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', *inputs, '-map', vmap, '-map', amap,
               '-vf', vf + ",tpad=stop_mode=clone:stop_duration=0.3", '-af', af, '-frames:v', str(n),
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '14', '-pix_fmt', 'yuv420p',
               '-c:a', 'pcm_s16le', '-ac', '2', str(out)]
        jobs.append((cmd, out))
    with cf.ThreadPoolExecutor(cfg['workers']) as ex:
        list(ex.map(lambda j: run(j[0]), jobs))
    lst = outdir / f"{label}list.txt"
    lst.write_text(''.join(f"file '{o}'\n" for _, o in jobs))
    return lst


def measure_loudness(lst, chain, target):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-f', 'concat', '-safe', '0', '-i', str(lst), '-vn', '-af',
                        f"{chain}loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", '-f', 'null', '-'],
                       capture_output=True, text=True)
    m = json.loads(r.stderr[r.stderr.rindex('{'):r.stderr.rindex('}') + 1])
    return (f"{chain}loudnorm=I={target}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
            f"linear=true,aresample=48000")


def crew_cards(srcs, plan, work, ow, oh):
    """Full-frame 'from the crew' cards for audio-only sources."""
    jobs, cards = [], {}
    for letter, s in srcs.items():
        if s['video']:
            continue
        c = plan.get('crew', {}).get(letter, {})
        out = work / 'gfx' / f"crewcard-{letter}-{ow}x{oh}.png"
        jobs.append({'type': 'crewcard', 'w': ow, 'h': oh, 'dur': 1, 'out': str(out),
                     'data': {'name': c.get('name') or 'The crew', 'question': c.get('question', '')}})
        cards[letter] = out
    render_graphics(jobs, work, f'crewcards-{ow}.json')
    return cards


def render_longform(cfg, ep, plan, srcs, trs):
    work = ep / 'work'
    keep = norm_keep(plan['keep'])
    tl = Timeline(keep)
    z = cfg['zoom']

    def vf(src, zoomed):
        s = srcs[src]
        crop = None
        if zoomed:
            fx, fy = plan.get('faces', {}).get(src) or [0.5, 0.42]
            cw, ch = s['w'] / z, s['h'] / z
            cx = min(max(fx * s['w'] - cw / 2, 0), s['w'] - cw)
            cy = min(max(fy * s['h'] - ch / 2, 0), s['h'] - ch)
            crop = f"crop={int(cw)//2*2}:{int(ch)//2*2}:{int(cx)}:{int(cy)}"
        return fit_filter(s, W, H, crop) if crop is None else fit_filter({**s, 'w': W, 'h': H}, W, H, crop)

    # punch in on alternate cuts so jump cuts look deliberate; never after a very short piece, reset per source
    segs, zoomed, prev = [], False, (None, 99)
    for src, a, b in keep:
        if src != prev[0]:
            zoomed = False
        elif plan.get('zoom', True) and prev[1] >= 2.5 and srcs[src]['video']:
            zoomed = not zoomed
        segs.append((src, a, b, zoomed))
        prev = (src, b - a)
    cards = crew_cards(srcs, plan, work, W, H)
    print(f"  encoding {len(segs)} pieces...")
    lst = encode_segments(cfg, srcs, segs, work / 'seg', 'lf', W, H, vf, cards.get)

    gjobs, overlays = [], []
    for i, g in enumerate(plan.get('graphics', [])):
        start, dur = tl.out(g['src'], g['t']), float(g.get('dur', 5))
        out = work / 'gfx' / f"g{i:02d}-{g['type']}.mov"
        gjobs.append({'type': g['type'], 'data': g.get('data', {}), 'w': W, 'h': H, 'dur': dur, 'fps': FPS, 'out': str(out)})
        overlays.append((start, dur, out))
    if plan.get('bug', True):
        gjobs.append({'type': 'bug', 'w': W, 'h': H, 'dur': 1, 'out': str(work / 'gfx' / 'bug.png')})
    print(f"  rendering {len(gjobs)} graphics...")
    render_graphics(gjobs, work)

    audio = measure_loudness(lst, 'highpass=f=70,afftdn=nf=-25,', cfg['loudness'])
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst)]
    parts, cur = [], '0:v'
    for i, (start, dur, out) in enumerate(overlays):
        cmd += ['-itsoffset', f"{start:.3f}", '-i', str(out)]
        parts.append(f"[{cur}][{i + 1}:v]overlay=0:0:eof_action=pass:enable='between(t,{start:.3f},{start + dur:.3f})'[o{i}]")
        cur = f"o{i}"
    if plan.get('bug', True):
        cmd += ['-i', str(work / 'gfx' / 'bug.png')]
        parts.append(f"[{cur}][{len(overlays) + 1}:v]overlay=0:0[ob]")
        cur = 'ob'
    parts += [f"[{cur}]format=yuv420p[vout]", f"[0:a]{audio}[aout]"]
    script = work / 'longform.filter'
    script.write_text(';\n'.join(parts))
    cmd += ['-filter_complex_script', str(script), '-map', '[vout]', '-map', '[aout]', *cfg['video_args'],
            '-r', str(FPS), '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(ep / 'podcast-full.mp4')]
    print("  final encode...")
    run(cmd)
    write_srt(ep / 'podcast-full.srt', mapped_words(trs, keep))
    write_youtube(ep, plan, tl)


def caption_groups(words, max_words=3, max_chars=16):
    groups, cur = [], []
    for w in words:
        if not w['w'].strip():
            continue
        if cur and (len(cur) >= max_words or len(' '.join(x['w'] for x in cur + [w])) > max_chars
                    or w['s'] - cur[-1]['e'] > 0.35 or re.search(r'[.?!,]$', cur[-1]['w'])):
            groups.append(cur)
            cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    return groups


def write_srt(path, mw):
    lines = []
    for n, g in enumerate(caption_groups(mw, max_words=9, max_chars=42), 1):
        lines += [str(n), f"{fmt_ts(g[0]['s'], True)} --> {fmt_ts(max(g[-1]['e'], g[0]['s'] + 0.5), True)}",
                  ' '.join(x['w'] for x in g), '']
    path.write_text('\n'.join(lines))


def write_youtube(ep, plan, tl):
    ch = sorted(((tl.out(c['src'], c['t']), c['title']) for c in plan.get('chapters', [])))
    if ch and ch[0][0] < 10:
        ch[0] = (0.0, ch[0][1])  # YouTube needs the first chapter at 0:00
    rows = ([(0.0, 'Intro')] if not ch or ch[0][0] > 0 else []) + ch
    rows = [r for i, r in enumerate(rows) if i == 0 or r[0] - rows[i - 1][0] >= 10]  # YouTube needs >= 10s each
    txt = ['# YouTube upload', '', '## Title options', *[f"- {t}" for t in plan.get('title_options', [])], '',
           '## Description', '', plan.get('description', '').strip(), '', 'Chapters:',
           *[f"{fmt_ts(t)} {title}" for t, title in rows], '',
           'Captions: upload podcast-full.srt under Subtitles.', '']
    (ep / 'youtube.md').write_text('\n'.join(txt))


def ass_time(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def write_ass(path, mw):
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Anton,104,&H00FFFFFF,&H00FFFFFF,&H00141E0A,&H64000000,0,0,0,0,100,100,1,0,1,7,3,2,70,70,520,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for g in caption_groups(mw):
        for i, w in enumerate(g):
            s = w['s']
            e = g[i + 1]['s'] if i + 1 < len(g) else max(w['e'], s + 0.3)
            txt = ' '.join(('{\\c&H3DFFC9&}' + x['w'].upper() + '{\\c&HFFFFFF&}') if j == i else x['w'].upper()
                           for j, x in enumerate(g))
            ev.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Cap,,0,0,0,,{txt}")
    path.write_text(head + '\n'.join(ev) + '\n')


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:40] or 'reel'


def render_reels(cfg, ep, plan, srcs, trs):
    work = ep / 'work'
    keep = norm_keep(plan['keep'])
    outdir = ep / 'reels'
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir()
    cards = crew_cards(srcs, plan, work, 1080, 1920)
    made = []
    for n, r in enumerate(plan.get('reels', []), 1):
        rk = clip_keep(keep, r['src'], r['start'], r['end'])
        if not rk:
            print(f"  reel {n}: nothing kept in that range, skipped")
            continue
        tl = Timeline(rk)
        s = srcs[r['src']]
        crop = None
        if s['video'] and s['w'] / s['h'] > 9 / 16 + 0.05:
            fx = r.get('crop_x') if r.get('crop_x') is not None else face_center(s['path'], r['start'], r['end'], 6)[0]
            cw = int(s['h'] * 9 / 16) // 2 * 2
            cx = int(min(max(fx * s['w'] - cw / 2, 0), s['w'] - cw))
            crop = f"crop={cw}:{s['h']}:{cx}:0"
        vf = lambda src, _x, crop=crop: (f"fps={FPS},{crop},scale=1080:1920,setsar=1" if crop
                                        else fit_filter(srcs[src], 1080, 1920))
        lst = encode_segments(cfg, srcs, [(x, a, b, None) for x, a, b in rk], work / f"reel{n:02d}", 'r',
                              1080, 1920, vf, cards.get)
        ass = work / f"reel{n:02d}.ass"
        write_ass(ass, mapped_words(trs, rk))
        hook_d, end_d = 3.2, 2.6
        gj = [{'type': 'hook', 'data': {'text': r.get('hook', ''), 'kicker': r.get('kicker', 'Hawks War Room')},
               'w': 1080, 'h': 1920, 'dur': hook_d, 'out': str(work / f"reel{n:02d}-hook.mov")},
              {'type': 'endcard', 'data': {}, 'w': 1080, 'h': 1920, 'dur': end_d, 'out': str(work / f"reel{n:02d}-end.mov")}]
        render_graphics(gj, work, f"reel{n:02d}-gfx.json")
        audio = measure_loudness(lst, 'highpass=f=70,afftdn=nf=-25,', cfg['reel_loudness'])
        end_at = max(0, tl.total - end_d)
        esc = lambda p: str(p).replace('\\', '/').replace(':', r'\:').replace("'", r"\'")
        filt = (f"[0:v]subtitles='{esc(ass)}':fontsdir='{esc(HERE / 'fonts')}'[cap];"
                f"[cap][1:v]overlay=0:0:eof_action=pass:enable='between(t,0,{hook_d})'[h];"
                f"[h][2:v]overlay=0:0:eof_action=pass:enable='gte(t,{end_at:.3f})',format=yuv420p[vout];"
                f"[0:a]{audio}[aout]")
        out = outdir / f"reel-{n:02d}-{slug(r.get('id') or r.get('hook', ''))}.mp4"
        run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst),
             '-i', gj[0]['out'], '-itsoffset', f"{end_at:.3f}", '-i', gj[1]['out'],
             '-filter_complex', filt, '-map', '[vout]', '-map', '[aout]', *cfg['video_args'], '-r', str(FPS),
             '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(out)])
        made.append({'file': f"reels/{out.name}", 'dur': round(tl.total, 1), **r})
        print(f"  reel {n}: {out.name} ({tl.total:.0f}s)")
    return made


def render_thumbs(ep, plan, srcs):
    work = ep / 'work'
    outdir = ep / 'thumbnails'
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir()
    jobs = []
    for n, t in enumerate(plan.get('thumbnails', []), 1):
        frame = work / f"thumbframe{n}.jpg"
        run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f"{t['t']:.3f}", '-i', str(srcs[t['src']]['path']),
             '-frames:v', '1', '-vf', 'scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720',
             '-q:v', '2', str(frame)])
        jobs.append({'type': 'thumbnail', 'w': 1280, 'h': 720, 'dur': 1, 'out': str(outdir / f"thumb-{n}.jpg"),
                     'data': {'image': frame.as_uri(), 'text': t.get('text', ''), 'tag': t.get('tag', '')}})
    render_graphics(jobs, work, 'thumb-jobs.json')


def removed_runs(trs, keep):
    """Stretches of speech the edit leaves out, per source, for the review page."""
    rows = []
    for letter, tr in sorted(trs.items()):
        ks = [(a, b) for s, a, b in keep if s == letter]
        run_words, start = [], None
        for w in tr.get('words', []):
            mid = (w['s'] + w['e']) / 2
            if any(a <= mid <= b for a, b in ks):
                if run_words:
                    rows.append((letter, start, ' '.join(run_words)))
                run_words = []
            else:
                if not run_words:
                    start = w['s']
                run_words.append(w['w'])
        if run_words:
            rows.append((letter, start, ' '.join(run_words)))
    return rows


def gfx_summary(g):
    d = g.get('data', {})
    if g['type'] == 'verdict':
        return f"{d.get('verdict', '')}: {d.get('line', '')}"
    if g['type'] == 'matchup':
        return f"{d.get('left', {}).get('name', '')} at {d.get('right', {}).get('name', '')} · {' · '.join(d.get('meta', []))}"
    if g['type'] == 'compare':
        return f"{d.get('title', '')}: " + ', '.join(f"{r['label']} {r.get('display', r['value'])}" for r in d.get('rows', []))
    for k in ('call', 'title', 'name', 'text', 'label'):
        if d.get(k):
            pre = d.get('value') or d.get('num') or ''
            return f"{pre} {d[k]}".strip()
    return json.dumps(d)[:120]


def write_review(ep, plan, srcs, trs, reels):
    keep = norm_keep(plan['keep'])
    tl = Timeline(keep)
    e = html.escape
    yt = (ep / 'youtube.md').read_text() if (ep / 'youtube.md').exists() else ''
    thumbs = sorted((ep / 'thumbnails').glob('*.jpg')) if (ep / 'thumbnails').exists() else []
    raw_total = sum(s['dur'] for s in srcs.values())
    src_rows = ''.join(
        f"<tr><td>{k}</td><td>{e(s['name'])}</td><td>{'video' if s['video'] else 'audio only'}</td><td>{fmt_ts(s['dur'])}</td>"
        f"<td>{fmt_ts(sum(b - a for x, a, b in keep if x == k))}</td><td>{e(s.get('recorded', ''))}</td></tr>" for k, s in srcs.items())
    g_rows = ''.join(f"<tr><td>{fmt_ts(tl.out(g['src'], g['t']))}</td><td>{e(g['type'])}</td><td>{e(gfx_summary(g))}</td></tr>"
                     for g in sorted(plan.get('graphics', []), key=lambda g: tl.out(g['src'], g['t'])))
    flags = ''.join(f"<li><b>{e(f.get('src', ''))} {fmt_ts(f.get('t', 0))}</b> {e(f.get('note', ''))}</li>" for f in plan.get('flags', []))
    reel_html = ''.join(
        f"<div class='reel'><video controls preload='metadata' src='{e(r['file'])}'></video><h3>{e(r.get('hook', '').replace('*', ''))}</h3>"
        f"<p class='muted'>{r['dur']}s · from {e(r['src'])} {fmt_ts(r['start'])}–{fmt_ts(r['end'])}</p><p>{e(r.get('why', ''))}</p></div>"
        for r in reels)
    cut_rows = ''.join(f"<tr><td>{k} {fmt_ts(t)}</td><td>{e(txt[:200])}</td></tr>" for k, t, txt in removed_runs(trs, keep))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review {e(ep.name)}</title><style>
body{{margin:0;background:#0a0f1c;color:#eff3f7;font:16px/1.5 system-ui,sans-serif}}main{{max-width:1100px;margin:0 auto;padding:24px 16px 80px}}
h1,h2{{font-family:Impact,sans-serif;text-transform:uppercase;letter-spacing:.01em;font-weight:400}}h2{{margin-top:40px;border-top:1px solid #283654;padding-top:20px}}
.muted{{color:#9eabc2}}.stats span{{display:inline-block;margin:0 18px 8px 0;font-family:monospace}}video{{width:100%;border-radius:10px;background:#000}}
.flags{{background:#402829;border:1px solid #ff8e85;border-radius:10px;padding:12px 18px 12px 34px}}table{{width:100%;border-collapse:collapse;font-size:14px}}
td,th{{border-bottom:1px solid #283654;padding:6px 8px;text-align:left;vertical-align:top}}td:first-child{{font-family:monospace;white-space:nowrap}}
.reels{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:18px}}.reel video{{aspect-ratio:9/16}}.reel h3{{font-size:16px;margin:8px 0 2px}}
.thumbs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}.thumbs img{{width:100%;border-radius:8px}}
pre{{white-space:pre-wrap;background:#141e33;border:1px solid #283654;border-radius:10px;padding:14px}}.howto{{background:#1a2c2c;border-left:4px solid #c9ff3d;padding:12px 16px}}
</style></head><body><main>
<p class="muted">HAWKS WAR ROOM · REVIEW · built {time.strftime('%b %d, %Y %H:%M')}</p><h1>{e(ep.name)} ({e(plan.get('kind', ''))})</h1>
<div class="stats"><span>Raw: {fmt_ts(raw_total)}</span><span>Edited: {fmt_ts(tl.total)}</span><span>Removed: {fmt_ts(raw_total - tl.total)}</span><span>Pieces: {len(keep)}</span><span>Graphics: {len(plan.get('graphics', []))}</span><span>Reels: {len(reels)}</span></div>
<div class="howto">Approve with <b>"approve {e(ep.name)}"</b>. Or send notes: "cut A 12:40 to 13:05", "drop reel 2", "move Matt's clip after Thing 4", "graphic at 4:10 has the wrong week".</div>
{f'<h2>Check these first</h2><ul class="flags">{flags}</ul>' if flags else ''}
<h2>Full episode</h2><video controls preload="metadata" src="podcast-full.mp4"></video>
<h2>Reels</h2><div class="reels">{reel_html or '<p class="muted">No reels in the plan.</p>'}</div>
<h2>Thumbnails</h2><div class="thumbs">{''.join(f"<img src='thumbnails/{t.name}' alt='Thumbnail option'>" for t in thumbs) or '<p class="muted">None.</p>'}</div>
<h2>YouTube text</h2><pre>{e(yt)}</pre>
<h2>Source files</h2><table><tr><th>Letter</th><th>File</th><th>Type</th><th>Length</th><th>Used</th><th>Recorded</th></tr>{src_rows}</table>
<h2>Graphics</h2><table><tr><th>Edited time</th><th>Type</th><th>Shows</th></tr>{g_rows}</table>
<h2>What got cut</h2><p class="muted">Every stretch of speech the edit leaves out (source letter and raw time), so you can catch a bad cut.</p><table><tr><th>Source time</th><th>Removed words</th></tr>{cut_rows}</table>
</main></body></html>"""
    (ep / 'review.html').write_text(page)


def validate(plan, srcs):
    errs = []
    for i, (s, a, b) in enumerate(norm_keep(plan.get('keep', []))):
        if s not in srcs:
            errs.append(f"keep[{i}] uses unknown source {s}")
        elif not (0 <= a < b <= srcs[s]['dur'] + 0.5):
            errs.append(f"keep[{i}] {s} {a}-{b} is outside the file ({srcs[s]['dur']:.1f}s)")
    for key in ('graphics', 'chapters', 'thumbnails', 'reels'):
        for i, g in enumerate(plan.get(key, [])):
            if g.get('src') not in srcs:
                errs.append(f"{key}[{i}] needs a valid 'src' letter")
    for i, r in enumerate(plan.get('reels', [])):
        if r.get('src') in srcs and not srcs[r['src']]['video']:
            errs.append(f"reels[{i}] comes from an audio-only source")
        elif r.get('src') in srcs and r['end'] - r['start'] < 12:
            print(f"  warning: reels[{i}] is under 12s; the hook and end card will cover most of it")
    if errs:
        sys.exit("plan.json problems:\n  " + '\n  '.join(errs))


def render(cfg, ep, only=None):
    if not (ep / 'plan.json').exists():
        sys.exit(f"{ep.name}: no plan.json yet (Claude writes it from plan.draft.json; see PLAYBOOK.md)")
    plan = json.loads((ep / 'plan.json').read_text())
    srcs = sources_of(ep)
    trs = load_transcripts(ep)
    validate(plan, srcs)
    (ep / 'work' / 'gfx').mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print(f"{ep.name}: rendering")
    save_state(ep, status='rendering')
    if only in (None, 'longform'):
        render_longform(cfg, ep, plan, srcs, trs)
    if only in (None, 'reels'):
        reels = render_reels(cfg, ep, plan, srcs, trs)
        (ep / 'work' / 'reels.json').write_text(json.dumps(reels))
    reels = json.loads((ep / 'work' / 'reels.json').read_text()) if (ep / 'work' / 'reels.json').exists() else []
    if only in (None, 'thumbs'):
        render_thumbs(ep, plan, srcs)
    write_review(ep, plan, srcs, trs, reels)
    save_state(ep, status='awaiting-approval')
    print(f"{ep.name}: done in {time.time() - t0:.0f}s -> {ep / 'review.html'}")


# ---------- approve / status ----------
def approve(cfg, ep):
    if ep.parent == cfg['approved']:
        sys.exit(f"{ep.name} is already approved")
    if cfg['repo']:
        dest = Path(cfg['repo']) / 'seahawks' / 'episodes' / ep.name
        dest.mkdir(parents=True, exist_ok=True)
        for name in ('transcript.txt', 'plan.json', 'youtube.md', 'podcast-full.srt'):
            if (ep / name).exists():
                shutil.copy2(ep / name, dest / name)
        print(f"blog material copied to {dest}")
    else:
        print('note: "repo" is not set in config.json, so nothing was copied for the blog')
    raw_dest = cfg['raw'] / ep.name
    if (ep / 'raw').exists():
        raw_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(ep / 'raw'), str(raw_dest))
    shutil.rmtree(ep / 'work', ignore_errors=True)  # intermediates only; everything in it can be rebuilt
    final = cfg['approved'] / ep.name
    final.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(ep), str(final))
    st = load_state(final)
    st.update(status='approved', raw_folder=str(raw_dest), updated=time.strftime('%Y-%m-%d %H:%M'))
    (final / 'state.json').write_text(json.dumps(st, indent=2))
    print(f"{ep.name}: approved -> {final}; raw footage -> {raw_dest}")


def status(cfg):
    rows = []
    for base in (cfg['outbox'], cfg['approved']):
        if base.exists():
            rows += [p for p in base.iterdir() if (p / 'state.json').exists()]
    waiting = [f.name for f in cfg['inbox'].iterdir()] if cfg['inbox'].exists() else []
    waiting = [n for n in waiting if not n.startswith('.') and Path(n).suffix.lower() in VIDEO_EXT | AUDIO_EXT]
    print(f"drop folder: {len(waiting)} file(s) waiting" + (f" ({', '.join(waiting)})" if waiting else ''))
    for ep in sorted(rows, key=lambda p: p.name):
        st = load_state(ep)
        print(f"{ep.name:24} {st.get('status', '?'):18} {len(st.get('sources', {}))} source(s)  {st.get('updated', '')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['status', 'inbox', 'transcribe', 'autocut', 'render', 'approve'])
    ap.add_argument('episode', nargs='?')
    ap.add_argument('--episode', dest='episode_opt')
    ap.add_argument('--only', choices=['longform', 'reels', 'thumbs', 'review'])
    ap.add_argument('--source')
    a = ap.parse_args()
    cfg = load_config()
    if a.cmd == 'status':
        return status(cfg)
    if a.cmd == 'inbox':
        return inbox(cfg, a.episode_opt or a.episode)
    if not a.episode:
        sys.exit("which episode?")
    ep = episode_dir(cfg, a.episode)
    {'transcribe': lambda: transcribe(cfg, ep, a.source), 'autocut': lambda: autocut(cfg, ep),
     'render': lambda: render(cfg, ep, a.only), 'approve': lambda: approve(cfg, ep)}[a.cmd]()


if __name__ == '__main__':
    main()

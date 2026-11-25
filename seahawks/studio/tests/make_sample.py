#!/usr/bin/env python3
"""Builds a synthetic three-source episode and runs the studio pipeline on it end to end.

Needs ffmpeg, espeak-ng, node + Playwright. Skips Whisper (no model download needed): the
transcript comes from the text-to-speech script, with word times estimated per phrase.

  python3 tests/make_sample.py /tmp/hwr-test
"""
import json, subprocess, sys, wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import studio  # noqa: E402

FONT = HERE.parent / 'fonts' / 'IBMPlexMono-SemiBold.ttf'

MAIN = [
    ("Welcome to the Hawks War Room. Week twelve, Seattle at San Francisco.", 0.4),
    ("Um", 0.5),
    ("Let's get into the ten things I'm watching on Sunday.", 1.8),
    ("Thing one. Protect the quarterback early.", 0.5),
    ("My call is no sacks on the opening drive.", 2.2),
    ("Uh", 0.4),
    ("Thing two. Run the ball at least twenty five times.", 0.6),
    ("The run game has improved three straight weeks and I want that to keep going.", 1.5),
    ("Here's a hot take. Seattle wins this game by a touchdown.", 1.0),
]
VOICE_MEMO = [("Hey Jesse, it's Matt. I think the defensive line wins this game. Six sacks again.", 0.3)]
VERTICAL = [("Quick one from the parking lot. The crowd is going to be loud for this one.", 0.3)]


def tts(phrases, out_wav):
    """Speak each phrase, join with pauses, return word timings."""
    tmp = out_wav.parent / 'tts'
    tmp.mkdir(exist_ok=True)
    frames, words, segs, t, rate = b'', [], [], 0.25, 22050
    frames += b'\0\0' * int(rate * t)
    for i, (text, pause) in enumerate(phrases):
        f = tmp / f"{out_wav.stem}-{i}.wav"
        subprocess.run(['espeak-ng', '-v', 'en-us', '-s', '165', '-w', str(f), text], check=True)
        with wave.open(str(f)) as w:
            rate = w.getframerate()
            data = w.readframes(w.getnframes())
        d = len(data) / 2 / rate
        toks = text.split()
        weights = [len(x) + 2 for x in toks]
        span_s, span_e = t + 0.05, t + d - 0.1
        c = span_s
        for tok, wt in zip(toks, weights):
            wd = (span_e - span_s) * wt / sum(weights)
            words.append({'w': tok, 's': round(c, 3), 'e': round(c + wd, 3)})
            c += wd
        segs.append({'s': round(span_s, 3), 'e': round(span_e, 3), 'text': text})
        frames += data + b'\0\0' * int(rate * pause)
        t += d + pause
    with wave.open(str(out_wav), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return {'words': words, 'segments': segs}, t


def make_video(wav, dur, out, size, label, color):
    w, h = size
    draw = (f"drawtext=fontfile={FONT}:text='{label}  %{{pts\\:hms}}':x=60:y=60:fontsize={h // 22}:fontcolor=white,"
            f"drawbox=x='(w-{w // 6})/2':y='h*0.25':w={w // 6}:h={w // 6}:color=0xc9ff3d@0.8:t=fill")
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', f"color=c={color}:s={w}x{h}:r=30:d={dur:.2f}",
                    '-i', str(wav), '-vf', draw, '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-shortest', str(out)], check=True)


def main(root):
    root = Path(root)
    drop = root / '01 Drop Videos Here'
    drop.mkdir(parents=True, exist_ok=True)
    gen = root / 'gen'
    gen.mkdir(exist_ok=True)
    tr_a, da = tts(MAIN, gen / 'main.wav')
    tr_b, db = tts(VOICE_MEMO, gen / 'memo.wav')
    tr_c, dc = tts(VERTICAL, gen / 'vert.wav')
    make_video(gen / 'main.wav', da, drop / 'IMG_0001.MOV', (1920, 1080), 'SOURCE A', '0x22303f')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(gen / 'memo.wav'), '-c:a', 'aac',
                    str(drop / 'Matt voice memo.m4a')], check=True)
    make_video(gen / 'vert.wav', dc, drop / 'IMG_0002.MOV', (1080, 1920), 'SOURCE C', '0x3f2a22')
    for i, f in enumerate(['IMG_0001.MOV', 'Matt voice memo.m4a', 'IMG_0002.MOV']):  # fake recording order
        subprocess.run(['touch', '-d', f"2026-11-24 19:0{i}:00", str(drop / f)], check=True)

    cfg = studio.load_config()
    cfg.update(root=root, inbox=drop, outbox=root / '02 Ready for Review', approved=root / '03 Approved',
               raw=root / '04 Raw Footage', repo='', settle_minutes=0, workers=4)
    studio.transcribe = lambda cfg, ep, only=None: None  # no Whisper here; use the TTS script instead
    real_autocut = studio.autocut
    studio.autocut = lambda cfg, ep: None
    studio.inbox(cfg, '2026-w12-pre')
    ep = cfg['outbox'] / '2026-w12-pre'
    st = studio.load_state(ep)
    by_name = {v['name']: k for k, v in st['sources'].items()}
    trs = {by_name['IMG_0001.MOV']: tr_a, by_name['Matt voice memo.m4a']: tr_b, by_name['IMG_0002.MOV']: tr_c}
    studio.write_transcripts(ep, trs)
    real_autocut(cfg, ep)

    draft = json.loads((ep / 'plan.draft.json').read_text())
    A, B, C = by_name['IMG_0001.MOV'], by_name['Matt voice memo.m4a'], by_name['IMG_0002.MOV']
    ka = [k for k in draft['keep'] if k[0] == A]
    kb = [k for k in draft['keep'] if k[0] == B]
    kc = [k for k in draft['keep'] if k[0] == C]
    w = {x['w'].strip('.,'): x for x in tr_a['words']}
    split = w['Thing'] ['s'] if 'Thing' in w else ka[len(ka) // 2][1]
    first_thing = next(x for x in tr_a['words'] if x['w'] == 'Thing')
    second_thing = [x for x in tr_a['words'] if x['w'] == 'Thing'][1]
    hot = next(x for x in tr_a['words'] if x['w'] == 'Here\'s')
    # play order: A up to "Thing two", Matt's memo, rest of A, the vertical clip at the end
    keep = [k for k in ka if k[2] <= second_thing['s'] + 0.01] + kb + \
           [k for k in ka if k[2] > second_thing['s'] + 0.01] + kc
    plan = {**draft, 'keep': keep,
            'crew': {B: {'name': 'Matt M.', 'question': 'Who wins the line of scrimmage?'}},
            'title_options': ['Seahawks at 49ers: 10 Things to Watch | Hawks War Room', 'Can Seattle Win in Santa Clara?'],
            'description': 'Week 12 game prep. TEST EPISODE built from synthetic audio.',
            'chapters': [{'src': A, 't': first_thing['s'], 'title': 'Thing 1: Protect the QB'},
                         {'src': A, 't': second_thing['s'], 'title': 'Thing 2: Run the ball'},
                         {'src': A, 't': hot['s'], 'title': 'The pick'}],
            'graphics': [
                {'src': A, 't': 0.5, 'dur': 5, 'type': 'matchup', 'data': {'kicker': 'Week 12 · TEST DATA', 'left': {'name': 'Seahawks', 'record': '0-0'}, 'right': {'name': '49ers', 'record': '0-0'}, 'meta': ['TEST', 'NOT REAL']}},
                {'src': A, 't': first_thing['s'], 'dur': 4, 'type': 'thing', 'data': {'num': 1, 'title': 'Protect the QB early'}},
                {'src': A, 't': first_thing['s'] + 3.5, 'dur': 5, 'type': 'call', 'data': {'num': 1, 'call': 'No sacks on the opening drive.'}},
                {'src': A, 't': second_thing['s'], 'dur': 4, 'type': 'thing', 'data': {'num': 2, 'title': 'Run the ball'}},
                {'src': A, 't': second_thing['s'] + 4, 'dur': 5, 'type': 'stat', 'data': {'value': '150', 'label': 'TEST rushing yards', 'source': 'test fixture'}},
            ],
            'reels': [{'src': A, 'start': hot['s'] - 0.2, 'end': tr_a['words'][-1]['e'] + 0.4, 'id': 'hot-take',
                       'hook': 'Seattle wins by *a touchdown*', 'why': 'Bold, specific, checkable call.'}],
            'thumbnails': [{'src': A, 't': 5, 'text': 'Week 12: *Ten things* to watch', 'tag': 'SEAHAWKS AT 49ERS · TEST'}],
            'flags': [{'src': A, 't': 10, 'note': 'Test flag: this is where a misstated stat would be called out.'}]}
    (ep / 'plan.json').write_text(json.dumps(plan, indent=1))
    studio.render(cfg, ep)
    return ep


if __name__ == '__main__':
    print(main(sys.argv[1] if len(sys.argv) > 1 else '/tmp/hwr-test'))

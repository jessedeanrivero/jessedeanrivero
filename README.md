# jessedeanrivero.com

Two pages, one static site. Home is the scroll-driven video site; `/playlist-submissions` is the SEO-preserved pitch page redesigned to match. Drops onto Vercel with no build step.

## Structure
```
index.html                    Home (scroll-scrubbed video)
playlist-submissions/
  index.html                  Playlist Submissions page
frames-desktop/               200 WebP frames @1920×1080 (~15 MB)
frames-mobile/                200 WebP frames @720×1280, vertical (~7 MB)
sitemap.xml  robots.txt  vercel.json
```

## Preview locally
From inside this folder:
```
python3 -m http.server 8080
```
Open **http://localhost:8080** (and the nav link to Playlist Submissions works). Run it through the server, not by double-clicking — the frames load over HTTP.

## What changed this round
- **Smoother scrub.** 200 dense frames pulled from your 15s clips (vs 160 sampled across a 60s clip before). Light denoise applied to kill grain flicker during the scrub. Desktop and mobile use your separate landscape/vertical cuts.
- **Copy:** dropped the redundant subhead; closing line is now **"Let's make music."**; signoff is now an **email link + Instagram** (@thejessephillips) instead of the Nashville line.
- **Persistent menu** (top, stays on screen): Playlist Submissions (live), Worship Bass 101 + Tools For Worship (marked "Soon", not clickable). Mobile gets a hamburger overlay. Songstage / Real Fun slot in later as two more links.
- **Layout:** since you're framed on the left of the new video, the copy is biased right/center so text never sits on top of you.

## Connecting the form — done

The pitch form posts to your Google Form behind the scenes. Visitors see your custom-designed form; you get responses in the Form (and its linked Sheet). No Apps Script, no OAuth, no "blocked app" screen.

**Turn on email alerts** (one-time, in the Google Form): open the Form → **Responses** tab → ⋮ (three dots) → **Get email notifications for new responses**. Done.

If you ever edit the Google Form's questions, the underlying `entry.xxxx` IDs can change. If that happens, generate a fresh pre-filled link (Form ⋮ → "Get pre-filled link," fill dummies, copy the URL) and update the `ENTRY` map near the bottom of `playlist-submissions/index.html`.

## SEO + AI search
The ranking page is preserved and hardened:
- **Title** = "Spotify Playlist Submission for Worship and Christian Songs" (your suffix removed, as requested). **Meta description, OG, and Twitter copy** kept verbatim.
- **Google site-verification token** carried over, so Search Console stays verified.
- **Canonical** set to `https://jessedeanrivero.com/playlist-submissions`, and `vercel.json` uses `cleanUrls` so that exact path (no trailing slash) is preserved character-for-character — the thing your ranking is tied to.
- **Structured data:** Person + services on home; WebPage + **FAQPage** on the playlist page (the FAQ markup is what AI/answer engines love to quote).
- **robots.txt** explicitly welcomes GPTBot, OAI-SearchBot, PerplexityBot, ClaudeBot, and Google-Extended, plus the sitemap.
- Added an on-page intro paragraph that restates your ranking keywords in plain, answer-shaped language (good for both Google and AI search) without changing the page's intent.
- `og:image` on the playlist page still points at your old Squarespace screenshot — swap it for a hosted image when you have one.

## Deploy
Drag this folder into a Vercel project (or run `vercel`). Static, no build. `vercel.json` handles clean URLs, 301s for your old Squarespace paths, and long-cache headers on the frames. Keep the domain pointed here and your `/playlist-submissions` ranking carries over.

// Renders Hawks War Room graphics from graphics.html.
// Usage: node render.cjs jobs.json
// jobs.json: [{ "type", "data", "w", "h", "dur", "fps", "out" }]
//   out ending in .mov  -> transparent animated overlay (PNG codec in MOV)
//   out ending in .png  -> transparent still
//   out ending in .jpg  -> opaque still (thumbnails)
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const page_url = 'file://' + path.join(__dirname, 'graphics.html');
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  for (const job of jobs) {
    const { type, data = {}, w = 1920, h = 1080, dur = 4, fps = 30, out } = job;
    await page.setViewportSize({ width: w, height: h });
    await page.goto(page_url);
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(([t, d, du, ww, hh]) => window.init(t, d, du, ww, hh), [type, data, dur, w, h]);
    await page.evaluate(() => document.fonts.ready);
    const ext = path.extname(out).toLowerCase();
    fs.mkdirSync(path.dirname(out), { recursive: true });
    if (ext === '.png' || ext === '.jpg' || ext === '.jpeg') {
      await page.evaluate(t => window.frame(t), Math.min(2, dur / 2));
      await page.screenshot({ path: out, omitBackground: ext === '.png', type: ext === '.png' ? 'png' : 'jpeg', quality: ext === '.png' ? undefined : 92 });
    } else {
      const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hwr-frames-'));
      const n = Math.round(dur * fps);
      for (let i = 0; i < n; i++) {
        await page.evaluate(t => window.frame(t), i / fps);
        await page.screenshot({ path: path.join(dir, String(i).padStart(5, '0') + '.png'), omitBackground: true });
      }
      execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', path.join(dir, '%05d.png'),
        '-c:v', 'png', '-pix_fmt', 'rgba', out]);
      fs.rmSync(dir, { recursive: true, force: true });
    }
    process.stdout.write(`rendered ${out}\n`);
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });

// Judah's Star Jar API (jessedeanrivero.com/judahstars)
// Reads and writes the "Judah's Star Jar" Airtable base.
// Env vars (Vercel > Project > Settings > Environment Variables):
//   AIRTABLE_TOKEN  personal access token scoped to only this base
//   FAMILY_USERS    who can log in, as Name:PIN pairs, e.g. "Jesse:1111,Kendall:2222"
// Every request (reading included) needs a name and PIN from FAMILY_USERS.
// PINs live only in Vercel, never in this public repo.

const BASE_ID = process.env.AIRTABLE_BASE_ID || "app9GXLbY0cAAIYCJ";
const TOKEN = process.env.AIRTABLE_TOKEN;
const USERS = String(process.env.FAMILY_USERS || "")
  .split(",")
  .map(pair => {
    const i = pair.lastIndexOf(":");
    return i > 0 ? { name: pair.slice(0, i).trim(), pin: pair.slice(i + 1).trim() } : null;
  })
  .filter(u => u && u.name && u.pin);
const GOAL = 100;

const STARS = "tblfcTqngMikUHywA";
const SETTINGS = "tblnKAcSYeztAQbzJ";
const F = {
  reason: "fldJnc0ql5noHP8yS",
  by: "flddBxpPL8VqYygJr",
  at: "fldUVOpNS0WYbqTmy",
  jar: "fld56AJf3QNx3VvtP",
  carried: "fld0N6aGI4QXgktsz",
};
const S = {
  name: "fldirMjdjHRnNZXMn",
  jar: "fldyxd51IRWEyZ9BG",
  prize: "fldvJRVUfCCuaHnZG",
  challenges: "fldGOvUkmbbsl4dzZ",
  filled: "fldbgHSR51lQncPR8",
};
const DEFAULT_CHALLENGES = [
  "Made his bed", "Cleaned his room", "Finished homework", "Read for 20 minutes",
  "Helped without being asked", "Kind to his brother", "Great effort at soccer",
  "Tried a new food", "Brushed teeth, no reminder", "Good listening",
];

class HttpError extends Error {
  constructor(status, code, message) { super(message); this.status = status; this.code = code; }
}

async function airtable(path, opts = {}) {
  const r = await fetch(`https://api.airtable.com/v0/${BASE_ID}/${path}`, {
    ...opts,
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  const text = await r.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (_) { /* not json */ }
  if (!r.ok) {
    const msg = (data && data.error && (data.error.message || data.error.type)) || `Airtable error ${r.status}`;
    throw new HttpError(502, r.status === 401 || r.status === 403 ? "token" : "airtable", msg);
  }
  return data;
}

async function getSettings() {
  const q = new URLSearchParams({ pageSize: "1", returnFieldsByFieldId: "true" });
  const d = await airtable(`${SETTINGS}?${q}`);
  let rec = d.records && d.records[0];
  if (!rec) {
    const created = await airtable(`${SETTINGS}?returnFieldsByFieldId=true`, {
      method: "POST",
      body: JSON.stringify({ records: [{ fields: { [S.name]: "Main", [S.jar]: 1, [S.challenges]: DEFAULT_CHALLENGES.join("\n"), [S.filled]: 0 } }] }),
    });
    rec = created.records[0];
  }
  const f = rec.fields || {};
  return {
    id: rec.id,
    jar: Number(f[S.jar]) || 1,
    prize: typeof f[S.prize] === "string" ? f[S.prize] : "",
    challenges: String(f[S.challenges] || "").split("\n").map(s => s.trim()).filter(Boolean),
    jarsFilled: Number(f[S.filled]) || 0,
  };
}

async function getStars(jar) {
  const out = [];
  let offset;
  do {
    const q = new URLSearchParams({ pageSize: "100", returnFieldsByFieldId: "true", filterByFormula: `{Jar}=${Number(jar)}` });
    if (offset) q.set("offset", offset);
    const d = await airtable(`${STARS}?${q}`);
    for (const rec of d.records || []) {
      const f = rec.fields || {};
      out.push({
        id: rec.id,
        reason: typeof f[F.reason] === "string" ? f[F.reason] : "",
        by: typeof f[F.by] === "string" ? f[F.by] : "",
        at: Date.parse(f[F.at] || rec.createdTime) || 0,
        carried: !!f[F.carried],
      });
    }
    offset = d.offset;
  } while (offset && out.length < 400);
  out.sort((a, b) => a.at - b.at);
  return out;
}

async function getState() {
  const settings = await getSettings();
  const stars = await getStars(settings.jar);
  return { settings, stars };
}

function publicState({ settings, stars }) {
  const { id, ...rest } = settings;
  return { ...rest, goal: GOAL, stars };
}

function login(name, pin) {
  if (!USERS.length) throw new HttpError(503, "setup", "Logins aren't set up yet.");
  const n = String(name || "").trim().toLowerCase();
  const u = USERS.find(x => x.name.toLowerCase() === n);
  if (!u || u.pin !== String(pin || "").trim()) throw new HttpError(401, "login", "That name and PIN didn't match.");
  return u.name;
}

const clean = (v, max) => String(v == null ? "" : v).replace(/\s+/g, " ").trim().slice(0, max);

async function patchSettings(id, fields) {
  await airtable(SETTINGS, { method: "PATCH", body: JSON.stringify({ records: [{ id, fields }] }) });
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  try {
    if (!TOKEN) throw new HttpError(503, "setup", "The Airtable token isn't set up yet.");

    if (req.method === "GET") {
      const h = req.headers || {};
      login(h["x-star-user"], h["x-star-pin"]);
      return res.status(200).json(publicState(await getState()));
    }
    if (req.method !== "POST") throw new HttpError(405, "method", "Not allowed.");

    let body = req.body;
    if (typeof body === "string") { try { body = JSON.parse(body); } catch (_) { body = {}; } }
    body = body || {};

    const user = login(body.user, body.pin);

    const action = body.action;
    let state = await getState();
    const { settings, stars } = state;

    if (action === "check") {
      // login is fine, just return the jar plus the name as stored
    } else if (action === "give") {
      const room = GOAL - stars.length;
      if (room <= 0) throw new HttpError(409, "full", "The jar is full! Start a new jar first.");
      const n = Math.min(Math.max(1, Math.floor(Number(body.count) || 1)), 99, room);
      const carried = n > 1 || !!body.carried;
      const reason = clean(body.reason, 60) || (carried ? "Carried over" : "A star");
      const by = user;
      const now = Date.now();
      const records = Array.from({ length: n }, (_, i) => ({
        fields: {
          [F.reason]: reason,
          [F.by]: by,
          [F.at]: new Date(now + i).toISOString(),
          [F.jar]: settings.jar,
          [F.carried]: carried,
        },
      }));
      for (let i = 0; i < records.length; i += 10) {
        await airtable(STARS, { method: "POST", body: JSON.stringify({ records: records.slice(i, i + 10) }) });
      }
    } else if (action === "remove") {
      const id = String(body.id || "");
      if (!/^rec[A-Za-z0-9]{14}$/.test(id)) throw new HttpError(400, "bad", "That star couldn't be found.");
      await airtable(`${STARS}/${id}`, { method: "DELETE" });
    } else if (action === "prize") {
      await patchSettings(settings.id, { [S.prize]: clean(body.prize, 60) });
    } else if (action === "challenges") {
      const list = Array.isArray(body.challenges) ? body.challenges.map(c => clean(c, 50)).filter(Boolean).slice(0, 30) : [];
      await patchSettings(settings.id, { [S.challenges]: list.join("\n") });
    } else if (action === "newjar") {
      const full = stars.length >= GOAL;
      const fields = { [S.jar]: settings.jar + 1, [S.filled]: settings.jarsFilled + (full ? 1 : 0) };
      if (full) fields[S.prize] = "";
      await patchSettings(settings.id, fields);
    } else {
      throw new HttpError(400, "bad", "Unknown action.");
    }

    if (action !== "check") state = await getState();
    return res.status(200).json({ ...publicState(state), user });
  } catch (e) {
    const status = e instanceof HttpError ? e.status : 500;
    const code = e instanceof HttpError ? e.code : "server";
    return res.status(status).json({ error: code, message: e.message || "Something went wrong." });
  }
};

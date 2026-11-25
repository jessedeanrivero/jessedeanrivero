# Hawks War Room: Claude Code instructions

Read this whole file before every weekly preview or postgame update. Part A records how this repo actually works. Part B is Jesse's editorial handoff, kept verbatim. Where they disagree, Part A (the real code) wins. Say so in the status report.

## Part A: Verified repo conventions (checked 2026-11-24)

- **Site root:** `seahawks/` is the hawkswarroom.com site. It has its own `vercel.json` (`cleanUrls: true`). Everything else in this repo belongs to jessedeanrivero.com and other projects. Don't touch it during a Hawks update.
- **Assets:** `seahawks/assets/` (lowercase), served at `/assets/<file>`. The handoff's `/Seahawks/assets` means this folder.
- **Game routes:** the preview is `seahawks/g/<season>-w<N>.html`, served at `/g/2026-wN`. The postgame is a **separate** page, `seahawks/g/<season>-w<N>-recap.html`, served at `/g/2026-wN-recap`. The handoff says to put the postgame on "the same archive entry". In this repo that means the linked preview + recap pair: leave the preview page unchanged and add the recap next to it. Playoff pages use `2025-div-recap`, `2025-conf-recap` and `2025-sb-recap`.
- **Homepage (`seahawks/index.html`) touchpoints:** meta/OG tags, the top info bar (record), `.gameday-label`, the current-game hero link, `.primetime-lead`, the helmet results strip, and the `.arch` season archive (recap and prep entries for each week). Call the Plays lives at `seahawks/calltheplays/index.html`.
- **Data:** `seahawks/data/2026-prediction-leaderboard.json` is the season prediction leaderboard. Its scoring is the sum of absolute Seattle and opponent errors, and lowest total wins. It also has a `newcomerPolicy`: anyone who joins late gets that week's worst error for each week they missed. That is the existing rule, so follow it for the leaderboard only. Never use it to invent a pick on a game page. The only model output on file is `data/2026-w3-model.json`.
- **Build/checks:** static HTML with no `package.json`, no build, no lint and no tests. To check a change: serve `seahawks/` locally (`python3 -m http.server`), scan for broken local `src`/`href`/`url()` references, and screenshot at desktop and phone widths with Playwright.
- **Never touch Songstage.** Hawks War Room work must never read, change or deploy anything in Songstage: not its Vercel team (`songstages-projects`), not its projects, not its repos. Use only Jesse's personal Vercel connection (scope `jessedeanrivero-9576s-projects`).
- **Deploy (verified 2026-11-25):** the Vercel project is `jessedeanrivero-seahawks` (`prj_tVm7CkkvdqSqZ6pLAyuzQSV2PbrW`, team `team_Ajpn9P2HlAh8xOkbNIRSiTCv`). A push to `main` deploys to production at hawkswarroom.com. A push to any other branch builds a preview deployment, which Vercel login protects. Only push to `main` when Jesse explicitly asks to go live, then fetch the live page to confirm it.
- **Sitemap:** `seahawks/sitemap.xml` is updated by hand. Add the new game URLs every week.
- **Not served:** `CLAUDE.md` is listed in `seahawks/.vercelignore` so these notes don't get published.
- **Known issues found 2026-11-24 (not yet fixed):** the sitemap stops at 2026-11-04, so the Week 9 and Week 10 pages and `/the53` are missing. `g/2026-w6-recap.html:37` points at `/assets/7ECBDCC0-1B68-44B9-B755-5B75E0B37CE2.png`, which isn't in the repo. `g/2026-w4.html:33` links to `/seahawks`, which doesn't exist on this domain.

## Part B: Editorial handoff (verbatim)

# Hawks War Room: Claude Code Project Handoff

> Project: Hawks War Room, https://hawkswarroom.com  
> Team: Seattle Seahawks  
> Owner and editorial voice: Jesse  
> Primary workflows: Weekly game preview, postgame review, and publishing to the existing site  
> Intended use: Put this file in the repository and have Claude Code read it before each weekly update. Merge the core rules into an existing `CLAUDE.md` if one already exists.

## 1. Mission

Hawks War Room is Jesse's Seahawks scouting, predictions, and game review site. It should feel like an informed fan's personal war room, backed by reliable football research, not a generic sports news site.

Every game has a two-part editorial cycle:

1. **Pregame preview:** Research the matchup, publish a scouting breakdown, write **10 Things to Watch**, collect predictions, and make clear, testable calls.
2. **Postgame review:** Report what happened, compare it with the original preview, grade the 10 calls and contributor predictions, add Jesse's observations, and carry lessons into the next game.

The preview and review belong to the **same game in the season archive**. Preserve the original preview. The postgame update should show what we predicted before kickoff and what happened afterward, not rewrite history to make the predictions look better.

## 2. First, Inspect the Existing Repository

Before writing code or editing content:

- Read the repository structure, `README`, package scripts, existing `CLAUDE.md`, deployment setup, data files, current homepage, and recent game pages.
- Find the current content model and route conventions. A previous game route has used `/g/2026-w4`, but **do not assume this route remains authoritative**. Follow the real implementation.
- Find the actual hero image asset directory and existing image references. The user has previously referred to the GitHub `/Seahawks/assets` folder. Verify case and paths before using it.
- Identify the source of truth for standings, records, analytics, model picks, contributor predictions, schedule, and archived games. Reuse existing components and calculations.
- Inspect the current postgame and preview layouts before changing design. Keep the site cohesive.
- Check scripts for linting, tests, type checking, and building. Run the available checks on every edit.
- Confirm the Git branch, deployment workflow, and whether a push to the tracked branch publishes to Vercel. **Never assume a local edit equals a live deployment.**

If the local repo has a conflicting convention, follow the actual code and explain the discrepancy. Do not invent paths, APIs, names, or files.

## 3. Standing Editorial Rules

### Voice

- Use Jesse's voice: direct, informed, optimistic about Seattle without excusing poor execution, occasionally funny, and comfortable with criticism.
- Write like a Seahawks fan who watches line play, execution, coaching decisions, efficiency, and situational football. Avoid canned sports clichés and breathless hype.
- Distinguish **Jesse's own commentary** from research and model outputs. If Jesse sends dictated thoughts, preserve the point of view and the meaning while lightly cleaning up dictation.
- Never put a made-up quotation in Jesse's mouth. If he has not given a fresh personal take, leave an obvious draft section for his review or write neutral analysis labeled as analysis.
- Focus on **evidence, what mattered, and what comes next** rather than long game recaps.
- Add humor only when it fits actual events. An example of a past humorous callout was comparing Kenneth Walker's run to the tunnel after a game with his rushing distance. Treat such items as editorial jokes, not verified numerical statistics unless sourced.

### Accuracy and sourcing

- Verify the **season, official NFL week, kickoff date/time and timezone, opponent, location, completed games, Seattle's record, injuries, active roster, score, and opponent's record** each week. Never derive NFL week from the number of Seahawks games played. Bye weeks are easy to miscount.
- Research current facts, not last week's lineup. Verify questionable starters, offensive line combinations, and player statuses. Do not confuse players on the Seahawks with players on the opponent.
- For game information and stats, favor NFL/Seahawks official gamebooks and box scores, official team communications, ESPN play-by-play, and established stat providers. Reconcile conflicting numbers before publication.
- For reporting and context, follow credible Seahawks writers and analysts, including Bob Condotta, Greg Bell, and Bryan Nemhauser. Seahawks Pressers is an additional press conference source: https://www.youtube.com/@seahawkspressers.
- Attribute factual claims, quotes, advanced metrics, and news appropriately. Provide source links where the site's current design supports them. Do not invent press conference quotes or misrepresent paywalled reporting.
- Distinguish official figures from projections and models. Do not call a projection a verified result.
- Use absolute dates on pages and changelogs. Check publication timing before using words such as “today” or “this week.”
- If a detail cannot be verified, omit it, qualify it, or flag it for Jesse. Never fill gaps with plausible-sounding facts.

## 4. Weekly Preview Workflow

Trigger examples: “Let's do the Hawks preview,” “Update Hawks War Room for Seahawks vs. [opponent],” “Prep this week's game.”

### A. Establish game identity

1. Look up the official Seahawks schedule.
2. Confirm season, NFL week, opponent, home/away, stadium, local kickoff time, TV if relevant, and both teams' entering records.
3. Pull current division standings and point differential if the site uses them.
4. Find the next archived game ID/slug using the existing scheme. Do not overwrite last week's page.

### B. Research the matchup

Cover the items that will affect the game rather than adding stats to fill space:

- Seattle's recent form: last game, offensive and defensive execution, points for/against, and meaningful trend lines.
- Opponent identity: how they score, how they defend, who drives their offense, who creates pressure, and weaknesses Seattle should test.
- Line of scrimmage: Seattle offensive line combinations, opposing edge rushers, Seattle defensive front, run blocking, protection, and obvious matchup risks.
- Quarterback and passing game: Sam Darnold and current receivers where applicable to the season, coverage looks, explosive-play opportunities, turnovers, and pressure response.
- Rushing game and red zone: efficiency, short yardage, finishing drives, and personnel deployment.
- Coaching and game management: Mike Macdonald and the relevant offensive/defensive coordinators after verifying their current roles.
- Special teams and situational football when material: penalties, third downs, turnovers, field position, fourth-down choices.
- Injury/availability news **only when current and substantiated**. Do not build a speculative injury board.

Research must be fresh for the actual matchup. Do not copy previous week's analysis and replace the opponent's name.

### C. Write “10 Things to Watch”

This is the centerpiece of every preview and the backbone of the postgame review.

Produce **exactly 10 numbered, distinct, testable items**. Each item needs:

1. A punchy title.
2. A short explanation of **why it matters**.
3. A concrete **what to watch** signal, matchup, or performance threshold.
4. Where appropriate, a **call** about what Jesse expects. Keep the call specific enough to check after the game.

Spread the 10 across offense, defense, coaching, line play, situational football, and the opponent's specific threats. Do not use 10 variations on “execute better.” Avoid precise numerical thresholds unless supported by a meaningful reason.

Past examples of topics, **not standing facts**: restored guard combinations, handling Josh Sweat, no free runners on the opening drive, run game progress, red-zone touchdowns, and sustaining offensive improvement. Verify the people and matchups anew every week.

Persist all 10 items with stable IDs/order so the postgame page uses the **original** claims and wording. Never silently revise the preview's calls after kickoff.

### D. Scouting, personal note, and predictions

- Present a concise “How Seattle Wins / What Could Go Wrong” scouting view.
- Include **Jesse's War Room Note** or “Latest from Jesse” when Jesse provides a personal take. Keep it in first person if his original wording uses first person.
- Show the site's existing **model prediction** only if the model ran and returned a real result. Record the run inputs/date if the implementation supports it. Never fabricate a model score.
- Include contributor score predictions when supplied. Historical contributors include Matt M., Steve M., Kendall P., Barry P., KC A., Josh F., and Jeff C., with others possible. **Use the active roster from the repository or the current submissions, not this historical list as definitive membership.**
- When Jesse sends screenshots of predictions, transcribe every name and score carefully, preserve Seattle/opponent orientation, and verify ambiguous text before publishing. Do not infer missing picks.
- Compute **Group Pick** from the valid submitted predictions using the repository's existing formula. If no formula exists, use the arithmetic mean of each team's predicted points, document the rounding policy, and exclude absent picks rather than treating them as zeros.

### E. Publish the preview experience

Update the existing site structure, respecting its implementation:

- Set the homepage's **current game** card and preview link.
- Use the supplied preview hero art, or existing approved art if none is supplied.
- Publish the full preview and 10 Things to Watch in the current game's entry.
- Keep “Call the Plays” visible **beneath the current week's main post/card**, per the prior design decision. Reuse the existing game and its artwork. Do not replace it with an unfinished share/export widget.
- Preserve season archives, prior game pages, historical predictions, rankings, point differential leaderboards, and other established features.
- Update the top information bar with verified useful context such as record, standing, or rankings where the existing UI supports it. Don't invent rankings.
- Keep share links and mobile presentation usable. Do not restore the previously removed standalone “export 10 Things” feature without an explicit request.

## 5. Postgame Workflow

Trigger examples: “Time for postgame,” “The Seahawks game is over, update the site,” “Grade our 10 Things,” “Let's do our postgame push.”

### A. Lock in actual game results

1. Confirm the game is final with an authoritative box score.
2. Record Seattle and opponent's exact final scores, winner, final records, game date, NFL week, venue, and any overtime.
3. Verify stats and game context that inform the analysis, including turnovers, sacks, offensive yards, rushing, efficiency, red-zone results, penalties, big plays, and other relevant categories.
4. Reconstruct the actual game story from trustworthy reporting and play-by-play. Focus on the outcome and the deciding moments, not an exhaustive drive log.
5. Compare current performance with earlier games or the previous season **only if the same metrics and time ranges are verified**.

### B. Lead with the result and Jesse's assessment

- Change the homepage current game card from **Preview** to **Final / Postgame** without losing access to the original preview.
- Write a concise, specific headline and recap lead.
- If Jesse provides dictation, incorporate it prominently in “Jesse's Take” / “War Room Note.” Preserve his tone. One past sentiment was that a win is welcome while the team still needs stronger execution, improved rushing, red-zone TDs, and sustainable growth. **Do not reuse it as if it were this week's fresh comment.**
- Give credit where it is due. Be direct about breakdowns. Tie conclusions to concrete moments or numbers.

### C. Grade the original “10 Things to Watch”

This is essential, not optional.

For **every one of the 10 original preview items**, show:

- **Our call:** The original pregame prediction or watch item, unchanged in substance.
- **Here's the reality:** What specifically happened, supported by a verified fact, stat, sequence, or credible reporting.
- **Verdict:** Choose from `We called it`, `Partly right`, `Missed it`, or `Not enough evidence`.
- **Why:** One or two sentences connecting the prediction to the evidence.

Recommended concise presentation:

```text
#3. NO FREE RUNNERS EARLY
Our call: Watch Seattle's opening-drive protection and avoid unblocked pressure.
Here's the reality: [Verified game evidence].
Verdict: [We called it / Partly right / Missed it / Not enough evidence].
```

Never award a hit based on vibes. A **watch item** that was not a directional prediction should be graded on whether the expected matchup/theme proved relevant, with its limits explained. Don't move the goalposts or change the old preview. If the record is unclear, choose `Not enough evidence`.

Optionally calculate an overall grade from the individual verdicts **only if the site has an existing methodology**. Otherwise display an honest qualitative summary rather than an invented “8/10” score.

### D. Grade the predictions

When predictions exist:

- Show each contributor's original predicted score alongside the verified final score.
- Report the picked winner correctly. A correct winner is different from a close exact score.
- If using a distance-to-final score, calculate `abs(predicted Seattle - actual Seattle) + abs(predicted opponent - actual opponent)`; lower is closer. Label the metric and show ties honestly. Follow the repo's existing grading rule if different.
- Evaluate the Group Pick and model pick if they exist, distinguishing them from contributor picks.
- Do not backfill absent picks or associate a score with the wrong contributor. Prior screenshot submissions are source material, not a license to guess.
- Update the site's historical prediction performance or leaderboard only if the existing data model supports it.

### E. What the game teaches us

Add a short section on:

- **What worked** and what improved.
- **What failed** and whether it was a one-off or an ongoing concern.
- **What carries forward** into next week, including 2 to 4 specific things to monitor.

If the site has a point differential/season trend view, update it using verified final results. Do not conflate this game with another week's outcome.

### F. Postgame content and artwork

- Attach the **postgame hero image** provided by Jesse. Sometimes the homepage hero image and full recap hero differ. Keep them distinct.
- Update the same season game archive entry with postgame material, rather than creating an unrelated duplicate page.
- Preserve the original scouting, 10 Things to Watch, and submitted predictions as historical context.
- Link to useful postgame reporting or pressers if the links are relevant and verified.
- Keep the homepage fresh: final score, outcome, postgame headline, teaser, and correct postgame link.

## 6. Image and Asset Handling

Jesse frequently supplies a custom PNG hero image and sometimes separate images for the homepage and postgame page.

Follow these rules:

1. Locate the supplied attachment/file in the working environment. Do not assume it is present based on a filename alone.
2. Inspect the project's established asset path. `/Seahawks/assets` has been used as a reference in prior requests, but verify it before writing.
3. Preserve the **exact uploaded filename, capitalization, and `.png` extension** when Jesse gives one, unless he explicitly requests a rename. A historical example format is `BD0A2924-76E0-4ECA-A169-94DFC150DC91.png`; that sample is not an instruction to reuse the image.
4. If the project requires copying/uploading into GitHub, perform the real upload and point the page to the existing asset using the correct path. Do not pretend a file exists or use a broken placeholder.
5. Keep preview, homepage postgame, and full recap image assignments straight. Avoid accidentally placing the homepage image into the recap slot or vice versa.
6. Verify that images load after build/deployment, fit mobile and desktop, and have useful alt text.
7. Do not modify player faces, team logos, or image composition unless Jesse explicitly requests visual edits.

## 7. Site Features to Preserve

These are established or previously discussed site features. Verify implementation before editing:

- Current-week scouting and postgame content on the homepage.
- Season stack/archive with a stable page for each week.
- “10 Things to Watch” and its postgame accountability scorecard.
- Score prediction contributions and Group Pick.
- Model predictions, when the model is implemented and has a real output.
- Team record, relevant rankings, and point differential display/leaderboard.
- “Latest from Jesse” / War Room personal commentary.
- “Call the Plays” mini-game, including its existing Mike Macdonald and Brian Fleury choices and associated art, positioned under the current post.
- Existing roster and scouting features, where implemented.
- Shareable pages and clean mobile presentation.

**Separate roadmap items, not automatic weekly tasks:** all-time 53-man Seahawks roster builder, 17-man practice squad, season simulation, physical-device prototype, enhanced roster/contracts database, presser analysis automation, and new social export features. Do not build these during a regular weekly update unless Jesse explicitly asks.

## 8. Technical Implementation Principles

- Make the smallest consistent changes needed to publish the requested game content. Prefer the site's existing data schema, components, styles, API adapters, and routes.
- If game content is currently hardcoded, follow the current pattern for the update and suggest a future structured content migration separately. Do not take a weekly editorial request as permission for a sitewide rewrite.
- Separate static editorial text, verified stat data, contributor picks, calculated predictions, and hero asset paths in the implementation when practical.
- Treat pregame and postgame as distinct states of one game (`upcoming`, `preview`, `final` or the existing equivalents). Updates must be idempotent: rerunning an update must not duplicate game cards or predictions.
- Keep older pages stable and linkable. Never delete the original preview as part of the postgame rollout.
- Use current status to determine the right lead on the homepage, but maintain both preview and recap access in the archive.
- Make no unrelated design or feature changes during weekly publication without a clear reason.
- Make new code accessible and responsive, and honor the site's existing visual design system.
- Do not commit secrets, API keys, scraped paywalled text, or large unoptimized duplicate images.
- Don't deploy automatically merely because code is complete. If Jesse explicitly requests a live update/push, follow the repository's authorized deployment flow and verify the result. If he asks to preview or mock up only, keep changes nonproduction and show the local/preview result.

## 9. Quality Control Before Declaring a Game Done

### Accuracy

- [ ] Correct official season, NFL week, opponent, venue, and kickoff/final date.
- [ ] Correct Seattle and opponent records; bye week handled correctly.
- [ ] Actual stats, names, depth-chart roles, scores, and quotes verified and attributed.
- [ ] Jesse's words attributed only when actually supplied.
- [ ] No invented contributor pick, model run, injury, result, or source.
- [ ] No mix-up between the Seahawks' players and opposing players.

### Content

- [ ] Preview has exactly 10 distinct testable Things to Watch.
- [ ] Postgame grades **all 10** original items against the game, with honest verdicts.
- [ ] Predictions match the original screenshots/submissions and final score.
- [ ] Group Pick computed by an established, documented method.
- [ ] Both the original preview and postgame remain accessible.
- [ ] Next-week implications are specific and grounded.

### Site

- [ ] Correct hero PNG present at the actual asset path and displayed in the correct slots.
- [ ] Homepage current card, score/status, headline, and game links updated.
- [ ] Archive and other games unchanged.
- [ ] “Call the Plays” remains accessible under the current card.
- [ ] Mobile/desktop layout, images, and links checked.
- [ ] Existing tests, lint, typecheck, and production build passed where available.
- [ ] No unintended files, secrets, or unrelated changes included.
- [ ] If published, deployed URL checked. Do not describe a deployment as complete until verified.

## 10. What to Send Jesse When Finished

Keep the status report short and precise:

1. **Updated:** Which matchup and NFL week, and whether this was preview, postgame, or both.
2. **Added:** Major changes: 10 Things, graded scorecard, Jesse's note, predictions, hero images, game stats, standings, etc.
3. **Checked:** Tests/build and factual verification performed.
4. **Links:** Local preview, Vercel preview, production page, and/or relevant GitHub PR/commit as applicable. Label each correctly.
5. **Need from Jesse:** Only genuine missing information, such as a hero file that was not supplied or ambiguous prediction screenshot. If missing, finish everything else first.

Never say “live,” “deployed,” or “uploaded” unless the corresponding action succeeded and was checked.

## 11. Ready-to-Use Workflow Requests

### Preview command

```text
Prepare this week's Hawks War Room preview for Seattle vs. [opponent].
Check the official NFL week and game details. Research the current matchup.
Write and publish the scouting breakdown and exactly 10 testable Things to Watch.
Preserve the site's existing design, model and contributor prediction systems,
current card, Call the Plays placement, and archive. Use the hero image I supply.
Run checks. Give me a preview before production unless I explicitly ask you to push live.
```

### Postgame command

```text
Do the Hawks War Room postgame update for Seattle vs. [opponent].
Verify the official final score, stats, and record. Keep the original preview intact.
Grade all 10 of our original Things to Watch using “Our call / Here's the reality /
Verdict,” and grade the contributors' original score predictions and Group Pick.
Use my notes as my personal take, add evidence-based lessons and next-week
watch items, update the homepage and same archived game, and use my supplied PNGs.
Run checks. Publish only when I ask for a live push, then verify the deployed page.
```

### Research-only command

```text
Research the next Seahawks opponent and give me an evidence-backed scouting memo
and a proposed 10 Things to Watch. Do not edit the repo or deploy anything yet.
```

### If Jesse says only “update Hawks War Room”

Check the Seahawks' schedule and game status first. If the next game has not started, use the preview workflow. If a game has finished and awaits an update, use the postgame workflow. If unclear, inspect the most recent site entry and explain the assumption in the final status. Do not invent a game or silently skip a week.

---

## Final Operating Rule

**The value of Hawks War Room is accountability.** Make a clear call before kickoff, preserve it, then show what happened. Every weekly update should improve the reader's understanding of the Seahawks while keeping Jesse's authentic voice and the site's existing structure intact.

# UI round, Step 1: audit, colour directions and landing concept

Date: 2026-10-15. Branch `feat/ui-design` (from `main` at `7884e1f`, the Phase 8 merge). No app
code was changed in this step. Everything here is input for the team's choice.

## Step 0

| Check                        | Command                                                                | Result                                                                                         |
| ---------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Phase 8 on main, tree clean  | `git checkout main && git pull --ff-only`, `git log`                   | `7884e1f Merge pull request #13`, clean; branch `feat/ui-design` created                       |
| GitHub Actions, merge commit | `GET /repos/.../actions/runs?head_sha=7884e1f` (`gh` is not logged in) | CI, push, **completed / success** (run 38630389430)                                            |
| ruff, black                  | `ruff check .`, `black --check .`                                      | All checks passed; 148 files unchanged                                                         |
| pytest                       | `python -m pytest -q`                                                  | **673 passed**, 4 warnings, 7 min 29 s                                                         |
| ESLint, Prettier             | `npm run lint`, `npx prettier --check .`                               | clean                                                                                          |
| i18n                         | `npm test -w @investiq/i18n`, `npm run check -w @investiq/i18n`        | 3/3; parity passed, 481 keys (2 expected warnings: Roman Urdu strings identical in both files) |
| Type-checks                  | web `tsc -b`, mobile `tsc --noEmit`, 4 shared packages                 | all clean                                                                                      |
| Unit tests                   | web `npm test`, api-client                                             | 48/48, 6/6                                                                                     |
| Web build                    | `npm run build`                                                        | built; **one 1,099.90 KB chunk (329.92 KB gzip)**, Vite's size warning                         |
| Playwright E2E               | `npm run e2e`                                                          | **5 passed** (2.0 min); test DB cleaned (5 accounts, 6 MOCK stocks)                            |

## A. Audit

84 screenshots in `audit/` (`<screen>_<en|ur>_<desktop|m390>.jpg`): login, register, onboarding,
dashboard, stocks, stock detail (HBL), portfolio, portfolio with one holding expanded, backtest,
backtest report, chat, the empty dashboard/portfolio/backtest/chat, loading (stock detail,
portfolio, backtest report: API delayed 15 s) and error (stock detail, portfolio, chat: API 500).
Desktop is 1440 px wide, full height; `m390` is 390 px. Real dev-DB data from a temporary
Moderate account (Rs 100,000 portfolio, 3-year backtest, one English and one Urdu chat message),
deleted afterwards. `rtl-truncation_ur_1024.jpg` shows the RTL bug at 1024 px.

Ranked by first-impression damage:

1. **No public face.** `/` redirects to `/dashboard`, then `/login`: the first screen anyone sees is
   a lone card on grey with "Welcome back" (`login_en_desktop`). Nothing says what InvestIQ is.
2. **Default-template look everywhere.** All colour is Tailwind's stock blue-600 and greys; the web
   app does not import `@investiq/design-tokens` at all (only `apps/mobile/App.tsx` does). The
   tokens package also disagrees with Design.md: spacing `xs` 4 px (not on the 8 px scale), type
   `xl` 1.25 rem (Design: 1.5 rem), motion `slow` 500 ms (Design caps at 400 ms), shadows differ
   from §21, colours are placeholders.
3. **Thin dashboard.** Two cards and a disclaimer, then empty space (`dashboard_en_desktop`). The
   portfolio card is one sentence; no figures, no forecasts, no way into the day's information.
4. **Stock list is a wall.** 95 identical cards with ticker, name and sector, no price or change,
   no sector grouping: 5,316 px tall on desktop, over 9,000 px at 390 px (`stocks_*`).
5. **RTL truncation (Memory §4).** In Urdu at 820 and 1024 px, long English names and sectors are
   cut from the left: "…ies (Pakistan) Limited", "…ology & Communication"
   (`rtl-truncation_ur_1024.jpg`). Fits at 1440 px and wraps at 390 px.
6. **Charts are library defaults.** The stock forecast is a tiny purple mark at the far right edge,
   easy to miss (Design §18 asks for a visibly distinct forecast with a band); legend text takes
   the series colours; Y-axis ticks read "600K" with no Rs.; three backtest lines of equal weight.
7. **Portfolio screen is long and flat.** 5,254 px on desktop; every holding card shows every block
   at once; no allocation visual; "Why this stock" is collapsed and last; most text is 12 px.
8. **Missing ▲/▼ on headline figures.** Backtest total return "+254.94%" is plain black with no
   arrow (Design §6.3); the benchmark's +381.49% sits in small text under it.
9. **Chat rendering bugs.** (a) English replies show "low_confidence", "transaction_cost": the
   U+2011 non-breaking hyphen falls into the Noto Naskh `@font-face`, whose `unicode-range`
   includes U+2010-2011, and Naskh draws it low (`chat_ur_desktop`). (b) In Urdu the counter
   reads "1000 / 0" (bidi). (c) Two language toggles on one screen in Urdu (header and chat).
   Content, for the wording task: one English reply named OGDC twice.
10. **Onboarding answers are small radio rows** in a 240 px column, not the large choice cards of
    Design §13; most of the screen is empty (`onboarding_en_desktop`).
11. **Low-contrast text.** `text-gray-400` (#9CA3AF) is used for 16 text elements: 2.54:1 on white,
    below AA.
12. **Inconsistent shapes and colours.** Buttons `rounded-md`, cards `rounded-xl`, badges
    `rounded-full`; risk badges use emerald/sky/orange outside any palette; the admin tag is purple.
13. **Off-scale spacing.** `mt-1` x32, `px-3` x21, `gap-1` x17, `py-3` x12, `space-y-3` x9, plus
    `py-0.5`, `py-2.5`, `mb-5` (Design §4: multiples of 8 px).
14. **States.** Skeletons are flat grey blocks that do not match the content; errors appear only
    after about 7 s (React Query retries three times) with the skeleton shown meanwhile
    (`error-chat_ur_desktop` was taken at 2.5 s and still shows it).
15. **390 px navigation** is a scrolling row of text tabs with no icons; logout is an unlabeled icon.
16. **Bundle.** One 330 KB gzip chunk for every route, including login.

Fine as is: Urdu Nastaleeq line heights (no clipping seen), figures stay LTR inside Urdu, the
low-confidence amber treatment on the forecast card, the disclaimer band.

## B. Three colour directions

Full token sets (light and dark, every Design §2 token plus tints, `surface-sunken`,
`border-strong`, `focus-ring`, four chart series and three gradient stops): `directions.json`.
Every contrast pair the components draw, computed: `contrast.md` (**156 pairs, 0 failures**;
text >= 4.5:1, input borders, focus rings and chart lines >= 3:1). Both are generated by
`tools/directions.py`.

**Gains and losses (all three directions).** A red/green pair passes contrast but almost merges
for colour-blind users (deuteranopia ΔE 8-18 in my first sets). A search over AA-passing pairs
gave a darker green against a brighter vermilion, separated by lightness as well as hue:

|       | Gain      | Loss      | ΔE normal | protanopia | deuteranopia | tritanopia |
| ----- | --------- | --------- | --------: | ---------: | -----------: | ---------: |
| Light | `#0D6644` | `#CC3A10` |      99.0 |       28.0 |         49.4 |      109.7 |
| Dark  | `#86E6BA` | `#EE6236` |     101.0 |       42.7 |         49.3 |      117.3 |

Always with ▲ / ▼ / —. Sentiment uses the same three colours with its own mood icons (Design §17).

|                                              | Truck Art                                                                                                    | Indus Night                                                                                      | Ink & Lime                                                                                       |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| Idea                                         | Magenta and marigold from Pakistani truck art on warm paper: loud on the landing page, quiet on data screens | A deep river-teal night with a cyan current and a coral spark: dark by default, calm and focused | Near-black ink on clean paper with one electric lime accent: editorial, almost no colour on data |
| Primary mode                                 | light (dark fallback)                                                                                        | **dark** (light fallback)                                                                        | light (dark fallback)                                                                            |
| Primary                                      | `#B0105C` / dark `#FF6BAA`                                                                                   | `#33C9DB` / light `#0A6E80`                                                                      | `#141413` / dark `#C8F03C`                                                                       |
| Secondary                                    | marigold `#F2A900`                                                                                           | coral `#FF8466`                                                                                  | lime `#C8F03C`                                                                                   |
| Background / surface                         | `#FAF7F2` / `#FFFFFF`                                                                                        | `#07131A` / `#0E1F27`                                                                            | `#F5F5F1` / `#FFFFFF`                                                                            |
| Text / secondary                             | `#1E1A17` / `#5C5650`                                                                                        | `#E8F3F4` / `#9DB6BC`                                                                            | `#141413` / `#5A5A55`                                                                            |
| Warning                                      | `#8A5300` on `#FFF3D6`                                                                                       | `#F5BC4A` on `#34290F`                                                                           | `#875600` on `#FFF2D6`                                                                           |
| Chart: portfolio, rules, benchmark, forecast | magenta, teal, warm grey, burnt orange                                                                       | cyan, amber, grey-teal, coral                                                                    | ink, teal, grey, olive                                                                           |
| Bloom gradient                               | `#FF3D8B` → `#FFC233` → `#25C6D2`                                                                            | `#33C9DB` → `#7BE0C3` → `#FF8466`                                                                | `#C8F03C` → `#4FE0A6` → `#E8F7FF`                                                                |
| Risk                                         | magenta reads as "sale" to some; must stay off figures                                                       | dark data screens need care with dense tables                                                    | lime is fashionable; less tied to Pakistan                                                       |

Rules shared by all: the secondary colour never carries text or figures; primary never colours a
number, so it cannot be mistaken for a gain or a loss; the low-confidence card keeps the warning
tint (Design §6.4). Blue-indigo is avoided in all three.

**Typography.** Unchanged per Design §3 (Inter or system UI; Urdu Nastaleeq). Proposed for the
landing page's Latin headings only: **Bricolage Grotesque**, SIL Open Font License 1.1,
self-hosted from `@fontsource-variable/bricolage-grotesque` 5.3.0, one 41 KB Latin woff2
(variable weight). Urdu headings on the landing page stay Nastaleeq.

## C. Landing page concept (`/` for logged-out users)

Route rule: `/` shows the landing page when logged out; a logged-in user goes to `/dashboard`
(onboarding first if the profile is incomplete, as `guestRedirect` already decides). Every
other unknown path keeps its current redirect.

1. **Hero: market bloom.** Rays radiate from one glowing point; each ray is one of the **95**
   included companies of `kse100_snapshot_2026-10-10.csv` (tickers and sectors only, no prices),
   its angle set by its sector (35 sectors, each a slice of the fan) and its length by a hash of
   the ticker, so nothing implies a price or a prediction. Sparks travel outward along the rays;
   the bloom breathes (±3.5% over 9 s) and tilts gently toward the pointer. Hover or tap a node:
   it brightens, the rest dim, and a label shows "HBL · Commercial Banks". Keyboard and screen
   readers: a "Browse the 95 companies" disclosure lists every ticker as a button; focusing one
   lights its node. Colours: the direction's dark gradient stops, by sector. The bloom sits beside
   the copy on desktop (mirrored in Urdu) and under it at 390 px, behind a scrim so text stays AA.
   Copy (concept, for team review):
   - EN: "Invest in PSX with your eyes open." / "Your risk profile, an AI forecast that says how
     unsure it is, and a portfolio with every rupee of charges and tax shown. In English or Urdu."
   - UR: "پی ایس ایکس میں سرمایہ کاری، کھلی آنکھوں سے" / "آپ کا رسک پروفائل، ایسی AI پیش گوئی جو اپنی
     غیر یقینی بھی بتاتی ہے، اور ایسا پورٹ فولیو جس میں ہر روپے کے اخراجات اور ٹیکس دکھائے گئے ہیں۔ اردو یا انگریزی میں۔"
   - "Get started" (primary), "Log in" (secondary), the en/ur toggle in the hero's top bar, and a
     source line: "Each ray is one of the 95 KSE-100 companies in our snapshot of 10 Oct 2026,
     grouped by its 35 sectors. Tickers only, no prices."
2. **Scroll zoom.** A 320 vh section with a pinned stage: the headline "Every rupee, accounted for."
   fills the screen, fades as a real screenshot of the portfolio screen rises full-bleed, then the
   screenshot shrinks into a laptop frame (a phone frame with the 390 px screenshot on phones)
   and the headline returns smaller above it. Caption: "Figures from a test account built on
   <date>; an example, not advice." The final build uses screenshots retaken in the chosen
   direction.
3. **Risk demo.** A three-stop slider (Conservative / Moderate / Aggressive) morphs a donut and a
   holding count, labelled "Example". It shows only the published rules (Memory §3, Phase 5):
   Conservative 7-10 holdings, 15% per company, 30% per sector, weights 1/σ²; Moderate 5-8, 20% /
   35%, 1/σ; Aggressive 4-6, 25% / 40%, equal weights. No returns, no tickers unless you choose
   option (b) in the questions below.
4. **What it really costs.** Rs 100,000 flows into bars: shares Rs 99,706.41; commission 149.55;
   sales tax on commission 22.43; CDC 3.59; PSX trading fee 3.48; SECP levy 0.66; NCCPL 0.80 +
   0.29 (total charges Rs 180.80); cash left Rs 112.79. Labelled "Worked example: Moderate, filer,
   prices of the 7 Oct 2026 close, rates `psx-costs-2026-10-11.2`; CDC and NCCPL rates not yet
   confirmed" (DetailedReport Phase 5; the column sums were re-added and match 180.80).
5. **How it works**, four steps with small looping line illustrations (paused under reduced
   motion): risk profile (7 questions); AI forecast and news sentiment (next trading day, with its
   confidence); costed portfolio (every charge and tax); backtest and bilingual chat.
6. **Honesty strip and footer.** "Forecasts are probabilistic and are flagged low-confidence when
   the model does no better than a simple baseline. Advisory only, not a licensed financial
   advisor. InvestIQ never places trades: execute only through a licensed PSX broker." Numbers
   used anywhere on the page, each with its source: 95 companies (snapshot 10 Oct 2026), 18 with
   forecasts (model `lstm-rf-20261009T233529Z`), 5 years of daily prices (7 Oct 2021 to 8 Oct 2026,
   122,099 stored closes, dev DB). No statistics, testimonials or logos beyond these.

**Performance and accessibility.**

- Route-level code splitting (`React.lazy` per route): `/` loads React, i18n and the landing chunk
  only; the app's 330 KB gzip chunk is no longer on the landing path.
- three.js loads in its own chunk after first paint (idle callback), so the LCP element is the
  headline, not the canvas. The canvas fades in.
- Static fallback image of the bloom (the hero still, about 60 KB WebP) for
  `prefers-reduced-motion`, WebGL failure, `navigator.hardwareConcurrency <= 4` or Save-Data.
  Under reduced motion the zoom section shows its final frame and the risk demo switches instantly.
- Rendering pauses when the hero is off screen or the tab is hidden; pixel ratio capped at 2.
- Target LCP < 2.5 s on a mid-range laptop, measured with Lighthouse (desktop preset) and with
  Playwright on 4x CPU throttling for mobile; reported with the build.
- Added size, measured with esbuild (minified, gzip -9) on the packages' current versions:
  three.js used directly **about 135 KB gzip**; three.js with react-three-fiber **about 250 KB
  gzip** (r3f imports the whole three namespace, so three cannot be tree-shaken). Both in the lazy
  landing chunk only. Display font 41 KB, landing only. Scroll effects: no library.

## D. In-app interaction style (logged-in screens)

Calm, per Design §11: cards lift 2 px with a slightly deeper shadow on hover (150 ms ease-out,
clickable cards only); charts draw in once on first load (Recharts' own animation, off on
refetch); figures count up on first appearance, capped at 400 ms; page transitions are a 200 ms
fade through the View Transitions API (react-router 7's `viewTransition`; browsers without it
switch instantly); skeletons shaped like the content they replace, with a soft shimmer that stops
under reduced motion. No 3D and no decorative motion on data screens.

## E. Previews

App screens are the running app with the direction's colour variables and chart colours
injected (`<direction>/preview.css`, generated by `tools/preview_css.py`), on real dev-DB data.
They show colour and surface treatment only: the layout problems of the audit are not fixed in
them yet.

| Direction      | Files (`<direction>/screens/`)                                                                                                                                                                                                            |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `truck-art/`   | `landing-hero_{en,ur}_{desktop,m390}.jpg`, `dashboard_*`, `portfolio-expanded_*`, `chat_*` (16)                                                                                                                                           |
| `indus-night/` | the same 16, plus `landing-zoom-{10,45,95}_{en,ur}_{desktop,m390}.jpg` (12) and `landing-prototype-indus-night.webm` (39 s, 960 px, 3.2 MB: pointer sweep with node labels, keyboard focus through the list, the zoom section, then Urdu) |
| `ink-lime/`    | the same 16 as Truck Art                                                                                                                                                                                                                  |

Prototype source: `prototype/landing.html` (three.js 0.169.0 from jsDelivr, prototype only),
`prototype/kse100-tickers.json`, `prototype/assets/` (portfolio screenshots per direction). To view:
`python -m http.server 8765` in this folder, then
`http://127.0.0.1:8765/prototype/landing.html?d=indus-night&lang=ur` (`&motion=reduce` for the
static version).

## F. Recommendation

**Indus Night**, dark as the primary theme, with its light set following the OS setting.

- The bloom only glows on a dark field; one dark identity runs from the landing page into the
  app instead of switching from a dark hero to a pale dashboard.
- Its cyan primary is far from both the gain green and the loss vermilion in every simulated
  colour-vision type, so a button never reads as a figure.
- The data screens stay calm: low-saturation teal surfaces, one accent, coral kept to the landing
  page. All 52 of its contrast pairs pass AA, and Urdu Nastaleeq stays readable on it
  (`indus-night/screens/chat_ur_desktop.jpg`).
- Runner-up: Truck Art is the most memorable and the most Pakistani, but magenta beside dense
  tables of figures is harder to keep calm.

**New dependencies (need your approval; Architecture.md §3 to be updated):**

| Package                                    | Version (published)                                         | Licence | Added size                         | Where                   |
| ------------------------------------------ | ----------------------------------------------------------- | ------- | ---------------------------------- | ----------------------- |
| `three`                                    | 0.186.1 (2026-09-24)                                        | MIT     | about 135 KB gzip                  | lazy landing chunk only |
| `@react-three/fiber` (optional)            | 9.8.1 (2026-09-24); peer React >= 19 < 19.4, we have 19.3.0 | MIT     | about +115 KB gzip on top of three | lazy landing chunk only |
| `@fontsource-variable/bricolage-grotesque` | 5.3.0 (2026-07-19)                                          | OFL-1.1 | 41 KB woff2                        | landing only            |

My advice: skip react-three-fiber. One React component that owns a plain three.js scene in an
effect is about 100 lines, halves the added size and is one dependency fewer. Your brief named
r3f, so this is your call.

**What the plan changes in Design.md (to record as deviations):**

- §2: filled with the chosen tokens, light and dark, dark primary; new tokens (tints,
  `surface-sunken`, `border-strong`, `focus-ring`, chart series, gradient stops). §21 gets the
  dark elevation set it asks for. §25's first bullet (no final palette) is retired.
- §3: a Latin display font on the landing page only; the landing headline goes above `--text-3xl`
  (up to 72 px; Urdu up to 56 px).
- §11: the landing page uses continuous, decorative motion (bloom, scroll zoom) that the in-app
  rules forbid. Proposed scope: public landing page only, all of it off under reduced motion; the
  in-app rules stay as written.
- §6.3: gains and losses use the colour-blind-tuned green and vermilion above instead of a
  generic red.
- `packages/design-tokens` is brought in line with §3, §4, §11 and §21 (4 px spacing, 1.25 rem
  `xl`, 500 ms motion and the shadow values are mismatches today) and the web app consumes it.

**Decisions needed from you:**

1. The direction, and dark-first or light-first for the app screens.
2. react-three-fiber or plain three.js.
3. A theme toggle next to the language toggle (Rules §4.3 already names theme as global state),
   or OS setting only. A toggle is new UI, so I am asking rather than adding it.
4. Risk demo data: (a) only the rules (counts, caps, weighting) with an abstract donut, or (b) the
   engine's real output for Rs 100,000 per profile, dated and labelled "Example".
5. Showing the snapshot's tickers publicly: Memory §4 has the open PSX terms-of-use question on
   that snapshot. Fine for a local demo; a public deployment needs the team's decision first.
6. Approve the display font and review the hero copy in both languages.

# Design.md — InvestIQ

### UI/UX Design System

**Companion docs:** PRD.md, Architecture.md, Rules.md, Phases.md
**Status:** Complete. The colour palette (§2) was chosen on 2026-10-15 (UI round: direction "Indus Night", dark-first with a full light theme); the source of truth is `packages/design-tokens`. Deviations from this document made in that round are marked **Deviation (UI round, 2026-10-15)**.

---

## 1. Design Principles

1. **Clarity over cleverness.** The entire product exists to make PSX investing less intimidating. Every screen should feel calmer and simpler than a typical trading app, not more advanced.
2. **Numbers are never naked.** Every price, return, or fee figure is labeled clearly (gross vs net, currency, time period) — a novice user should never have to guess what a number means.
3. **Uncertainty is visible, not hidden.** Confidence scores, low-confidence flags, and disclaimers are a designed part of the UI, not fine print apologetically tucked away.
4. **Bilingual is a first-class citizen, not an afterthought.** Urdu text (RTL-aware where needed) must get the same layout care as English — no cramped or truncated Urdu labels.
5. **Trust is built visually, not just through copy.** Consistent, professional visual language (spacing, alignment, restrained color use) signals "this is a serious financial tool," which matters for a product asking users to trust it with investment decisions.

## 2. Color Palette — Indus Night (chosen 2026-10-15)

A deep river-teal night with a cyan accent: bold on the landing page, calm on data screens. **Dark is the default theme; light is a full alternative**, chosen with the theme toggle (§14.1) and remembered per device. The values live in `packages/design-tokens/src/colors.ts` (single source; the web app reads them as `--iq-*` CSS variables and Tailwind's stock palette is switched off). The options considered and the full contrast tables: `docs/design-directions/`.

| Token (Design §2 name)         | Dark (default)                                                                | Light                                      | Use                                                          |
| ------------------------------ | ----------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------ |
| `--color-primary`              | `#33C9DB`                                                                     | `#0A6E80`                                  | buttons, active states, links                                |
| `--color-primary-dark` (hover) | `#5FD6E4`                                                                     | `#08596A`                                  | hover/pressed state of primary                               |
| primary tint (new)             | `#0F3640`                                                                     | `#E0F3F6`                                  | active navigation item, primary badges                       |
| `--color-secondary`            | `#FF8466`                                                                     | `#E8603F`                                  | brand accent on the landing page only; never text or figures |
| `--color-success`              | `#86E6BA`                                                                     | `#0B5E3F`                                  | gains (with ▲), positive sentiment                           |
| `--color-danger`               | `#EE6236`                                                                     | `#BF360C`                                  | losses (with ▼), negative sentiment, destructive actions     |
| `--color-warning`              | `#F5BC4A`                                                                     | `#875700`                                  | low-confidence flags, estimates, alerts                      |
| `--color-neutral`              | `#9DB6BC`                                                                     | `#4B6168`                                  | hold, neutral sentiment                                      |
| `--color-background`           | `#07131A`                                                                     | `#F3F7F8`                                  | app background                                               |
| `--color-surface`              | `#0E1F27`                                                                     | `#FFFFFF`                                  | cards, panels                                                |
| surface sunken (new)           | `#0A1920`                                                                     | `#EAF1F2`                                  | tiles, the disclaimer band, row hover                        |
| `--color-border`               | `#1F3A44`                                                                     | `#D4E1E3`                                  | dividers                                                     |
| border strong (new)            | `#5E7D86`                                                                     | `#778C92`                                  | input borders (3:1)                                          |
| `--color-text-primary`         | `#E8F3F4`                                                                     | `#0B1D23`                                  | body text                                                    |
| `--color-text-secondary`       | `#9DB6BC`                                                                     | `#4B6168`                                  | captions, labels, disclaimers                                |
| `--color-text-inverse`         | `#04161B`                                                                     | `#FFFFFF`                                  | text on primary                                              |
| focus ring (new)               | `#33C9DB`                                                                     | `#0A6E80`                                  | one visible focus style everywhere                           |
| tints (new)                    | success `#113524`, danger `#3D1A1C`, warning `#34290F`                        | `#E2F4E8`, `#FEF4F0`, `#FFF3D9`            | badge and notice backgrounds                                 |
| chart series (new)             | portfolio `#33C9DB`, rules `#F5BC4A`, benchmark `#8AA3AA`, forecast `#C4A5FF` | `#0A6E80`, `#B45309`, `#6B7F85`, `#6D4AB8` | every series also differs by line style                      |
| gradient stops (new)           | `#33C9DB` → `#7BE0C3` → `#FF8466`                                             | `#0A8EA3` → `#2CC5D8` → `#FF8466`          | wordmark, landing bloom                                      |

**Rules (all met, and tested):**

- WCAG AA in both themes: every text pair the components draw is at least 4.5:1, and input borders, the focus ring and chart lines at least 3:1 (`packages/design-tokens/src/colors.test.ts`, run in CI).
- **Deviation (UI round, 2026-10-15) — colour-blind-tuned gains and losses:** instead of a generic red and green, a darker green against a brighter vermilion, so the pair differs in lightness as well as hue (simulated colour difference ΔE in light: protanopia 28, deuteranopia 48; in dark: 43 and 49). Always paired with ▲ / ▼ / — (§5, §6.3).
- The primary colour never colours a number, so a button is never read as a result. Risk badges use primary (Conservative), neutral (Moderate) and warning (Aggressive), never the gain or loss colours.
- Themes switch through CSS variables only, so changing the palette is a one-file change (`colors.ts`).

## 3. Typography

| Use                       | Font                                                                                                                   | Notes                                                                                                                                                                  |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Primary UI font (English) | Inter or system font stack (`-apple-system, Segoe UI, Roboto`)                                                         | Clean, highly legible, standard for fintech UIs                                                                                                                        |
| Urdu font                 | Noto Nastaliq Urdu (for headings/emphasis) or Noto Sans Arabic/Urdu (for body text, better readability at small sizes) | Body Urdu text should use the Naskh-style font, not Nastaliq, for readability at small UI sizes — reserve Nastaliq (if used at all) for large decorative headings only |
| Numeric/financial figures | Tabular (monospaced-number) figures, e.g., Inter's tabular-nums feature                                                | Prevents prices/percentages from jittering in width as digits change                                                                                                   |

**As built (team decision 2026-10-13, replacing the Naskh body font chosen on 2026-10-09):** all Urdu text uses **Nastaleeq**. The stack is "Jameel Noori Nastaleeq" when it is installed on the viewer's computer (never shipped: its licence does not clearly allow web embedding), then **Noto Nastaliq Urdu** (SIL Open Font License 1.1, self-hosted from `@fontsource/noto-nastaliq-urdu` so it works offline and makes no third-party request; weights 400 and 700 only, about 156 KB each, downloaded only when Urdu is on screen), then Noto Naskh Arabic. A `unicode-range` keeps Latin letters, digits, tickers and emails in the UI font. Urdu text (any element with `lang="ur"`, the whole page or one chat reply) gets a line height of 2.0 so dots and descenders are not clipped; Urdu inputs and selects grow instead of clipping, and the text inside a native `<select>` uses Naskh, because browsers draw a select's value on one fixed line that clips Nastaleeq's tall letters. Before/after screenshots: `docs/screenshots/phase8/before-*` and `after-*`.

**Deviation (UI round, 2026-10-15) — landing display font:** Bricolage Grotesque (SIL OFL 1.1, self-hosted, Latin only, 40 KB) for the headings of the public landing page and the auth panel; Urdu letters fall through to Nastaleeq. On the landing page only, the headline goes above `--text-3xl` (up to 72 px in English, 56 px in Urdu).

**Deviation (UI round, 2026-10-15) — the language toggle's label:** on English pages the four-letter "اردو" label is drawn in the system font, so the 156 KB Nastaleeq file is downloaded only when Urdu text is actually on screen. All other Urdu text stays Nastaleeq.

**Scale (web, rem-based):**

```
--text-xs:    0.75rem   (12px)  — captions, disclaimers, timestamps
--text-sm:    0.875rem  (14px)  — secondary body text, labels
--text-base:  1rem      (16px)  — body text
--text-lg:    1.125rem  (18px)  — emphasized body, card titles
--text-xl:    1.5rem    (24px)  — section headings
--text-2xl:   2rem      (32px)  — page headings
--text-3xl:   2.5rem    (40px)  — hero/landing headline only
```

Mobile app uses the same scale ratios via React Native's platform-appropriate `rem`-equivalent (density-independent pixels).

## 4. Spacing & Layout

- 8px base spacing unit (`--space-1: 8px`, `--space-2: 16px`, `--space-3: 24px`, `--space-4: 32px`, `--space-6: 48px`, `--space-8: 64px`) — every margin/padding in the app is a multiple of 8px, no arbitrary values
- Web: max content width 1200px, centered, with responsive breakpoints at 640px (mobile), 768px (tablet), 1024px (desktop)
- Mobile: safe-area-aware padding (respect notch/home-indicator on iOS, status bar on Android)
- Card-based layout for portfolio holdings, stock listings, and notification items — consistent card component (see Section 6.2) reused everywhere rather than bespoke layouts per screen

## 5. Iconography

- Use a single consistent icon set throughout (e.g., Lucide or Heroicons) — never mix icon libraries
- Financial direction icons: ▲ (up/gain), ▼ (down/loss), — (flat/hold) always paired with color, never color alone (accessibility, Section 2)
- Risk profile icons: distinct, simple glyphs for Conservative / Moderate / Aggressive (e.g., shield / balance-scale / rocket) used consistently across onboarding, dashboard, and portfolio screens

## 6. Core Components

### 6.1 Buttons

- Primary (filled, `--color-primary`) — one primary action per screen max
- Secondary (outlined) — secondary actions
- Destructive (uses `--color-danger`) — reserved for things like "exclude stock" or "log out," never for normal navigation
- Disabled state must be visually distinct, not just a slightly duller version of enabled

### 6.2 Card

- Used for: stock listings, portfolio holdings, notifications, backtest result summaries
- Standard structure: title row → key metric (large, tabular numerals) → secondary details → optional action row
- Consistent border-radius and shadow token across the whole app (define once, reuse — don't let each screen invent its own card style)

### 6.3 Financial Figure Display (critical, reused everywhere a number appears)

Every price/return/fee figure follows this pattern:

```
[±][value][unit]   e.g.  +12.4%   or   Rs. 45,230
(label beneath in --text-xs, --color-text-secondary)   e.g. "Net return after fees & tax"
```

- Gains: `--color-success` + ▲ prefix
- Losses: `--color-danger` + ▼ prefix (both colour-blind tuned, §2; one shared `Delta` component draws every gain, loss and no-change)
- Always show currency as "Rs." or "PKR" — never a bare number that could be mistaken for a different currency
- Gross vs net figures, when both are relevant (e.g., portfolio recommendation screen), always shown side-by-side or in a clearly labeled breakdown — never just "net" with gross hidden

### 6.4 Confidence/Uncertainty Indicator

- A visual meter or badge (not just a number) accompanies every AI prediction: e.g., a 3-segment bar (Low/Medium/High confidence) or a percentage badge with a color from the success/warning/neutral set
- Low-confidence predictions (per PRD.md FR16) get a visibly different treatment — a border/background tint using `--color-warning`, not just a small text note easy to miss

### 6.5 Chat Bubble (Chatbot UI)

- User messages: right-aligned, `--color-primary` background, `--color-text-inverse` text
- Assistant messages: left-aligned, `--color-surface` background, `--color-text-primary` text
- Assistant messages referencing real data (predictions, portfolio figures) visually cite the source inline (e.g., a small "from your current portfolio" tag) — reinforces the grounding principle from Architecture.md Section 12 and builds user trust that the bot isn't making things up
- Language toggle visible within the chat interface at all times, not buried in settings
- **As built (Phase 8, 2026-10-13, deviation):** bubbles use logical sides: the user's on the _end_ side and the assistant's on the _start_ side, so in Urdu (right to left) the user's bubbles sit on the left, as in Urdu chat apps, instead of always "right". Each bubble takes its direction from its own message (Urdu script right to left; English and Roman Urdu left to right) and keeps every figure left to right. Source tags are built by the server from the figures the reply actually used. The disclaimer banner sits under the chat; a reply in a language the banner is not in (Roman Urdu) repeats the disclaimer in its own language under the bubble.

### 6.6 Disclaimer Banner

- Persistent, non-dismissible-on-first-view banner/footer on onboarding and every recommendation/prediction screen: "Advisory only. Not a licensed financial advisor. Predictions are probabilistic. Execute trades only through a licensed PSX broker." (PRD.md Section 8.5)
- Styled to be legible, not hidden in tiny gray text — use `--text-sm` minimum, sufficient contrast, but visually secondary (not competing with primary content) via placement and a muted `--color-surface` background band

## 7. Key Screen UX Patterns

### 7.1 Onboarding / Risk Profiling

- Single-question-per-screen wizard, progress indicator at top, back button always available
- Plain-language question phrasing (no jargon) — e.g., instead of "What is your risk tolerance?", ask something concrete like "If your investment dropped 15% in a month, what would you do?"
- Result screen explains the assigned risk category in a sentence or two, not just a label — sets the tone for the whole product's "explain, don't just declare" philosophy

### 7.2 Stock Detail Screen

- Order top to bottom: price chart → key stats → AI prediction (with confidence) → sentiment ("what's driving this," headlines) → "add to portfolio consideration" action
- Chart interactions (zoom/pan on web, pinch/swipe on mobile) but never required to understand the basic trend — a plain-language summary line above the chart (e.g., "Up 8% over the last 30 days") for users who don't read charts fluently

### 7.3 Portfolio Recommendation Screen

- Lead with the plain-language summary (e.g., "Based on your moderate risk profile, here's a portfolio across 5 companies")
- Each holding as a card (Section 6.2): company, allocation %, gross price, fee/tax breakdown, net price
- Total portfolio summary at top or bottom: total invested, total fees/tax, net position
- "Why this stock" expandable detail per holding, pulling from prediction + sentiment data — never just a bare allocation number with no reasoning

### 7.4 Backtesting Report

- Headline metric (total return) largest/first, followed by Sharpe ratio, max drawdown, win rate as secondary metrics
- Visual comparison against KSE-100 benchmark (simple line chart, InvestIQ portfolio vs benchmark) — this is the single most persuasive visual for both users and the FYP panel

### 7.5 Notifications

- Grouped by type (buy/sell/roll) or chronological, user's choice
- Each notification card shows the action, the reasoning summary, and a direct link to the relevant stock/portfolio screen — never a dead-end notification

### 7.6 Admin Panel

- Data-dense, utilitarian — this is the one place in the product where "dashboard-y" (tables, status badges, charts) is appropriate, unlike the calmer investor-facing screens
- System health section uses the same success/warning/danger color logic as the rest of the app (green = healthy, amber = degraded, red = down) for consistency

## 8. Responsive & Cross-Platform Consistency

- Web and mobile should feel like the same product wearing different clothes — same information hierarchy, same component logic, same copy (via `packages/i18n`), different navigation patterns appropriate to each platform (top nav/sidebar on web, bottom tab bar on mobile)
- Mobile bottom tab bar (suggested): Home/Dashboard, Stocks, Portfolio, Chat, Notifications
- Any design token (color, spacing, type scale) defined once and consumed by both platforms — never redefine `--color-success` differently on web vs mobile

## 9. Accessibility

- WCAG AA contrast minimum throughout (Section 2)
- All interactive elements reachable via keyboard on web (tab order, focus states visible)
- Touch targets on mobile minimum 44x44dp
- Never convey meaning through color alone (Section 5, 6.3) — always pair with icon/text
- Urdu text direction and font rendering tested specifically, not assumed to "just work" because English does

## 10. Voice & Tone (UI Copy)

- **Plain-language first.** Every technical term (RSI, Sharpe ratio, CGT) gets a one-line plain explanation available on tap/hover (tooltip, Section 15) — never assume the user already knows it.
- **Honest about uncertainty.** Copy never says "will," always "may" or "is forecast to" when discussing predictions. E.g., not "This stock will rise 8%" but "AI forecasts an 8% rise, with medium confidence."
- **Calm, not hyped.** No exclamation marks on financial outcomes, no "🚀" emoji culture around gains — this is a trust product, not a meme-stock app. Losses are stated matter-of-factly, not softened into meaninglessness.
- **Second person, direct.** "Your portfolio," "you're classified as Moderate risk" — not passive/third-person phrasing.
- **Urdu tone matches, not just translates.** Urdu copy should sound like a knowledgeable friend explaining money, not a stiff formal/bureaucratic translation of the English string. Review Urdu copy for tone separately from literal accuracy.

## 11. Motion & Animation

- Motion is functional, never decorative-only: it should communicate state change (loading → loaded, list reordering, a new notification arriving), not just add flair
- Standard durations: micro-interactions (button press, toggle) 100–150ms; screen/panel transitions 200–300ms; nothing longer than 400ms anywhere in the app — this is a tool people check often, it must feel fast
- Standard easing: ease-out for elements entering, ease-in for elements leaving
- Respect `prefers-reduced-motion` on web; disable non-essential animation for users with that OS setting
- Chart animations (price line drawing in, bars growing) allowed once on initial load only — never re-animate on every re-render/refetch, which reads as sluggish
- Number transitions (e.g., a price ticking on refresh) use a brief count-up/count-down animation rather than an abrupt jump, but capped at ~500ms so it never feels like it's stalling
- **As built (UI round, 2026-10-15):** clickable cards lift 2 px on hover (150 ms), screens fade in on a route change (250 ms), charts draw in once on first load (400 ms), headline figures count up once (400 ms, always ending on the API's exact figure) and skeletons shimmer. All of it stops under `prefers-reduced-motion`.
- **Deviation (UI round, 2026-10-15) — landing page only:** the public landing page uses continuous, decorative motion that the in-app rules forbid: the 3D market bloom (breathing, pointer tilt, travelling sparks), the scroll-pinned zoom section, the cost rows revealing in sequence and the step icons' slow orbit. It is limited to that one public page; three.js loads only after the first paint; under reduced motion, without WebGL, on low-power devices or with Save-Data the bloom is a static image and the zoom shows its final frame. There is no 3D and no decorative motion on any logged-in screen.

## 12. Loading, Empty, and Error States (every screen needs all three, explicitly designed — never left as a blank white screen)

### 12.1 Loading States

- Skeleton loaders (gray placeholder shapes matching the eventual content's layout) for cards, charts, and lists — not spinners, except for full-page initial load or button-level in-progress actions (e.g., "Generating your portfolio…" with a small inline spinner on the button itself)
- Chart loading: show a skeleton chart shape, not a blank area, so layout doesn't jump when data arrives

### 12.2 Empty States

- Every list/collection screen (portfolio with no holdings yet, notifications with none yet, chat with no history) has a designed empty state: a short explanatory line + a relevant next action (e.g., empty portfolio → "You don't have a portfolio yet — generate one based on your risk profile" with a button)
- Empty states never just say "No data" with nothing else — always explain why and what to do next

### 12.3 Error States

- Network/API failure: inline error message + retry button, scoped to the failed section only (don't blank the whole screen if only the sentiment panel failed to load, per Architecture.md Section 8.3 graceful degradation)
- Form validation errors: inline, next to the specific field, in `--color-danger`, appearing on blur/submit — never a generic toast that doesn't say which field is wrong
- Full-page error (e.g., failed auth) gets a dedicated state with a clear action (e.g., "Session expired — log in again")

## 13. Forms & Input Patterns

- Label above input (not placeholder-as-label — placeholders disappear on typing and are an accessibility anti-pattern)
- Required fields marked consistently (e.g., asterisk); no field asks for information not justified by PRD.md's functional requirements
- Numeric/currency inputs use appropriate input modes (numeric keyboard on mobile) and format as the user types (e.g., thousands separators) where it aids readability without fighting the user's typing
- Risk questionnaire (Section 7.1) inputs are large, tappable choice cards rather than radio buttons/dropdowns — reduces friction and reads as more approachable for a novice user
- Every submit button shows a loading state and disables itself during submission (prevent double-submit, especially anything touching portfolio generation or auth)

## 14. Navigation Patterns (detail)

### 14.1 Web

- Top nav bar: logo, primary nav links (Dashboard, Stocks, Portfolio, Backtest, Chat), language toggle, notification bell, user menu (profile, risk profile, logout)
- **Deviation (UI round, 2026-10-15) — theme toggle:** a dark/light toggle sits next to the language toggle on every screen (landing, auth, onboarding and the app). Dark is the default; the choice is remembered on the device (`investiq.theme`) and applied before the first paint. Below 768 px the primary navigation is a bottom tab bar.
- Admin routes visually distinct (different top-bar color/badge — e.g., a small "Admin" tag) so it's never ambiguous which mode you're in, especially important since the same person may use both during FYP demos

### 14.2 Mobile

- Bottom tab bar (5 items max, per Section 8): Home, Stocks, Portfolio, Chat, Notifications
- Settings/profile/risk-profile access via a top-right icon or a "More"/profile tab, not crammed into the bottom bar
- Back navigation follows platform convention (Android hardware/gesture back, iOS swipe-back) — never trap the user

### 14.3 Breadcrumb / Context

- Stock detail, chat, and backtest report screens always show how the user got there or what they're looking at (e.g., a header showing "Portfolio > Engro Fertilizers" ) so deep-linked or notification-triggered navigation never feels disorienting

## 15. Tooltips & Contextual Help

- Every jargon term (RSI, MACD, Sharpe ratio, CGT, WHT, confidence score) has a tooltip/info-icon with a one-sentence plain-language definition, consistent wording reused everywhere that term appears
- Tooltips on mobile trigger via tap-and-hold or a small info icon (never hover-only, which doesn't exist on touch)
- First-time users see a lightweight one-time coach-mark/walkthrough on the dashboard and portfolio screen (dismissible, never forced, never repeats after first dismissal)

## 16. Modals & Dialogs

- Reserved for: confirmations with consequence (e.g., "exclude this stock and regenerate portfolio?"), and the risk-profile retake flow
- Never used for primary content (e.g., don't show the full portfolio recommendation in a modal — it deserves a full screen)
- Always dismissible via an explicit close action AND a backdrop click/tap (web) — except destructive confirmations, which require an explicit choice (no accidental backdrop-dismiss on "are you sure you want to log out")

## 17. Badges, Tags & Status Indicators

- Risk profile badge (Conservative/Moderate/Aggressive): consistent color+icon pairing (Section 5) used identically on the dashboard, onboarding result, and profile settings
- Signal badges (Buy/Sell/Hold): pill-shaped, color per Section 6.3 logic, always paired with the confidence indicator (Section 6.4) directly adjacent — never shown alone without confidence context
- Sentiment badge (Positive/Negative/Neutral): same pill pattern, distinct enough from signal badges to not be confused with them (e.g., different icon set — sentiment uses a face/mood-style icon, signals use arrow icons)

## 18. Charts (detail, extends Section 7.2)

- Price chart: line chart for simple trend view (default), optional candlestick toggle for more advanced users — default view should always be the simpler one
- Prediction overlay: forecast shown as a dashed/lighter-weight continuation of the historical line, visually distinct from actual historical data — never rendered identically to real data, to avoid a user mistaking a forecast for a fact
- Confidence band: shaded area around the forecast line widening with time horizon, reinforcing that further-out predictions are less certain
- Backtest comparison chart: InvestIQ portfolio line vs KSE-100 benchmark line, distinct colors, legend always visible (not just on hover) since this is a key persuasive/defense visual
- All charts have accessible data-table fallback or at minimum a text summary line (e.g., "Up 8% over 30 days") for screen readers and quick scanning

## 19. Push Notification Content Design (not just in-app notification list — the actual OS-level push)

- Title: short, action-oriented — e.g., "Sell signal: Engro Fertilizers"
- Body: one-line reasoning — e.g., "AI confidence dropped to 55%, sentiment turned negative this week"
- Tapping opens directly to the relevant stock/portfolio screen (deep link), never just the app's home screen
- Never include a raw predicted price figure in the push notification body itself (space-constrained, easy to misread out of context) — save exact figures for the in-app detail

## 20. Design Tokens — File Structure (for Antigravity AI to implement)

```
packages/design-tokens/
├── colors.ts          # placeholder values per Section 2, single source of truth
├── typography.ts       # font families, scale from Section 3
├── spacing.ts           # 8px-based scale from Section 4
├── shadows.ts            # elevation levels, see Section 21
├── motion.ts              # durations/easing from Section 11
└── index.ts                # re-exports everything
```

Both `apps/web` (as CSS variables / Tailwind theme extension) and `apps/mobile` (as a React Native theme object) consume this single package — no duplicated token definitions, per Section 8's cross-platform consistency rule.

## 21. Elevation / Shadow System

```
--elevation-0: none                                  /* flat elements, page background */
--elevation-1: 0 1px 2px rgba(0,0,0,0.06)             /* cards at rest */
--elevation-2: 0 4px 8px rgba(0,0,0,0.08)              /* raised cards, dropdowns */
--elevation-3: 0 8px 16px rgba(0,0,0,0.12)              /* modals, floating action elements */
```

**As built (2026-10-15):** `packages/design-tokens/src/shadows.ts` defines both sets; the dark set adds a 1 px light hairline (3-7% white) to each level. Dark-mode shadow values should use lower opacity + a subtle lighter border instead of relying purely on shadow (shadows read poorly on dark backgrounds) — if dark mode is the chosen theme, define a parallel `--elevation-*-dark` set rather than reusing light-mode shadow values as-is.

## 22. Grid System

- Web: 12-column responsive grid, `--space-2` (16px) gutters, content max-width 1200px (Section 4)
- Dashboard/portfolio layouts: 2-column on desktop (main content + summary sidebar), collapsing to single-column stacked on tablet/mobile breakpoints
- Mobile: single-column by default; only the stock-comparison or admin-analytics views may use a 2-column grid on tablet-sized mobile devices

## 23. Right-to-Left (Urdu) Layout Handling

- Urdu is a right-to-left script. When the app language is set to Urdu, layout direction flips (`dir="rtl"` on web root) — icons that imply direction (back arrows, forward chevrons) must also flip
- Numeric figures (prices, percentages) remain left-to-right internally even within an RTL layout — this is standard bidi handling, not optional, since financial figures read incorrectly if reversed
- Test every screen in Section 7 specifically in Urdu/RTL mode, not just English — RTL bugs (misaligned icons, overflowing labels) are easy to miss if only ever designed/reviewed in English

## 24. Text Expansion & Truncation

- Urdu and English string lengths differ significantly for the same meaning — never design a component around English text's exact pixel width (e.g., button labels, badge text) — allow for 30–40% length variance
- Truncate with ellipsis + full text on tap/tooltip for long company names in cards/lists, never silently cut off with no way to see the full name

## 25. What Antigravity AI should NOT do (expanded)

- ~~Do not invent a color palette and ship it as final~~ — retired 2026-10-15: the palette was chosen with the team (§2); never hard-code a colour outside `packages/design-tokens`
- Do not create one-off component styles per screen — always check Section 6 for an existing pattern first
- Do not hardcode Urdu or English strings directly in component markup — route through `packages/i18n` per Rules.md Section 4.4
- Do not treat the disclaimer banner (Section 6.6) as optional or skippable on any prediction/recommendation screen
- Do not design or build a screen without an explicit loading, empty, and error state (Section 12) — "just show the happy path" is not acceptable for a financial product
- Do not render forecast data visually identical to historical/actual data on any chart (Section 18) — the distinction is a safety feature, not a style choice
- Do not skip RTL/Urdu testing on a screen because "it's just a layout flip" — verify it explicitly (Section 23)
- Do not use hover-only interactions for anything that must also work on mobile touch (tooltips, Section 15)

# Design.md — InvestIQ

### UI/UX Design System

**Companion docs:** PRD.md, Architecture.md, Rules.md, Phases.md
**Status:** Structure complete — **color palette intentionally left as a placeholder**, to be filled in by Manam. Everything else (typography, spacing, components, UX patterns, accessibility) is final and should be followed as-is.

---

## 1. Design Principles

1. **Clarity over cleverness.** The entire product exists to make PSX investing less intimidating. Every screen should feel calmer and simpler than a typical trading app, not more advanced.
2. **Numbers are never naked.** Every price, return, or fee figure is labeled clearly (gross vs net, currency, time period) — a novice user should never have to guess what a number means.
3. **Uncertainty is visible, not hidden.** Confidence scores, low-confidence flags, and disclaimers are a designed part of the UI, not fine print apologetically tucked away.
4. **Bilingual is a first-class citizen, not an afterthought.** Urdu text (RTL-aware where needed) must get the same layout care as English — no cramped or truncated Urdu labels.
5. **Trust is built visually, not just through copy.** Consistent, professional visual language (spacing, alignment, restrained color use) signals "this is a serious financial tool," which matters for a product asking users to trust it with investment decisions.

## 2. Color Palette — **⚠️ PLACEHOLDER, PENDING YOUR INPUT**

```
/* Fill these in once you've decided on your theme */

--color-primary:        #______;   /* main brand color — buttons, active states, links */
--color-primary-dark:   #______;   /* hover/pressed state of primary */
--color-secondary:      #______;   /* accent color — used sparingly, e.g. highlights */

--color-success:        #______;   /* positive returns, "buy" signals, gains (commonly green) */
--color-danger:         #______;   /* negative returns, "sell" signals, losses (commonly red) */
--color-warning:        #______;   /* low-confidence flags, alerts (commonly amber/gold) */
--color-neutral:        #______;   /* "hold" signals, neutral sentiment */

--color-background:     #______;   /* app background */
--color-surface:        #______;   /* card/panel background */
--color-border:         #______;   /* dividers, input borders */

--color-text-primary:   #______;   /* main body text */
--color-text-secondary: #______;   /* muted/secondary text, captions, disclaimers */
--color-text-inverse:   #______;   /* text on top of primary-colored backgrounds */
```

**Rules regardless of final palette chosen:**

- Success/danger/warning colors must be color-blind-safe distinguishable (don't rely on red/green alone — pair with icons: ▲/▼, or +/− prefixes, per Section 6.3)
- Maintain WCAG AA contrast ratio (4.5:1 minimum) for all text against its background
- If dark mode is chosen as the primary theme, still define a light-mode fallback token set — some users will have system-level light mode forced, and Antigravity AI should implement theme-switching via CSS variables/tokens (not hardcoded hex values scattered through components) so swapping the palette later is a one-file change, not a rewrite

## 3. Typography

| Use                       | Font                                                                                                                   | Notes                                                                                                                                                                  |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Primary UI font (English) | Inter or system font stack (`-apple-system, Segoe UI, Roboto`)                                                         | Clean, highly legible, standard for fintech UIs                                                                                                                        |
| Urdu font                 | Noto Nastaliq Urdu (for headings/emphasis) or Noto Sans Arabic/Urdu (for body text, better readability at small sizes) | Body Urdu text should use the Naskh-style font, not Nastaliq, for readability at small UI sizes — reserve Nastaliq (if used at all) for large decorative headings only |
| Numeric/financial figures | Tabular (monospaced-number) figures, e.g., Inter's tabular-nums feature                                                | Prevents prices/percentages from jittering in width as digits change                                                                                                   |

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
- Losses: `--color-danger` + ▼ prefix
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

Dark-mode shadow values should use lower opacity + a subtle lighter border instead of relying purely on shadow (shadows read poorly on dark backgrounds) — if dark mode is the chosen theme, define a parallel `--elevation-*-dark` set rather than reusing light-mode shadow values as-is.

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

- Do not invent a color palette and ship it as final — use the placeholder token names from Section 2 with obviously-fake values (or a neutral gray/blue holding palette) until Manam provides real values, so nothing looks "finished" prematurely
- Do not create one-off component styles per screen — always check Section 6 for an existing pattern first
- Do not hardcode Urdu or English strings directly in component markup — route through `packages/i18n` per Rules.md Section 4.4
- Do not treat the disclaimer banner (Section 6.6) as optional or skippable on any prediction/recommendation screen
- Do not design or build a screen without an explicit loading, empty, and error state (Section 12) — "just show the happy path" is not acceptable for a financial product
- Do not render forecast data visually identical to historical/actual data on any chart (Section 18) — the distinction is a safety feature, not a style choice
- Do not skip RTL/Urdu testing on a screen because "it's just a layout flip" — verify it explicitly (Section 23)
- Do not use hover-only interactions for anything that must also work on mobile touch (tooltips, Section 15)

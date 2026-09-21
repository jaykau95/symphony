---
name: editorial-email
description: House style for designing and writing HTML emails. Auction-catalogue restraint — 600px white card on warm greige, monochrome only, italic serif display against sans body, tracked-caps micro-labels, roman-numeral sections, one tinted stat panel, one sharp-cornered black CTA. Use for any marketing email, newsletter, announcement, campaign, lifecycle or transactional-adjacent send, or when asked to design, write, lay out or review an email.
---

# Editorial Email

The reference standard is an auction-house catalogue page, not a marketing email.
Restraint is the whole point. Every rule below exists to keep an email from
looking like it was assembled from a template gallery.

Apply this to **every** email unless the user explicitly asks for something else.

---

## 1. Banned outright

No exceptions without the user overriding in writing.

- **Rounded corners.** `border-radius` is `0` everywhere. Buttons, panels, images.
- **Colour.** No accent, no brand hue, no coloured link, no coloured badge. The
  palette in §2 is complete. If a logo demands colour, it lives in the logo only.
- **Gradients, drop shadows, glows, borders thicker than 1px.**
- **Emoji, icons, icon rows, illustration spots, stock photography.**
- **Two different actions.** One email, one action. Repeating the *same*
  button twice is fine (§7); footer utility links don't count.
- **Exclamation marks.** Anywhere. Including subject lines.
- **Hype vocabulary**: *revolutionary, game-changing, unlock, supercharge,
  seamless, elevate, transform, delighted to announce, excited to share,
  don't miss out, limited time.*
- **`Hi {FirstName}!` openers** and any merge-tag chumminess.
- **Feature grids, card decks, pricing tables, testimonial carousels.** A
  three-across grid of *real items with real photographs* is allowed (§7).
- **Centre-aligned body copy.** Only display type and the stat panel centre.
- **Dark mode inversion tricks.** See §10.

---

## 2. Palette — complete, measured

| Token | Hex | Use |
|---|---|---|
| Ink | `#111111` | Display headlines, stat numeral, CTA fill, logo block |
| Body | `#333333` | All running copy |
| Muted | `#8C877B` | Eyebrows, section labels, stat label, micro-copy |
| Footer ink | `#8A8578` | Footer text and links |
| Surface | `#F0EDE8` | Page background, stat panel, footer band |
| Card | `#FFFFFF` | The email body card |
| Rule (header) | `#D9D9D9` | Hairline under the masthead |
| Rule (content) | `#D8D4CD` | Divider before the close |

Seven values and white. Do not add an eighth.

---

## 3. Geometry — measured

- Page background `#F0EDE8`, full bleed.
- Card **600px** wide, `#FFFFFF`, centred. On mobile it goes fluid to 100%.
- Card padding **44px** left and right → **512px content column**. Every element
  spans that column; nothing is inset further except by centring.
- Masthead: white, logo centred, **1px `#D9D9D9`** rule beneath.
- Footer sits **outside** the white card, on the `#F0EDE8` background.
- Stat panel: full 512px content width, `#F0EDE8`, **~208px** tall, no border.
- CTA: **~257 × 38px**, `#111111`, **square corners**, centred.
- Content divider: 1px `#D8D4CD`, full content width.

**Vertical rhythm.** Generous and uneven on purpose:

| Gap | px |
|---|---|
| Eyebrow → headline | 24 |
| Headline → first paragraph | 33 |
| Paragraph → paragraph | 28 |
| Body → stat panel | 56–64 |
| Stat panel → first section | 40 |
| Section → section | 40 |
| Last section → divider | 48 |
| Divider → closing line | 36 |
| Closing line → CTA | 32 |

When in doubt, add space. This design fails by being cramped, never by being airy.

---

## 4. Type — measured

Two families. Serif carries voice, sans carries information. Never mix the roles.

```
Display serif : Georgia, 'Times New Roman', serif          /* italic, always */
Body sans     : -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif
```

If the brand licenses a high-contrast display serif (Canela, Freight Display,
GT Sectra), lead the stack with it and keep Georgia as the fallback — Outlook
and most clients will render the fallback, so the design must hold up in Georgia.

| Element | Size | Line-height | Style |
|---|---|---|---|
| Hero headline | 30px | 39px | Serif, **italic**, `#111`, centred |
| Stat numeral | 48px | 1 | Serif, **italic**, `#111`, centred |
| Closing line | 20px | 26px | Serif, **italic**, `#111`, centred |
| Body | 15px | 26px | Sans, `#333`, **left** |
| Eyebrow / section label / stat label | 10px | 1.4 | Sans, CAPS, `letter-spacing:.18em`, `#8C877B` |
| CTA label | 11px | 1 | Sans, CAPS, `letter-spacing:.14em`, `#FFF` |
| Micro-copy under CTA | 12px | 1.5 | Sans, `#8A8578`, centred |
| Footer | 12px | 18px | Sans, `#8A8578`, centred |

**The tracked-caps micro-label is the signature of this system.** The same
10px/0.18em treatment marks the eyebrow, every section heading, the stat label
and the button. That single repeated detail is what makes the email read as one
designed object. Never substitute bold sans headings for it.

---

## 5. Purpose first — what to leave out

**The most common failure of this system is using it to publish everything you
know.** The restraint has to apply to content, not just colour. Decide the job
before writing a word, then cut everything that does not serve it.

| Job | Reader needs | Cut |
|---|---|---|
| **Announce / drive registration** | What it is, when, why it matters, one action | Full inventory, house-by-house lists, process essays, backstory |
| **Catalogue / full listing** | Every item, in order, with condition notes | Persuasion, repetition of the announcement |
| **Explain a service** | The discipline, the limits, the proof | Item lists, logistics tables |

Word budgets, hard:

- **Announcement or registration email: 200–250 words.** Image-led.
- Service or positioning email: 350–450 words.
- Catalogue: as long as the items require, and nothing else.

Rules for cutting:

- **Name a representative few, then count the rest.** *"Patek Philippe, Rolex,
  F.P. Journe, Greubel Forsey and sixteen others"* beats twenty names in a row.
- **Three highlights, not eleven.** Pick the most valuable, the most complete
  and the most recognisable. Link to the rest.
- **Logistics belong in a panel, not in prose.** Dates, times, formats and
  counts are scanned, never read. See §7.
- If a fact does not change whether the reader acts, it belongs on the landing
  page, not in the email.

---

## 6. Structure

Both variants share the masthead, eyebrow, italic-serif headline, tinted panel,
divider, closing line, CTA and footer. They differ in the middle.

### A. Announcement / registration  *(default for a campaign)*

1. **Masthead** — wordmark, hairline beneath.
2. **Eyebrow** — what and when. *"ONLINE-ONLY AUCTION · 2–6 OCTOBER 2026"*
3. **Headline** — italic serif, short. *"A Century of Watchmaking"*
4. **Sub-line** — tracked caps, the qualifier the headline dropped.
5. **Hero image** — 512px wide, square corners. Not optional here: a
   text-only announcement is what "doesn't look good" means.
6. **Lede** — one paragraph, three sentences. Scale, span, and the one thing
   that makes it unusual. Nothing else.
7. **Details panel** — the tinted block as a label/value table (§7).
8. **Primary CTA** — immediately after the details. Most readers act here.
9. **Highlights** — three items, images, name plus one line each. Then one
   muted line naming a few more.
10. **Divider → closing line → CTA repeat → micro-copy → footer.**

### B. Service / positioning

Masthead → eyebrow → headline → opening (2 paragraphs) → stat panel →
**roman-numeral sections, 3–5**, tracked-caps label and one paragraph each →
divider → closing line → CTA → micro-copy → footer.

Roman numerals belong to variant B. An announcement does not need them.

## 7. Components

### Tinted panel — two uses, one per email

**Stat** (variant B): giant italic numeral, tracked-caps label, one centred
sentence that gives the claim its context and its limit.

**Details** (variant A): a label/value table. Tracked-caps muted label in a 38%
left column, value in 15px `#111111` on the right. Four rows is the ceiling —
dates, bidding time, count, format. On mobile both columns go full-width and
stack, label above value.

Never put both panels in one email.

### Highlights grid

Three items across the 512px column: 160px cells with 16px gutters
(160×3 + 16×2 = 512). Each cell is a 160×200 portrait image, the item name in
**italic serif 15/21**, then one 13px sans line — a single fact, not a
description.

On mobile the cells stack. **Cap the image at `max-width:180px`** — letting it
go to 100% blows a 160×200 portrait up to full bleed and doubles the email's
height. This is the one place the fluid-image rule is wrong.

Follow the grid with one muted 13px line naming a few more items, then stop.
This is not the banned three-column feature grid: it is a catalogue plate, and
it carries real items with real images, not invented benefits with icons.

### CTA

One **action** per email. Placing that same button twice — once after the
details panel, once after the closing line — is correct for an announcement,
because the two placements catch readers who decide early and readers who
decide late. Same label, same URL, both times. Two *different* actions is the
thing that is banned.

### Images and placeholders

Every `<img>` needs a real `src`. When the asset does not exist yet, ship a
**visible placeholder** — flat `#E6E2DB`, 1px `#D6D1C8` border, corner-to-corner
hairlines, centred tracked-caps label stating the dimensions — never an empty
band and never a sized-but-broken image. A placeholder that announces itself
gets replaced; white space does not.

---

## 8. Copy

The visual restraint is worthless if the writing oversells. Hold the line:

- **Declare, don't sell.** State what you do and how. Let the reader conclude.
- **Admit limits.** The most persuasive line in the reference is
  *"Where an original part is unavailable, we say so, rather than substitute
  silently."* Every email should contain one sentence that costs you something.
- **One number, qualified.** A single quantified claim, with its basis
  (*"on average"*) and its boundary (*"without asking you to compromise"*).
  Never a wall of statistics.
- **Concrete nouns over abstractions.** *Lug lines, calibres, patina* — not
  *quality, excellence, expertise*.
- **Subject lines** declare, run 4–8 words, use no colon-clickbait and no
  brackets. *"A different standard of care for vintage timepieces."*
- **Preheader** extends the subject, never repeats it.

---

## 9. Email-safe build rules

This must survive Outlook. Divs and flexbox will not.

- **Tables for all layout.** `role="presentation"`, `cellpadding="0"`,
  `cellspacing="0"`, `border="0"`.
- **Every style inline.** Keep a `<style>` block only for media queries and
  dark-mode locks; assume it is stripped.
- **Spacing via table cells** (`padding` on `<td>`) or spacer rows. Never
  margin-collapse. Never rely on `<br>` stacks.
- **Button** = a `<table>` with `bgcolor="#111111"` and an `<a>` filling a
  padded `<td>`. Square corners mean no VML roundrect is needed.
- **Images**: `display:block`, explicit `width`, `border:0`, real `alt` text
  written in the same voice as the copy.
- **Width**: card table `width="600"` with `max-width:600px`; the media query
  drops it to `100%` and padding to `24px` under 600px.
- Set `background-color` on `<body>` **and** a wrapper `<table>` — several
  clients ignore one or the other.

---

## 10. Dark mode

Clients that auto-invert will wreck a warm greige palette. Lock it:

```html
<meta name="color-scheme" content="light only">
<meta name="supported-color-schemes" content="light only">
```
```css
:root { color-scheme: light only; }
```

Then verify the CTA specifically: `#111111` on white is the element most often
mangled by forced inversion. Never design a separate dark variant — this system
is light only.

---

## 11. Pre-flight

Refuse to ship until every line is true.

- [ ] The job is named, and the copy is inside its word budget (§5).
- [ ] Exactly one **action**, square-cornered, `#111111`.
- [ ] `border-radius` appears **nowhere**.
- [ ] No hex outside the eight in §2.
- [ ] Display type is serif **italic**; body is sans; neither role borrowed.
- [ ] Eyebrow, section labels, stat label and CTA all share the tracked-caps
      treatment.
- [ ] Roman numerals only if this is variant B.
- [ ] Exactly one quantified claim, and it is qualified.
- [ ] No fact in the email that you were not given. No invented reassurance
      ("free", "takes two minutes", "limited places").
- [ ] One sentence in the email admits a limit.
- [ ] Zero exclamation marks, zero emoji, zero banned vocabulary.
- [ ] Every image has a real `src` or a visible placeholder — **no empty bands**.
- [ ] Mobile: highlight images capped, not fluid to 100%.
- [ ] Layout is tables, styles are inline, dark mode is locked.
- [ ] Renders at 600px and reflows under 600px.
- [ ] Footer carries unsubscribe, preferences and a postal address.

---

`reference/template.html` is a complete, client-safe skeleton built to this
spec. Start from it rather than from memory.

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
- **Multiple CTAs.** One email, one action. Footer utility links don't count.
- **Exclamation marks.** Anywhere. Including subject lines.
- **Hype vocabulary**: *revolutionary, game-changing, unlock, supercharge,
  seamless, elevate, transform, delighted to announce, excited to share,
  don't miss out, limited time.*
- **`Hi {FirstName}!` openers** and any merge-tag chumminess.
- **Three-column feature grids, card decks, pricing tables, testimonial carousels.**
- **Centre-aligned body copy.** Only display type and the stat panel centre.
- **Dark mode inversion tricks.** See §8.

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

## 5. Structure

Emails follow this spine. Drop sections that have nothing to say; never reorder.

1. **Masthead** — wordmark only, centred, hairline beneath.
2. **Eyebrow** — tracked caps, names the sender department or series.
   *"FUTUREGRAIL SERVICE CENTRE"*
3. **Hero headline** — italic serif, centred, 1–2 lines, states a position
   rather than an offer. *"A Different Standard of Care for Vintage Timepieces"*
4. **Opening** — two short paragraphs. The first establishes why the subject is
   difficult. The second says how you approach it. No pitch yet.
5. **Hero image** *(optional)* — full 512px content width, square corners.
   **If you include one, it must be a real asset path.** An unfilled slot leaves
   a large dead white band that reads as a broken send.
6. **Stat panel** — the one tinted block. Giant italic numeral, tracked-caps
   label, then one centred sentence giving the claim its context and its limit.
7. **Numbered sections** — **roman numerals**, 3–5 of them. Tracked-caps label,
   then one paragraph. No bullets, no icons, no rules between them.
   *"I. MOVEMENT RESTORATION"*, *"II. CASE & BRACELET"*
8. **Divider** — 1px `#D8D4CD`.
9. **Closing line** — italic serif, centred, one sentence. An aphorism about the
   subject, not about the company. *"A vintage watch, properly cared for, does
   not resist time. It simply continues keeping it."*
10. **CTA** — one black square button.
11. **Micro-copy** — one line naming the alternative route. *"Reply to this
    email or DM us to arrange a consultation."*
12. **Footer** — preferences / unsubscribe, postal address, copyright. Outside
    the card, on the greige.

---

## 6. Copy

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

## 7. Email-safe build rules

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

## 8. Dark mode

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

## 9. Pre-flight

Refuse to ship until every line is true.

- [ ] Exactly **one** CTA, square-cornered, `#111111`.
- [ ] `border-radius` appears **nowhere**.
- [ ] No hex outside the eight in §2.
- [ ] Display type is serif **italic**; body is sans; neither role borrowed.
- [ ] Eyebrow, section labels, stat label and CTA all share the tracked-caps
      treatment.
- [ ] Sections use roman numerals.
- [ ] Exactly one quantified claim, and it is qualified.
- [ ] One sentence in the email admits a limit.
- [ ] Zero exclamation marks, zero emoji, zero banned vocabulary.
- [ ] Every image slot has a real `src` — **no empty bands**.
- [ ] Layout is tables, styles are inline, dark mode is locked.
- [ ] Renders at 600px and reflows under 600px.
- [ ] Footer carries unsubscribe, preferences and a postal address.

---

`reference/template.html` is a complete, client-safe skeleton built to this
spec. Start from it rather than from memory.

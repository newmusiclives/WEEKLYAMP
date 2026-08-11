# TrueFans RADIO × TrueFans DISPATCH — Co-Promotion Playbook

Status: proposed, 2026-08-11. Owner: Paul.
Both properties are owned by the same company, so this is not a barter
negotiation with a partner station — it is one funnel with two front doors,
and all inventory on both sides is ours to allocate.

---

## 1. Why this works: the two channels fix each other's weakness

| | RADIO | DISPATCH |
|---|---|---|
| Reach | Ambient, passive, wide | Only people who already opted in |
| Addressability | Zero — every listener is anonymous | Total — every reader is a row in Postgres |
| Measurability | Effectively none | Per-open, per-click, per-section |
| Persistence | Ephemeral, gone in 3 minutes | Sits in an inbox, forwardable, archived |
| Discovery | Strong — people find it by accident | Weak — no discovery surface at all |

Read that table as one sentence: **radio has the reach but can't own the
audience; the newsletter owns the audience but can't reach anyone new.**

That gives each channel exactly one primary job for the other. Everything
else in this document is secondary to these two:

- **RADIO's job for DISPATCH:** convert anonymous reach into an owned,
  addressable list. A listener is a stranger; a subscriber is an asset.
- **DISPATCH's job for RADIO:** manufacture *appointment listening*. Driving
  someone to "listen sometime" is worth almost nothing. Driving them to a
  specific show at a specific hour is the only thing that moves stream
  concurrency and makes on-air inventory sellable.

## 2. RADIO → DISPATCH: converting listeners into subscribers

### The callback promise (the highest-converting mechanic)

Do not run "check out our newsletter" reads. Brand-level CTAs fail on radio.
The one that works ties the ask to a problem the listener *just experienced*:

> "Everything we played this hour — every artist, every link — lands in your
> inbox tomorrow morning. Free. [city].truefansradio.com/list"

This converts because it isn't asking for brand affinity, it's answering
"what was that song?" — the single most common unspoken thought a music
listener has. The newsletter becomes the station's memory.

### Rules for the on-air read

1. **Same slot every hour** (e.g. :28 and :58). Predictability compounds;
   scattered reads don't.
2. **Host-read, live, never a produced spot.** In this format a produced ad
   is heard as an ad and tuned out. A host saying it in their own words is
   heard as information.
3. **Two per hour, hard cap.** Over-promotion trains listeners to tune out
   the station, and the damage is not recoverable in the short term.
4. **One URL, spoken slowly, twice.** If it can't be remembered through a
   car windshield it doesn't exist.

### Vanity URL per show, not per station

Radio cannot carry a UTM parameter — the URL *is* the tracking. Give each
show its own path (`/list/driveinhome`, `/list/morning`) which 301s to the
subscribe form with the source pre-set. That tells you which host actually
converts, which is information you cannot get any other way and which will
almost certainly surprise you.

### The station website is the highest-intent surface you own

DISPATCH already ships an embeddable subscribe widget
(`/embed/subscribe`, `src/weeklyamp/web/routes/embed.py`). Put it:

- Above the fold on the station home page.
- On the **now-playing / recently-played page** — this is the single
  highest-intent page on the whole property. Someone on it is actively
  trying to identify a song. That is precisely the promise the newsletter
  makes. Expect this one placement to outperform the home page.
- In the stream player's companion panel, where a click is possible and a
  real UTM can be attached.

## 3. DISPATCH → RADIO: manufacturing appointment listening

### Drive to a *time*, never to "anytime"

An "On air this week" module only earns its space if every line has a day
and an hour attached, ideally with a calendar link. "Listen live" is not a
call to action; "Thursday 8pm, Sugar Lime Blue live in session" is.

### The spin-data content loop (the best free content you'll ever get)

"The 10 most-played songs in [city] this week" is genuinely good newsletter
content, it's *free* — a pure byproduct of running the station — and it is
enormously shareable by the artists on it. An artist who charts will post
about it to their own fans, which is your cheapest possible acquisition
channel. Ship this as a recurring auto-generated section.

### Requests and dedications close the loop visibly

A request form in the newsletter → played on air → the requester named on
air → mentioned again in next week's edition. This is a small feature that
does something no ad can: it proves to readers that the two properties are
one thing, and it gives them a reason to listen *at a specific time*.

## 4. The shared content engine (the real advantage of owning both)

Because both properties are ours, they should run off one pipeline, not two:

- **One submission door.** `/submit` already exists. An artist submits once
  and is considered for both editorial coverage and rotation. You get double
  the value per submission; the artist gets half the friction.
- **Guaranteed reciprocity.** Every artist featured in DISPATCH gets
  airplay; every artist added to rotation gets a newsletter mention. Make
  this an explicit, published promise. It converts every featured artist
  into a promoter of *both* properties to their own fanbase — which is the
  highest-leverage distribution available to a local music brand.
- **Shared scene data.** The events/scene-graph data already powering the
  newsletter calendar is the same data a host needs for "what's on tonight."
  Write it once.

## 5. The money: bundled sponsorship

This is the strongest commercial reason to run the two together.

Local radio inventory is cheap and unmeasurable. Newsletter inventory is
measurable but scarce (27 ad slots today, per
`src/weeklyamp/web/routes/sponsor_blocks.py`). Sold separately, both are
weak propositions. Sold as one package they fix each other:

> **The local bundle:** on-air reads + a newsletter ad slot + one edition
> takeover, sold as a single line item.

- The newsletter's click data makes the *whole* spend defensible to the
  advertiser — including the radio half, which they could never measure
  before.
- The radio reach makes the package big enough to justify a real budget,
  which a newsletter slot alone often isn't.
- Charge more than the sum of the parts. The measurement is the premium.

This also materially strengthens the `/license` city-franchise offer: a
licensee who gets a newsletter *and* a station is buying a local media
business, not a mailing list.

## 6. Attribution design (and its honest limits)

Radio attribution is structurally undercounted — many people will type the
base URL, or search the brand name, and never touch the vanity path. Build
for direction, not precision:

1. **Vanity path per show** → `/subscribe?source=radio-<show>`, persisted on
   the subscriber row.
2. **A one-click "how did you hear about us?"** on the confirmation page as
   a backstop — it catches the people the vanity URL misses.
3. **Aggregate lift**: watch total signups in the 30 minutes following each
   promo block. With a fixed hourly slot this becomes a clean signal even
   when individual attribution fails.
4. **The reverse direction is easy** — newsletter → stream clicks already
   route through `/t` and are exactly measurable. Report both directions
   side by side.

Do not let the imprecision of (1)–(3) stop you shipping. Directional data
about which host converts is worth far more than no data.

## 7. Weekly operating rhythm

| When | What |
|---|---|
| Mon | Pull last week's spin counts → generate the "most played" section |
| Mon | Rotation adds decided from the submission queue → mention list for the week |
| Tue–Fri | Edition ships with On-Air module (day + hour on every line) |
| Daily | Two host reads per hour of the callback promise, fixed slots |
| Fri | Review: signups by show vanity path, newsletter → stream clicks |
| Monthly | Bundle sponsorship report to advertisers — combined reach + clicks |

## 8. What NOT to do

- **Don't let the newsletter become a program guide.** It has to stand on
  its own for someone who never listens. The radio module is a section, not
  the spine.
- **Don't split the brand.** One name, one look, one signup, one login.
  Two brands means paying twice for the same recognition.
- **Don't exceed two reads an hour.** See §2.
- **Don't automate before the manual loop works.** Run the hourly read and
  the weekly spin section by hand for a month before building ingestion.

---

## 9. Build plan for DISPATCH

Ordered by dependency. Phase 1 is small and unblocks all measurement.

### Phase 1 — measurement foundation (nothing else is meaningful without it)

1. **Fix hardcoded signup source.** `src/weeklyamp/web/routes/subscribe.py:140`
   passes `source_channel="website"` unconditionally, so every signup looks
   identical regardless of origin. Accept and persist `?source=`.
   *Without this, no radio attribution is possible at all.*
2. **Vanity redirect route** — `/list/{show}` → subscribe form with the
   source pre-set, plus a hit counter so you see reach even when the signup
   doesn't complete.
3. **"How did you hear" prompt** on the subscribe confirmation page.

### Phase 2 — the cross-promo surfaces

4. **RADIO as a promo-block target.** `PromoConfig`/`PromoTarget`
   (`src/weeklyamp/core/models.py:728-773`) already support configurable
   targets with UTM and `/t/promo` click tracking. Add a `radio` target.
5. **Market-aware promo routing.** Routing today keys on `edition_slug` /
   `audience`. City editions already exist via `/admin/markets`, so extend
   routing to key on market → the right local station stream.
6. **On-Air module** as a new edition section — day, hour, calendar link.

### Phase 3 — the content loop and the money

7. **Spin-data ingestion** → auto-generated "most played this week" section.
8. **Request form** (`/request`) → admin queue → on-air, with the follow-up
   mention back in the newsletter.
9. **Bundled sponsorship inventory** — extend `sponsor_blocks` so one
   booking covers both a newsletter slot and on-air reads, and the
   advertiser report shows them together.
10. **Attribution dashboard** — signups by radio source vs. newsletter →
    stream clicks, both directions on one page.

### Deliberately deferred

- Automated stream/now-playing API integration (do it by hand first).
- Any shared-login / single-sign-on work between the properties.
- Podcast/on-demand repackaging of station content.

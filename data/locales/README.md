# Locale Fact Sheets

Hyperlocal editions reference real venues, studios, festivals, and people. Without
a constraint, the writer hallucinates — see the `demo_corrales_artist.html` v1
draft, which referenced the Corrales Bistro Brewery (closed since 2021), invented
"Empire Recording" in the North Valley, and put The Kitchen Sink studio in the
wrong city.

Fix: each locale gets a YAML fact sheet of **verified entities only**. The writer
is hard-constrained to reference nothing else, and a post-draft guardrail flags
any named entity that isn't on the sheet.

## File layout

One file per locale, kebab-case: `<city>-<state>.yaml`. Example: `corrales-nm.yaml`.

## Schema

```yaml
locale:
  name: <City Name>            # display name
  state: <2-letter>            # e.g. NM
  metro: <metro area>          # nearest metro the locale draws from
  last_full_review: <YYYY-MM-DD>   # date the whole sheet was last walked through

# Live-music venues. Only include rooms that currently book original music.
venues:
  - name: <string>
    type: bar | brewery | listening_room | concert_hall | open_mic | event_space
    address: <string>          # full street address
    city: <string>
    drive_minutes_from_locale: <int>
    capacity: <int|null>
    books_original_music: yes | no | sometimes
    booking_contact: <email|null>
    notes: <string>            # one-sentence reality check
    source_url: <url>
    verified_on: <YYYY-MM-DD>

# Recording studios within an hour's drive.
studios:
  - name: <string>
    address: <string>
    city: <string>
    drive_minutes_from_locale: <int>
    focus: music | post_production | mixed   # IMPORTANT: post-production rooms are not for tracking music
    notable_clients: [<string>, ...]
    rate_range: <string|null>
    source_url: <url>
    verified_on: <YYYY-MM-DD>

# Annual events worth pitching.
festivals:
  - name: <string>
    when: <month or season>
    location: <string>
    paid_slots: yes | no | unknown
    source_url: <url>
    verified_on: <YYYY-MM-DD>

# Standalone scene claims (history, regional sound, demographics, etc.). Each
# claim is a sentence-level fact the writer is free to paraphrase but not extend.
scene_facts:
  - claim: <string>
    source_url: <url>
    verified_on: <YYYY-MM-DD>

# Things the writer must NOT mention because they were once on the sheet but are
# no longer accurate. Keeps stale knowledge from sneaking back in.
do_not_mention:
  - name: <string>
    reason: <string>           # closed, sold, never existed, etc.
    verified_on: <YYYY-MM-DD>
```

## Rules for entries

1. **No claim without a `source_url` and a `verified_on` date.** If you can't
   find a current source, the entry doesn't go in.
2. **`verified_on` older than 12 months** = treat as stale. The guardrail will
   warn; refresh before next issue.
3. **Closures go in `do_not_mention`, not deleted.** That way the guardrail
   catches the writer if it tries to revive a dead venue from training data.
4. **Specifics over vibes.** "Sister Bar — 360 cap, books indie/rock, contact
   events@sisterthebar.com" beats "Sister Bar is a great venue."
5. **One claim per `scene_fact`.** Don't bundle. Each one needs its own source.

## How the writer uses it

`weeklyamp.research.locale_facts.build_writer_context(locale_slug)` loads the
YAML and returns a prompt fragment. The fragment is appended to the writer's
system prompt with a hard rule:

> You may reference ONLY the venues, studios, festivals, and facts listed above.
> If a section requires an entity that is not on this list, write the section
> without naming a specific entity, or omit the section.

After generation, `weeklyamp.research.locale_facts.audit_draft(html, locale_slug)`
extracts proper-noun candidates from the draft and reports any that don't match
an entry on the sheet or appear in `do_not_mention`. Output is editor-facing,
not auto-blocking — a human approves before send.

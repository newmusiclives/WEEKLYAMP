"""Generate the Venue Edition sample issue — Sandia Bar, Corrales NM.

Hand-built rather than agent-generated, and deliberately so: every factual
claim here traces to a source listed under the section that makes it. The
one thing a venue-trade newsletter cannot do is invent a capacity, a pay
rate, or a quote from a named operator, and a demo that fabricates those
teaches the wrong lesson about what the pipeline is allowed to produce.

The underlying entity is on the Corrales fact sheet
(``data/locales/corrales-nm.yaml``), so ``audit_draft`` recognises it.

Run:  python3 generate_venue_sample.py
Out:  demo_venue_sandia_bar.html
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from weeklyamp.delivery.templates import render_newsletter, render_section  # noqa: E402

# --- Sources, referenced by key from each section ---------------------
SRC = {
    "comment_sandia": {
        "title": "New ownership brings new life to the Sandia Bar (Sept 12, 2024)",
        "url": "https://corralescomment.com/2024/09/12/new-ownership-brings-new-life-to-the-sandia-bar/",
        "author": "The Corrales Comment",
    },
    "sandia_site": {
        "title": "Sandia Bar — official site (hours, address, live-music submission)",
        "url": "https://sandiabar.com/",
    },
    "sandia_submit": {
        "title": "Sandia Bar — Live Music Submission",
        "url": "https://sandiabar.com/live-music-submission/",
    },
    "visitabq": {
        "title": "Weekend Live Music at Sandia Bar — event listing",
        "url": "https://www.visitalbuquerque.org/event/weekend-live-music-at-sandia-bar/64066/",
        "author": "Visit Albuquerque / Today in ABQ",
    },
    "noise_2026": {
        "title": "The sound of silence: Corrales council takes next step in drafting noise ordinance (Apr 1, 2026)",
        "url": "https://corralescomment.com/2026/04/01/the-sound-of-silence-corrales-council-takes-next-step-in-drafting-noise-ordinance/",
        "author": "The Corrales Comment",
    },
    "noise_input": {
        "title": "Corrales seeks public input on noise ordinance revision (Jul 21, 2025)",
        "url": "https://corralescomment.com/2025/07/21/corrales-seeks-public-input-on-noise-ordinance-revision/",
        "author": "The Corrales Comment",
    },
    "noise_abuzz": {
        "title": "All abuzz about noise (Jul 31, 2025)",
        "url": "https://corralescomment.com/2025/07/31/all-abuzz-about-noise/",
        "author": "The Corrales Comment",
    },
    "noise_loud": {
        "title": "How loud is too loud? (Jun 24, 2025)",
        "url": "https://corralescomment.com/2025/06/24/how-loud-is-too-loud/",
        "author": "The Corrales Comment",
    },
}


def s(*keys):
    return [SRC[k] for k in keys]


INTRO = """<p>Corrales, New Mexico has about 8,500 people, one main road, and an
argument about amplified music that has now outlasted two mayors. It is also where
a 1948 bar reopened with a new patio and a rooftop — which is to say, it is a very
small place doing a very ordinary thing that puts it squarely in the middle of the
hardest question in this trade: how loud are you allowed to be, and who decides?</p>

<p>This issue is a working file on <strong>the Sandia Bar</strong>, 4445 Corrales Rd.
Not a review. If you run a room in a village that likes its quiet, the useful part
is not whether the drinks are good — it is the sequence of decisions the operators
have made, and the one regulatory question still hanging over all of them.</p>

<p><em>Everything below is sourced. Where we could not verify something, we say so
rather than filling the gap — the last section is nothing but gaps.</em></p>"""

SECTIONS = [
    dict(
        display_name="VENUE SPOTLIGHT",
        headline="A 1948 room, nearly doubled — and what that buys you",
        byline="Bridget Lyle, Venue Edition",
        sources=s("comment_sandia", "sandia_site"),
        content_html="""<p>The Sandia Bar was established in <strong>1948</strong>. The
Chavez family ran it continuously until <strong>2018</strong>; Steve Chavez was the last
family operator, and the bar changed hands following his death. <strong>Lane McIntyre</strong>
is general manager under the new ownership.</p>

<p>The renovation is the part worth studying. Per the <em>Corrales Comment</em>, the work
<strong>nearly doubled the interior square footage</strong>, added a <strong>patio and a
rooftop area</strong>, and converted the family's former private area into public space.
The adobe walls stayed, with <em>truth windows</em> cut to expose the original materials,
and the vintage Budweiser and Schlitz signs stayed on the wall. Pool tables and a jukebox
are operational.</p>

<p>Read that as a set of trade-offs rather than a decor story:</p>

<ul>
<li><strong>Doubling the interior</strong> raises your fixed nut — staffing, HVAC,
insurance — before it sells a single extra pint. It also raises what a slow Tuesday
costs you.</li>
<li><strong>Adding a patio and a rooftop</strong> buys the highest-margin square footage
in the business. It is also the square footage that makes you audible to your neighbours,
and it is seasonal in a way an indoor room is not.</li>
<li><strong>Keeping the adobe and the old signage</strong> is not sentiment. In a village
that has fought development for decades, visible continuity with 1948 is political capital
you will want when you go to the council.</li>
</ul>

<p>The house cocktails are named <em>The Wagner</em>, <em>Corrales Cowboy</em>, and
<em>Bosque Stroll</em> — all three named for the immediate geography, which is the same
strategy as the truth windows, applied to the menu.</p>

<p>Current published hours: <strong>bar</strong> Sun–Tues 11a–10p, Wed–Thur 11a–11p,
Fri–Sat 11a–12a. <strong>Restaurant</strong> Sun–Thur 11a–9p, Fri–Sat 11a–10p. Phone
(505) 835-5983.</p>""",
    ),
    dict(
        display_name="HOUSE RULES",
        headline="Corrales still has no new noise ordinance — and that is the exposure",
        byline="Cole Rutherford, Venue Edition",
        sources=s("noise_2026", "noise_input", "noise_abuzz", "noise_loud"),
        content_html="""<p>If you operate outdoor entertainment in Corrales, you are
currently operating under a rule the village's own attorney has said may not hold up.</p>

<p>The existing ordinance prohibits &ldquo;excessive or unusually loud noise&rdquo; — and
Village Attorney <strong>Randy Autio</strong> has said it &ldquo;may not be enforceable
because of that vagueness.&rdquo; That cuts both ways. It means enforcement against you is
shaky. It also means you have <em>no safe harbour</em>: there is no decibel number you can
hit and point to.</p>

<p>The debate through 2025 was about what replaces it. At the July 2025 work study:</p>

<blockquote><p>&ldquo;If those folks at that first table can't talk, then it's too
loud.&rdquo;<br><em>— Dan O'Brien, Casa Vieja</em></p></blockquote>

<blockquote><p>&ldquo;We could talk about a solo guitarist on a very small amp, playing
something that barely is audible across the patio.&rdquo;<br><em>— Joel Gregory, Ex Novo
Brewing Co.</em></p></blockquote>

<blockquote><p>&ldquo;We were a partying town, but we partied indoors.&rdquo;<br><em>—
Tessa Davidson, Corrales Resident Noise Committee</em></p></blockquote>

<p>Councilor <strong>Zachary Burkett</strong> summarised the problem: &ldquo;I think right
now it's very subjective, and it's created a lot of problems.&rdquo; Davidson's counter to
a decibel standard is worth noting if you are lobbying for one — she warned that
&ldquo;decibel levels are a deterrent to noise that you may have to enforce pretty strongly
at the beginning.&rdquo;</p>

<p><strong>Where it actually stands (April 2026):</strong> no new ordinance. Mayor
<strong>Fred Hashimoto</strong> said it will be &ldquo;at least a few months.&rdquo; The
village contracted sound engineer <strong>Joshua Leasure of Colorado Analytics</strong>,
through Complete Safety Supply, to make recommendations. Village Administrator
<strong>Melanie Romero</strong>: &ldquo;They will be sending us some recommendations
sometime in the coming weeks, but we don't have a definite date.&rdquo; After that it goes
to the village attorney, planning and zoning, and code enforcement before public input and
council approval.</p>

<p><strong>What an operator should do with that:</strong> a consultant-drafted, engineer-backed
ordinance is far more likely to arrive as a measurable standard than as a vibe test. If you
run outdoor music in Corrales, the cheap move now is to <em>measure your own property line
yourself</em> — Saturday afternoon, at the fence, with a calibrated meter — so that when a
number lands you already know whether you clear it. Finding out during enforcement is the
expensive version.</p>

<p class="note"><strong>Unconfirmed, flagged deliberately:</strong> a 2024 draft amendment
reportedly proposed exempting commercial establishments along Corrales Road
<em>between Meadowlark Lane and Wagner Lane</em>, 8 a.m.–9 p.m. Sunday–Thursday and
8 a.m.–10 p.m. Friday–Saturday. We could not confirm those boundaries in the primary
reporting we were able to read, that draft was <strong>not</strong> adopted, and we could
not verify whether 4445 Corrales Rd falls inside them. Treat it as context, not
protection.</p>""",
    ),
    dict(
        display_name="THE DOOR",
        headline="A free 2–5pm weekend slot is a bar-spend bet, not a ticket bet",
        byline="Sal Marchetti, Venue Edition",
        sources=s("visitabq", "sandia_site"),
        content_html="""<p>Sandia Bar's published live music is
<strong>Saturdays and Sundays, 2–5pm, free, on the patio</strong>, listed as a
family-friendly daytime slot with a full bar.</p>

<p>Four things follow from that structure, and they are worth stating plainly because a lot
of operators pick this format by accident rather than on purpose.</p>

<p><strong>1. There is no door revenue, so the music is a cost line, not a revenue line.</strong>
It has to be justified entirely by incremental bar and kitchen spend against the same hours
without music. That is a measurable thing — same weekday, music weeks against non-music
weeks — and if you are not measuring it you are guessing.</p>

<p><strong>2. Free-and-daytime buys you the widest possible audience and the lowest
possible spend-per-head.</strong> Families come. Families order one round and a basket of
something. Your revenue per head at 3pm will not look like your revenue per head at 10pm,
and it is a mistake to hold the afternoon slot to the evening's numbers.</p>

<p><strong>3. It is the lowest-risk slot you have with the neighbours.</strong> In a village
mid-way through rewriting its noise rules, a 2–5pm finish is the single most defensible
programming decision available. You are done before dinner. Nobody is drafting a complaint
about a 4pm guitar. Whatever ordinance lands, an afternoon slot is the one most likely to
survive it intact.</p>

<p><strong>4. No cover means no guarantee of the artist's income</strong> — which makes the
pay structure the artist's first question and the one thing the public listing does not
answer. See the next section.</p>

<p>We have not published a revenue model for this room because <strong>Sandia Bar's
capacity, covers, and spend-per-head are not public</strong> and we will not invent them.
If you run a comparable room, the arithmetic above is the frame; your own POS data is the
only honest input.</p>""",
    ),
    dict(
        display_name="BOOKING DESK",
        headline="The booking channel is a web form — here's what to ask before you fill it in",
        byline="Marisol Vega, Venue Edition",
        sources=s("sandia_submit", "sandia_site", "comment_sandia"),
        content_html="""<p>Sandia Bar takes artist pitches through a form on its own site —
the nav item reads <em>&ldquo;Play Music at Sandia Bar?&rdquo;</em> and points at
<code>sandiabar.com/live-music-submission/</code>. There is no named talent buyer published,
and no public booking email.</p>

<p><strong>That is a genuinely common setup and it is not a red flag.</strong> A form filters
volume for a room without a full-time buyer. But it does mean the terms are not published,
and the terms are the whole negotiation. The site does not state pay structure, set length,
whether a PA is provided, backline, load-in time, or how far ahead the calendar is built.</p>

<p>So the pitch email — or the form's notes field — should be the one that makes those
questions easy to answer. For a free daytime patio slot, the five that matter:</p>

<ol>
<li><strong>How is the artist paid?</strong> Flat fee, percentage of bar over a baseline, or
tips only. All three are legitimate for a no-cover afternoon; only one of them is a surprise
after the fact.</li>
<li><strong>Is there a house PA, and who runs it?</strong> An outdoor patio slot with no
house system means you are carrying everything, and it changes what the fee has to cover.</li>
<li><strong>Set length and format.</strong> Three hours is a long afternoon. One act for
2–5pm is a very different ask from two 75-minute sets.</li>
<li><strong>How far out is the calendar?</strong> Determines whether this is a routing option
or a standing local gig.</li>
<li><strong>Is it year-round?</strong> The 2024 reporting said live music was planned
&ldquo;likely on a seasonal basis, depending on local regulations&rdquo; — and the regulations
are still unsettled. Worth asking directly.</li>
</ol>

<p><strong>For operators reading this from the other side of the form:</strong> publishing
even three of those five on the submission page would cut your unusable-pitch volume
sharply. Artists self-select out when the terms are visible. The rooms that publish terms
get fewer pitches and better ones.</p>""",
    ),
    dict(
        display_name="BAR & BOARD",
        headline="The kitchen landed — and the hours moved with it",
        byline="Sal Marchetti, Venue Edition",
        sources=s("comment_sandia", "sandia_site"),
        content_html="""<p>A small timeline that tells you something about sequencing.</p>

<p>In <strong>September 2024</strong>, at reopening, the kitchen was still under construction,
targeting the end of that year. In the meantime the bar ran on <strong>food trucks</strong> —
Wanna Taco Bout Burgers and BigBoss HotLinks, on a rotating schedule.</p>

<p>As of <strong>August 2026</strong> the site publishes distinct restaurant hours — Sun–Thur
11a–9p, Fri–Sat 11a–10p — separate from bar hours. The kitchen is running.</p>

<p>The opening hours also moved. The 2024 reporting listed <strong>Monday–Tuesday 2–10 p.m.</strong>
Today the site lists <strong>Sun–Tues 11a–10p</strong>. Early-week open moved from 2pm to 11am
— which is what happens when you have a kitchen to amortise. A bar opens when drinkers arrive;
a kitchen opens for lunch because it has to.</p>

<p><strong>The food-truck bridge is the transferable idea.</strong> It let the room open, build
a habit, and trade for a year without waiting on a hood, a grease trap, and an inspection. The
risk is that you train your customers to expect the truck; the mitigation is that you take the
food revenue in-house the moment the kitchen is legal, which is what appears to have
happened here.</p>""",
    ),
    dict(
        display_name="THE NEIGHBOURHOOD",
        headline="Your parking overflow and your volume are the same conversation",
        byline="Tam Okonjo, Venue Edition",
        sources=s("sandia_site", "noise_loud", "noise_abuzz"),
        content_html="""<p>Sandia Bar's own site notes that its parking lot fills frequently
and directs overflow to <strong>Village of Corrales public parking areas</strong>.</p>

<p>Put that next to the noise file and you have the complete picture of what a village
actually experiences when a room gets busy. Corrales resident <strong>Sabine Shurter</strong>
reported measuring <strong>65 decibels at her home for several hours some nights, sometimes as
high as 76</strong>. Tessa Davidson's line — &ldquo;We were a partying town, but we partied
indoors&rdquo; — is not anti-business. It is a precise description of what changed: the
activity did not arrive, it moved outside.</p>

<p>Parking overflow and amplified sound are the same complaint wearing two hats. Both are
your success becoming your neighbour's Saturday. And both get raised at the same council
meeting, usually by the same people.</p>

<p><strong>The practical read:</strong> a room that has already routed its overflow to
designated public parking has done the visible, documentable thing — it has an answer when
asked. The equivalent move on sound is a written volume policy and a property-line
measurement you took yourself. Mayor Jim Fahey, during the 2025 debate, said of the venues:
&ldquo;We want them to be able to survive.&rdquo; That is a real opening. Operators who show
up to the process with data get written into the exemption; operators who show up after
enforcement get written out of it.</p>""",
    ),
    dict(
        display_name="WHAT WE COULD NOT VERIFY",
        headline="The gaps, stated rather than filled",
        byline="Roz Whitaker, Editor",
        sources=s("sandia_site"),
        content_html="""<p>A venue newsletter that invents a capacity is worse than useless.
Here is everything we wanted for this issue and could not confirm from a source we could
read:</p>

<ul>
<li><strong>Capacity</strong> — indoor, patio, or rooftop. Not published anywhere we found.</li>
<li><strong>PA, backline, and who engineers the patio slot.</strong> Not stated.</li>
<li><strong>Artist pay structure</strong> for the weekend afternoon slot. Not stated.</li>
<li><strong>Whether live music runs year-round.</strong> The 2024 reporting said
&ldquo;likely on a seasonal basis, depending on local regulations&rdquo;; the current listing
shows a recurring weekly slot with no end date. These may both be true. We did not confirm
which.</li>
<li><strong>Current and upcoming performers.</strong> The venue's Facebook and Instagram are
the live calendar; neither was machine-readable for us, and we will not summarise a lineup
we have not seen.</li>
<li><strong>The names of the current owners.</strong> The Sept 2024 reporting names the general
manager but not the ownership group.</li>
<li><strong>Whether 4445 Corrales Rd sits inside the boundaries</strong> of the 2024 proposed
commercial exemption. Unconfirmed, and the draft was not adopted regardless.</li>
</ul>

<p>If you work at the room and want any of the above corrected or filled in, reply to this
email — corrections run in the next issue with attribution.</p>""",
    ),
]

PS = ("Every one of these villages has the same fight, and it is never really about "
      "decibels. It is about whether the place you love staying the place you love "
      "requires it to stop changing. A 1948 bar with a new rooftop is the whole argument "
      "in one building. I don't think there's a clean answer — but I notice the rooms "
      "that survive it are the ones that showed up to the meeting with a number instead "
      "of a grievance. — PS")


def main():
    rendered = [
        {"html": render_section(
            display_name=sec["display_name"],
            content_html=sec["content_html"],
            headline=sec["headline"],
            byline=sec["byline"],
            sources=sec["sources"],
        )}
        for sec in SECTIONS
    ]

    html = render_newsletter(
        newsletter_name="TrueFans DISPATCH",
        tagline="Everything that happens before the doors open",
        issue_number=1,
        title="Sandia Bar, Corrales NM — a 1948 room and an unfinished ordinance",
        sections=rendered,
        intro_copy=INTRO,
        ps_closing=PS,
        edition_slug="venue",
        issue_date="Monday, August 12, 2026",
        preheader_text="A 1948 Corrales bar reopened with a rooftop. The village still "
                       "hasn't finished its noise ordinance. Both facts matter.",
    )

    out = os.path.join(os.path.dirname(__file__), "demo_venue_sandia_bar.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"Wrote {out} ({len(html):,} bytes, {len(SECTIONS)} sections)")


if __name__ == "__main__":
    main()

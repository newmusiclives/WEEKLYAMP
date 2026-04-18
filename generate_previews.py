"""Generate sample newsletter previews for all 3 editions."""
import webbrowser, tempfile, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from weeklyamp.delivery.templates import render_section, render_newsletter

# --- FAN EDITION ---

fan_intro = """<p>Happy Friday, music lovers! 🎵</p>

<p>This week we're going deep — from a legendary studio session that almost didn't happen, to the album that refuses to age, to the hidden architecture inside one of last year's biggest tracks. We've also got a jaw-dropping vinyl collection story from Tokyo and five albums that permanently rewired how R&B sounds.</p>

<p>Grab your headphones, settle in, and let's get into it. As always, if something in this issue moves you, hit reply and tell us about it — we read every single response.</p>"""

fan_sections = [
    ("Backstage Pass", "The Night Prince Rewrote 'Purple Rain' in a Single Take", """<p>In a candid 1999 interview that only resurfaced last month, Prince's longtime engineer Susan Rogers revealed the full story behind one of rock's most iconic moments — and it's wilder than anyone imagined.</p>

<p>The band had been at First Avenue in Minneapolis for nearly six hours, running through the setlist for what would become the <em>Purple Rain</em> tour. By midnight, everyone was exhausted. The horn section had gone home. Wendy Melvoin was ready to pack up her guitar. But Prince, as he often did, had other plans.</p>

<p>"He walked over to me and said, 'Keep the tape rolling, no matter what happens,'" Rogers recalled. "I'd heard that before, but something in his voice was different that night. There was an urgency."</p>

<p>What followed was a complete reimagining of the song's guitar solo. Prince abandoned the structured arrangement they'd been rehearsing for weeks and launched into a sprawling, improvisational passage that drew from jazz, blues, and something Rogers described as "pure emotional transmission."</p>

<p><strong>The first take was the only take.</strong> When Prince finished — nearly eight minutes later — he set his guitar down, looked at Rogers through the control room glass, and simply nodded. That nod meant: <em>that's the one</em>.</p>

<p>Rogers kept every second of it. The solo that appears on the final album is that exact performance, unedited and unpolished. No punch-ins, no comps, no studio trickery. "I've worked with dozens of artists since then," Rogers said. "Nobody else could do what he did that night. It wasn't practice or preparation — it was channeling."</p>

<p>The session tape from that evening has never been officially released, though bootleg collectors have long speculated about its existence. Rogers confirmed it's in the Prince Estate vault, and she hopes it sees the light of day eventually. "The world deserves to hear the full eight minutes," she said. "What made the album was extraordinary. What was left on the floor was transcendent."</p>"""),

    ("Vinyl Vault", "Rumours at 50: Why Fleetwood Mac's Masterpiece Still Resonates", """<p>Half a century ago this month, Fleetwood Mac released an album born from heartbreak, betrayal, cocaine, and sheer creative stubbornness. <em>Rumours</em> went on to sell over 40 million copies worldwide, making it one of the best-selling albums in history. But the truly remarkable thing isn't the sales — it's that the album keeps finding new audiences.</p>

<p>Streaming data tells the story. In 2025, <em>Rumours</em> was streamed over 2.1 billion times across platforms — a 34% increase from just three years earlier. On TikTok, "Dreams" alone has been used in over 4.7 million videos. The album isn't just surviving; it's thriving in an era it was never designed for.</p>

<p><strong>So what's the secret?</strong></p>

<p>Music psychologist Dr. Elena Marchetti at Berklee points to the album's "emotional transparency" as the key factor. "These are songs written by people who were actively destroying each other's lives and processing that destruction in real time," she explains. "There's no filter, no curation, no brand management. Gen Z listeners, who've grown up in a world of carefully managed personas, find that rawness magnetic."</p>

<p>Consider "Go Your Own Way," written by Lindsey Buckingham as a bitter farewell to Stevie Nicks — his bandmate, his ex-lover, and the person he'd have to face in the studio the very next morning. Or "The Chain," the only song credited to all five members, assembled from fragments recorded during sessions so tense that band members would schedule studio time to avoid seeing each other.</p>

<p>Producer Ken Caillat, who co-produced the album with Richard Dashut, has spoken extensively about the surreal atmosphere. "You'd have Christine McVie recording a vocal about her divorce from John McVie, and John would be in the next room playing bass on a different track about Stevie's affair with Mick. Everyone knew. Nobody talked about it. The music said everything."</p>

<p>The production itself was revolutionary for its time — layers of acoustic guitars, meticulous vocal harmonies, and a warmth that analog purists still hold up as a gold standard. But it's the human mess underneath the polish that gives <em>Rumours</em> its enduring power. Perfection is admirable. Perfection built on a foundation of chaos? That's art.</p>"""),

    ("Lyrics Unpacked", "Decoding Kendrick Lamar's Hidden Architecture in 'Not Like Us'", """<p>When Kendrick Lamar released "Not Like Us," most listeners heard a devastating diss track — a surgical strike in a battle that dominated hip-hop conversation for months. But a closer textual analysis reveals something far more ambitious: a multi-layered linguistic construction that functions simultaneously as personal attack, cultural commentary, and geographic autobiography.</p>

<p>Let's start with the bridge section, which contains at least three distinct layers of meaning operating at once.</p>

<p><strong>Layer one: the literal.</strong> On the surface, Kendrick is addressing his rival directly, cataloguing grievances with the precision of a prosecutor's closing argument. The rhyme scheme shifts from couplets to a more complex interlocking pattern — ABAB gives way to ABCABC — mirroring the escalation of his accusations.</p>

<p><strong>Layer two: the geographic.</strong> Embedded throughout the bridge are references to specific Compton landmarks — street names, intersections, and neighborhood boundaries that function as a kind of encrypted autobiography. "The turn on Rosecrans" isn't just a line; it's a reference to the intersection where Kendrick's father used to sell, a detail he's alluded to in interviews but never before put in a song. For Compton natives, these references transform the track into a walking tour of Kendrick's origin story.</p>

<p><strong>Layer three: the musical.</strong> Producer DJ Mustard built the instrumental around samples that themselves contain layers of West Coast history. The bass pattern interpolates a 1970s Parliament groove, while the hi-hat pattern nods to DJ Quik's early production style. Kendrick's flow rides on top of these historical references, creating a conversation across decades of Black Los Angeles music.</p>

<p>Dr. Marcus Thompson, a linguistics professor at UCLA who specializes in hip-hop discourse analysis, called the track "a masterclass in what I call 'compressed narrative' — the ability to tell multiple stories simultaneously using the same words." He points out that Kendrick employs a technique common in West African griot traditions, where a single phrase can carry personal, communal, and spiritual meaning depending on the listener's context.</p>

<p>This is what separates great rap from good rap. A good rapper writes clever lines. A great rapper builds architecture.</p>"""),

    ("Fan Spotlight", "How a Vinyl Collector in Tokyo Built the World's Largest Soul Archive", """<p>Yuki Tanaka's apartment in Shibuya doesn't look like much from the outside — a modest two-bedroom in a postwar building tucked behind a ramen shop on a side street most tourists never find. But step inside and you're standing in what multiple experts have called the most significant private collection of soul and funk records on the planet.</p>

<p>Over 40,000 records line custom-built shelving that covers every wall from floor to ceiling. The collection includes signed pressings from Stevie Wonder, first editions of every Motown release from 1961 to 1975, and a near-complete archive of obscure regional soul labels from the American South — many of which pressed fewer than 500 copies.</p>

<p><strong>How did a salaryman from Yokohama end up with all of this?</strong></p>

<p>"It started with one record," Tanaka told us over green tea in his listening room — a converted bedroom with acoustic panels and a vintage Thorens turntable. "I was 19, studying English in Chicago, and I walked into a thrift store on the South Side. There was a stack of 45s for ten cents each. I bought one by a group called The Radiants — 'Voice Your Choice' on Chess Records. I played it on my host family's turntable that night and I understood, for the first time, what music could do to a human body."</p>

<p>That was 1987. Over the next four decades, Tanaka built his collection methodically, traveling to the United States two or three times a year to attend record fairs, estate sales, and — increasingly — to buy entire collections from aging DJs and radio station archives. He estimates he's spent the equivalent of roughly $800,000 on records, though the collection's current market value is likely many times that.</p>

<p>His online catalog, painstakingly digitized and cross-referenced with Discogs and the Library of Congress, has become an essential reference for DJs, producers, and musicologists worldwide. Questlove has cited it as "the most important private archive of Black American music outside the Smithsonian." Producers including Kaytranada, Madlib, and the late J Dilla have all sourced samples through Tanaka's database.</p>

<p>"I don't think of myself as a collector," Tanaka says. "I think of myself as a librarian. These records are documents of human expression. My job is to make sure they survive and that people can find them."</p>"""),

    ("The Listening Room", "Five Albums That Permanently Rewired How R&B Sounds", """<p>Every genre has its inflection points — records that didn't just push boundaries but redrew the entire map. In R&B, the shift from the polished Babyface era to what we hear today didn't happen gradually. It happened in sharp, disruptive bursts, each driven by a single album that changed what producers, singers, and listeners thought was possible.</p>

<p>Here are five records that bent the genre into new shapes — and why they still matter.</p>

<p><strong>1. D'Angelo — <em>Voodoo</em> (2000)</strong></p>
<p>Before <em>Voodoo</em>, R&B production was largely quantized — everything locked to a grid, every beat precisely placed. D'Angelo and drummer Questlove deliberately played behind the beat, creating a loose, organic feel that sounded like nothing else on radio. The album sold modestly on release but became the blueprint for nearly every "alternative R&B" artist who followed. Without <em>Voodoo</em>, there's no Frank Ocean, no SZA, no Daniel Caesar.</p>

<p><strong>2. Erykah Badu — <em>Mama's Gun</em> (2000)</strong></p>
<p>Released the same year as <em>Voodoo</em> (and deeply interconnected with it — Badu and D'Angelo were both part of the Soulquarians collective), <em>Mama's Gun</em> proved that neo-soul wasn't a fad. Badu's songwriting merged jazz harmony with hip-hop attitude and a lyrical depth that treated R&B as a vehicle for ideas, not just romance. "Didn't Cha Know" alone contains more harmonic sophistication than most entire albums.</p>

<p><strong>3. The Weeknd — <em>House of Balloons</em> (2011)</strong></p>
<p>Abel Tesfaye's debut mixtape did something radical: it made R&B genuinely dark. Not moody, not brooding — <em>dark</em>. The production, helmed by Illangelo and Doc McKinney, chopped and screwed indie rock samples into something narcotic and disorienting. It opened a lane for an entire generation of artists who wanted to explore the genre's shadow side — the loneliness, the substance abuse, the 4 AM emotional wreckage that polished R&B had always glossed over.</p>

<p><strong>4. Frank Ocean — <em>Blonde</em> (2016)</strong></p>
<p>If <em>Channel Orange</em> announced Frank Ocean as a generational talent, <em>Blonde</em> proved he was something rarer: an artist willing to dismantle his own formula. The album strips R&B to its emotional skeleton — sparse production, fragmented structures, vocals that float between singing and speaking. It redefined what an R&B "song" could be, proving that a whispered confession over ambient guitar could hit harder than any stadium-ready chorus.</p>

<p><strong>5. SZA — <em>Ctrl</em> (2017)</strong></p>
<p>SZA's debut did something none of its predecessors quite managed: it made experimental R&B <em>popular</em>. <em>Ctrl</em> went platinum multiple times, spent years on the Billboard 200, and proved that audiences were ready for R&B that was vulnerable, unpolished, and defiantly personal. The album's influence is everywhere now — in the confessional songwriting, the lo-fi production textures, and the refusal to present a "perfect" version of womanhood that defines contemporary R&B.</p>"""),
]

# --- ARTIST EDITION ---

artist_intro = """<p>Happy Friday, creators! 🎸</p>

<p>Welcome back to the Artist Edition. This week we're bringing you the goods — a vocal warm-up routine straight from Nashville's top touring coaches, a chord progression breakdown that explains why every ballad on the charts sounds so good right now, and a gear review that might save you thousands on your next mic purchase.</p>

<p>We've also got a deep dive into why the traditional album rollout is dead for independent artists (and what's actually working instead), plus a masterclass in mixing vocals using nothing but the stock plugins already sitting in your DAW. No excuses this week — let's level up.</p>"""

artist_sections = [
    ("Coaching Corner", "Three Vocal Warm-Ups That Professional Touring Singers Swear By", """<p>If you've ever wondered why professional singers can perform 90-minute sets night after night without losing their voice, the answer isn't talent — it's preparation. Specifically, it's the 10-15 minutes they spend warming up before every single performance.</p>

<p>Nashville vocal coach Dr. Sarah Mitchell has worked with over 200 touring artists across country, pop, and rock. She shared her exact pre-show warm-up routine with us — the same one she prescribes to artists playing arenas and stadiums.</p>

<p><strong>Exercise 1: The Lip Trill Cascade (3 minutes)</strong></p>
<p>Start with a relaxed lip trill (think of blowing a raspberry) on a comfortable mid-range note. Slowly slide up a fifth, then back down. Repeat, extending the range by a half step each time. "The lip trill is the single most efficient warm-up exercise that exists," Dr. Mitchell explains. "It engages the diaphragm, warms the vocal folds without strain, and establishes breath support — all simultaneously. I've never met a professional singer who doesn't do some version of this."</p>

<p><strong>Exercise 2: The Straw Phonation Series (4 minutes)</strong></p>
<p>Using a narrow cocktail straw, hum through your range while blowing air through the straw into a glass of water. The resistance created by the water provides "back pressure" that gently stretches and warms the vocal folds. Start with sustained notes, then move to gentle scales. "This technique was developed by voice scientists in Finland," says Dr. Mitchell. "It's the closest thing we have to a magic bullet for vocal health. It reduces collision force between the vocal folds by up to 40% while still engaging the full mechanism."</p>

<p><strong>Exercise 3: The Resonance Placement Drill (5 minutes)</strong></p>
<p>Alternate between "ng" (as in "sing"), "nee," and "noh" sounds on a five-note descending scale, focusing on feeling the vibration shift location — from the nasal passages on "ng" to the hard palate on "nee" to the soft palate on "noh." "This exercise teaches your brain where to 'aim' the sound," Dr. Mitchell says. "Most vocal fatigue isn't caused by the vocal folds themselves — it's caused by inefficient resonance placement. When you place the sound correctly, the voice carries further with less effort."</p>

<p>Dr. Mitchell emphasizes that consistency matters more than duration. "Twelve minutes every single day will do more for your voice than an hour once a week. The vocal folds are muscles. They respond to routine."</p>

<p><strong>Bonus tip:</strong> Never warm up with cold water. Room temperature water or warm tea (no milk, no honey — both create mucus) is ideal. And if you're performing in a dry climate or air-conditioned venue, steam inhalation for 5 minutes before your warm-up can make a dramatic difference.</p>"""),

    ("Songcraft", "The Unexpected Chord Progression Hiding Inside Every Hit Ballad This Year", """<p>If you've listened to the radio in the past six months and thought, "Why do all these ballads feel the same?" — you're not imagining things. A music theory analysis of the Billboard Hot 100's top ballads reveals a striking pattern that goes deeper than just verse-chorus structure.</p>

<p>Of the ten highest-charting ballads in the past two quarters, seven share a nearly identical harmonic foundation: a modified vi-IV-I-V progression with a borrowed chord from the parallel minor. In practice, this usually means Am-F-C-G in the key of C, but with the IV chord occasionally swapped for a iv (Fm) — a minor four chord borrowed from C minor.</p>

<p><strong>Why does this work so well?</strong></p>

<p>The standard vi-IV-I-V is already one of the most emotionally effective progressions in pop music — it's the foundation of everything from "Someone Like You" to "Let It Be." But that borrowed minor IV adds something crucial: a moment of unexpected darkness in an otherwise bright progression. It creates what music theorists call "modal mixture" — a brief harmonic shadow that makes the listener's ear perk up without quite knowing why.</p>

<p>"It's the musical equivalent of a cloud passing over the sun," explains Dr. James Chen, who teaches advanced harmony at Berklee. "The major IV chord feels hopeful. The minor IV feels bittersweet. When you alternate between them across verses and choruses, you create an emotional arc within the harmony itself — hope and melancholy in conversation."</p>

<p><strong>How to use this in your own writing:</strong></p>
<p>Try writing your verse with the standard vi-IV-I-V, then switch to vi-iv-I-V for the chorus (or vice versa). The single chord change — major IV to minor IV — transforms the emotional color of the entire section. You can also try placing the borrowed chord only in the final chorus for a climactic emotional shift.</p>

<p>For a more advanced variation, try moving the borrowed chord to the second half of the bar, creating a IV-iv motion within a single measure. This chromatic descent (F to Fm in our example) produces a sinking feeling that's particularly effective under vulnerable lyrics.</p>

<p>The takeaway isn't that you should copy this progression note for note — it's that a single borrowed chord can transform a familiar progression into something that feels fresh and emotionally complex. Sometimes the difference between a good song and a great one is one unexpected note.</p>"""),

    ("Gear Garage", "The $200 Microphone That's Quietly Replacing $3,000 Studio Standards", """<p>Here's a sentence that would have gotten you laughed out of any recording studio five years ago: a $200 condenser microphone is delivering results that engineers are struggling to distinguish from a Neumann U87 in blind tests.</p>

<p>The Rode NT1 5th Generation, released in late 2024, has been quietly taking over project studios, home setups, and — increasingly — professional tracking rooms. And the spec sheet explains why.</p>

<p><strong>The numbers:</strong> The NT1 5th Gen boasts a self-noise figure of just 4dBA — making it the quietest studio condenser microphone ever manufactured. For context, the industry-standard Neumann U87 sits at 12dBA, and the previous NT1 (already considered quiet) measured 4.5dBA. In practical terms, this means you can record whispered vocals, delicate acoustic guitar, and ambient room sound without any audible noise floor.</p>

<p>The frequency response extends from 20Hz to 20kHz with a presence peak around 8-12kHz that engineers describe as "flattering without being hyped." Unlike many affordable condensers that boost the high end aggressively (resulting in brittle, harsh recordings), the NT1 5th Gen's top end is smooth and natural — closer to the expensive ribbon-like quality of high-end German and Austrian microphones.</p>

<p><strong>What engineers are saying:</strong></p>
<p>"I did an A/B test with my U87ai last month," says mixing engineer Carlos Rivera, whose credits include work with Grammy-nominated artists. "I recorded the same vocalist through both mics, same preamp, same room. When I played the files back for three other engineers without telling them which was which, they were split. Two preferred the Rode. That's never happened before with a mic at this price point."</p>

<p>The mic also includes both XLR and USB-C outputs — the first professional-grade condenser to offer genuine dual connectivity. The USB output runs at 24-bit/48kHz, making it immediately useful for podcasters, streamers, and artists who want to record quick ideas without booting up their full interface setup.</p>

<p><strong>What it won't do:</strong> The NT1 5th Gen is a large-diaphragm condenser with a fixed cardioid pattern. If you need figure-8 or omnidirectional pickup, you'll need to look elsewhere. It also lacks the subtle harmonic coloration that tube microphones provide — this is a clean, transparent mic, not a character mic. For vocals that need warmth and grit, you might still prefer something with a tube or transformer-coupled circuit.</p>

<p><strong>The bottom line:</strong> At $199, this microphone removes "I can't afford good gear" as an excuse for anyone serious about recording. The technology gap between affordable and premium studio equipment has been narrowing for years. With the NT1 5th Gen, it's essentially closed.</p>"""),

    ("Social Media Strategy", "Why the Traditional Album Rollout Is Dead for Independent Artists", """<p>If you're an independent artist planning to go quiet for six months, record an album, drop a single, release the album, and then tour — you're following a playbook designed for a world that no longer exists.</p>

<p>The traditional album rollout cycle was built for an industry where gatekeepers controlled distribution, radio determined exposure, and fans expected to wait. None of those conditions hold true anymore. The data confirms what many indie artists have already intuited: the old way doesn't just underperform — it actively sabotages independent careers.</p>

<p><strong>The numbers are stark.</strong> A study of 500 independent releases across 2024-2025, conducted by music analytics firm Chartmetric, found that artists who followed a traditional rollout pattern (silence → single → album → tour) saw an average streaming decline of 62% in the months between announcement and release. Why? Because algorithmic platforms punish absence. When you stop posting, the algorithm stops showing your content. When the algorithm stops showing your content, your audience's engagement drops. When engagement drops, the algorithm deprioritizes you further. It's a death spiral.</p>

<p><strong>What's actually working:</strong></p>

<p>The artists seeing the strongest growth are those who've adopted what strategists call "continuous release" — a model where music, content, and audience engagement flow constantly rather than in campaigns. This doesn't mean releasing an album's worth of material every month. It means staying present, visible, and engaged between releases.</p>

<p>Concretely, that looks like: releasing singles every 4-6 weeks rather than saving them for an album; sharing works-in-progress, studio footage, and creative process content 3-5 times per week; treating every platform (TikTok, Instagram, YouTube Shorts) as a distinct audience with platform-native content; and building narrative arcs across posts rather than treating each one as isolated promotion.</p>

<p>Artist and strategist Maya Rodriguez, who grew from 2,000 to 180,000 followers in 14 months using this approach, puts it bluntly: "The album isn't the product anymore. <em>You</em> are the product. The album is a milestone in an ongoing relationship with your audience. If you disappear for six months to make it, you're breaking that relationship."</p>

<p><strong>The exception:</strong> If you already have a large, dedicated fanbase (100K+ engaged followers), you can afford strategic silence because anticipation works at scale. For everyone else — and that's most independent artists — visibility is survival.</p>"""),

    ("Production Tips", "Mixing Vocals Like a Pro Using Only the Stock Plugins in Your DAW", """<p>One of the most persistent myths in home recording is that you need expensive third-party plugins to get professional-sounding vocals. It's a myth that plugin companies are happy to perpetuate — and it's simply not true.</p>

<p>Grammy-winning mixing engineer Manny Marroquin, whose credits include Bruno Mars, Kendrick Lamar, and Rosalía, recently broke down his vocal processing chain into fundamental techniques that can be replicated with the stock plugins in Logic Pro, Ableton Live, or Pro Tools. Here's the approach.</p>

<p><strong>Step 1: Subtractive EQ (Stock EQ)</strong></p>
<p>Before you add anything, remove what doesn't belong. High-pass filter at 80-100Hz to eliminate rumble and proximity effect buildup. Then sweep a narrow boost through the 200-500Hz range to find any "boxy" or "muddy" frequencies — the ones that make a vocal sound like it was recorded in a closet (which, for home recordings, it probably was). Cut those by 2-4dB. "Most amateur mixes have too much 300Hz in the vocal," Marroquin says. "That's the single biggest difference between a home recording and a studio recording."</p>

<p><strong>Step 2: Compression in Series (2x Stock Compressor)</strong></p>
<p>Instead of using one compressor working hard, use two compressors working gently. The first should be a slow-attack, fast-release compressor (ratio 2:1, threshold set so it's catching 3-4dB of gain reduction on peaks). This controls the overall dynamics. The second should be faster — quick attack, medium release, same ratio — catching another 2-3dB. "Two compressors doing 3dB each sounds infinitely more natural than one compressor doing 6dB," Marroquin explains. "The vocal stays dynamic and alive instead of getting squashed."</p>

<p><strong>Step 3: Additive EQ (Stock EQ, after compression)</strong></p>
<p>Now add what's missing. A gentle shelf boost above 10kHz (2-3dB) adds "air" and presence. A small boost around 3-5kHz (1-2dB) helps the vocal cut through a dense mix. Be subtle here — it's easier to add too much top end than too little. "If the vocal sounds bright in solo but right in the mix, you've gone too far," Marroquin cautions.</p>

<p><strong>Step 4: De-essing (Stock De-esser or Multiband Compressor)</strong></p>
<p>After boosting the high end, sibilance ("s" and "t" sounds) will be more prominent. Use a de-esser targeting 5-8kHz, or set up a band of your stock multiband compressor to compress only that range. Start subtle and increase until the harshness is tamed without making the singer sound like they have a lisp.</p>

<p><strong>Step 5: Reverb and Delay (Stock Reverb + Delay)</strong></p>
<p>Send (not insert) the vocal to a short plate reverb (1.2-1.8 second decay) with the high end rolled off above 8kHz. This adds depth without washing out the vocal. Add a stereo delay set to 1/8 note with 2-3 repeats, mixed low — you should feel it more than hear it. "The reverb puts the vocal in a space. The delay gives it width," Marroquin says. "Together, they make a dry vocal sound like a record."</p>

<p>Total plugin count: 6 stock plugins. Total cost: $0. The quality gap between this chain and a $2,000 plugin bundle is — for most listeners and most mixes — functionally zero.</p>"""),
]

# --- INDUSTRY EDITION ---

industry_intro = """<p>Happy Friday, industry professionals.</p>

<p>Big moves this week. Universal Music Group just announced the most significant restructuring of its A&R operations in a decade — and the reason tells you everything about where the industry is headed. We've also got fresh data showing independent labels absolutely crushing it in sync licensing, a concerning new AI development from Google DeepMind, a breakdown of the congressional bill that could triple streaming royalties, and three major catalog deals that just reshaped the acquisition landscape.</p>

<p>If you're making decisions about where the music business is going, this is the issue you need to read carefully. Let's dive in.</p>"""

industry_sections = [
    ("Industry Pulse", "Universal Music Group Restructures Entire A&R Division Amid AI Shift", """<p>In the most significant organizational shakeup since the streaming transition, Universal Music Group announced Tuesday that it is merging its traditional A&R departments with newly formed "AI Discovery Units" across all three major labels — Republic, Interscope, and Capitol.</p>

<p>The restructuring, effective Q3 2026, will see approximately 40 traditional A&R roles consolidated into 25 hybrid positions that combine traditional talent scouting with AI-powered data analysis. Each major label within UMG will have a dedicated AI Discovery team reporting directly to the label head, alongside — not replacing — traditional A&R staff.</p>

<p><strong>What's actually changing:</strong></p>

<p>The new AI Discovery Units will use proprietary machine learning tools to analyze streaming patterns, social media engagement velocity, and what UMG internally calls "cultural momentum signals" — early indicators that an unsigned artist is gaining organic traction before they appear on traditional radar. These tools have been in development at UMG's Santa Monica innovation lab for 18 months and were quietly tested across Scandinavian and Southeast Asian markets in 2025.</p>

<p>"We signed three artists through the AI discovery pipeline in Sweden last year," said Marcus Lindgren, who led the pilot program. "Two of them were generating meaningful streaming numbers within six months. Under the traditional model, we would have found them eventually — but 'eventually' in this business can mean the difference between signing a developing artist and bidding against four other labels for an established one."</p>

<p><strong>Industry reaction has been mixed.</strong> Veteran A&R executives — several of whom spoke to us on background — expressed concern that the restructuring prioritizes data over taste. "The algorithm can tell you who's trending," said one senior A&R VP at a competing label. "It can't tell you who's going to be important in five years. That requires human judgment, relationships, and — frankly — gut instinct. You can't automate gut instinct."</p>

<p>UMG Chairman Lucian Grainge addressed these concerns in an internal memo obtained by us: "This is not about replacing human judgment with machines. It is about ensuring our teams have the best possible tools to find extraordinary artists, wherever they are, as early as possible. The A&R instinct remains irreplaceable. The A&R process is evolving."</p>

<p>The restructuring is expected to result in a net reduction of approximately 15 positions across the division, though UMG says affected employees will be offered retraining into the new hybrid roles. Union representatives for UMG's UK operations have requested a formal consultation period.</p>

<p>Warner Music Group and Sony Music have not announced similar restructurings, though sources at both companies indicated that internal discussions about AI-augmented A&R are "well advanced."</p>"""),

    ("Money Moves", "Independent Labels See 47% Revenue Surge from Sync Licensing Deals", """<p>New data released this week by Merlin, the global rights agency representing independent labels, reveals a staggering 47% year-over-year increase in sync licensing revenue for its members — a number that significantly outpaces the major labels' sync growth of 18% over the same period.</p>

<p>In raw numbers: Merlin's member labels collectively earned $2.1 billion from sync placements in 2025, up from $1.43 billion in 2024. The growth was driven primarily by three sectors: streaming television (up 62%), gaming (up 54%), and social media content licensing (up 89%).</p>

<p><strong>Why independents are winning:</strong></p>

<p>The answer is structural, not artistic. Independent labels can clear sync licenses faster — often within 48-72 hours — compared to major label clearance processes that routinely take 2-4 weeks. In an era where content production cycles have compressed dramatically (a Netflix series might need 40 sync placements cleared in a single production month), speed has become a decisive competitive advantage.</p>

<p>"We had a music supervisor call us on a Thursday, needing a clearance by Monday for a scene they were editing over the weekend," said Rachel Torres, head of sync at independent label group [PIAS]. "We turned it around in six hours. She told us the major label she'd approached first quoted her three weeks. That placement was worth $85,000."</p>

<p><strong>The social media factor</strong> deserves special attention. The 89% growth in social media sync revenue reflects a relatively new licensing category: brands and creators paying to license music for sponsored content on TikTok, Instagram Reels, and YouTube Shorts. Unlike user-generated content (which is covered by platform-level blanket licenses), branded content requires individual sync clearances — and independent labels have been far more aggressive about building streamlined licensing portals for this market.</p>

<p>Merlin CEO Jeremy Sirota pointed to the gaming sector as the next major growth driver. "Gaming soundtracks used to be an afterthought — stock music and original scores. Now games like Fortnite, GTA, and FIFA are cultural platforms in their own right. Their music budgets have tripled in three years, and they're increasingly looking for independent and alternative catalog that gives their games a distinct identity. Major label pop has its place, but music supervisors want texture and authenticity. That's where independent music thrives."</p>

<p><strong>The implication for independent artists:</strong> If you're on an independent label — or self-releasing — make sure your music is registered with a sync agent or aggregator that actively pitches to music supervisors. Sync income is one of the few revenue streams in music that's growing faster than streaming, and the barrier to entry for independents has never been lower.</p>"""),

    ("AI Music Lab", "Google DeepMind's New Model Generates Master-Quality Stems on Demand", """<p>Google DeepMind quietly published a technical paper this week describing Lyria 3, the latest iteration of its music-generation AI — and the capabilities it demonstrates are raising urgent questions across the industry.</p>

<p>Unlike previous music AI systems that generate complete mixed tracks, Lyria 3 can separate, regenerate, and remaster individual stems (vocals, drums, bass, guitar, keys, etc.) from any existing recording with what Google describes as "near-lossless fidelity." In plain terms: you can feed it a finished song and get back individual instrument tracks that sound as clean as the original studio recordings.</p>

<p><strong>Why this matters:</strong></p>

<p>Stem separation technology isn't new — tools like iZotope RX and Moises.ai have offered it for years. What's different about Lyria 3 is the quality. Independent blind tests conducted by the Audio Engineering Society found that listeners could not reliably distinguish Lyria 3's separated stems from original studio multitracks in 78% of test cases. Previous best-in-class tools scored around 45% on the same test.</p>

<p>The implications are enormous and immediate. For remix and sampling: producers can now extract clean, artifact-free stems from any recording ever made, opening up the entire history of recorded music as raw material. For rights holders: this dramatically complicates enforcement of sampling clearances, since AI-separated stems can be manipulated beyond recognition. For live performance: DJs and producers can create real-time remixes and mashups with studio-quality stems extracted on the fly.</p>

<p><strong>The copyright question:</strong></p>

<p>Industry groups have responded swiftly. The RIAA issued a statement calling the technology "a potentially devastating tool for copyright infringement at scale" and urging Congress to clarify that AI-powered stem separation of copyrighted recordings constitutes unauthorized reproduction. The IFPI (International Federation of the Phonographic Industry) echoed these concerns, noting that current copyright frameworks "were not designed to address a world where any recording can be instantly decomposed into its constituent parts."</p>

<p>Google's position, articulated in the paper's ethics section, is that stem separation itself is a transformative process analogous to reverse engineering and should be treated as fair use. This argument is virtually certain to be tested in court.</p>

<p>Dr. Meredith Chen, an intellectual property scholar at Stanford Law School, offered a nuanced take: "The technology itself is neutral. A screwdriver can build a house or break into one. The legal question isn't whether stem separation should exist — it's how we create a licensing framework that allows legitimate creative use while protecting rights holders. That framework doesn't exist yet, and we're running out of time to build it."</p>

<p>Google has not announced a public release date for Lyria 3, stating that it is "engaging with industry stakeholders" before making the technology widely available. However, open-source implementations based on the published paper are already appearing on GitHub.</p>"""),

    ("Rights & Royalties", "The Streaming Royalty Cliff: What the New Congressional Bill Means for Artists", """<p>A bipartisan group of senators introduced the Living Wage for Musicians Act this week — a bill that, if passed, would fundamentally restructure how streaming platforms compensate artists. The bill's central provision: a mandated minimum per-stream payment of $0.01 for any stream exceeding 30 seconds.</p>

<p>To put that number in context: the current average per-stream rate across major platforms is approximately $0.003-0.005, depending on the platform, the listener's subscription tier, and the territory. The proposed minimum would represent roughly a 2-3x increase in per-stream payments.</p>

<p><strong>How it would work:</strong></p>

<p>The bill proposes replacing the current "pro-rata" streaming model — where all subscription revenue is pooled and distributed based on total stream share — with a "user-centric" model where each subscriber's payment goes only to the artists they actually listened to. Under this model, if you pay $10.99/month and listen exclusively to five artists, your entire royalty contribution goes to those five artists, rather than being diluted across the platform's entire catalog.</p>

<p>Additionally, the bill mandates that no less than 50% of streaming revenue be allocated to rights holders (songwriters, publishers, labels, and artists), with at least 20% of that flowing directly to performers — a provision designed to address the well-documented problem of artists receiving pennies while labels and distributors capture the majority of streaming income.</p>

<p><strong>Who supports it:</strong></p>

<p>The bill has attracted bipartisan co-sponsors from both parties, driven in part by constituent pressure from musicians in Nashville (Tennessee), Los Angeles (California), and Austin (Texas) — all states with significant music industry employment. The United Musicians and Allied Workers union, the American Association of Independent Music (A2IM), and the Songwriters Guild of America have all endorsed the bill.</p>

<p><strong>Who opposes it:</strong></p>

<p>Unsurprisingly, the major streaming platforms are lobbying aggressively against the bill. Spotify's head of public policy called the minimum per-stream mandate "economically unworkable" in a blog post, arguing that it would require either significant subscription price increases or a reduction in the platform's catalog. Amazon Music, Apple Music, and YouTube Music have not commented publicly but are understood to share Spotify's position through industry trade groups.</p>

<p>The major labels' stance is more complex. While higher per-stream rates would benefit their catalogs, the user-centric model would likely reduce payments to the most-streamed major label artists (who benefit disproportionately from the current pro-rata system) while increasing payments to mid-tier and independent artists. Sources at two of the three majors described their position as "cautiously observing."</p>

<p><strong>Realistic outlook:</strong> Music industry legislation moves slowly in Congress, and the bill faces significant lobbying opposition from the tech sector. Most observers give it a less than 30% chance of passing in its current form. However, the bill's introduction shifts the Overton window on streaming compensation and may pressure platforms to make voluntary adjustments to avoid regulatory action — a strategy that has precedent in the EU's approach to digital copyright reform.</p>"""),

    ("Deal Radar", "Three Catalogs That Just Changed Hands and What They Signal About Valuations", """<p>Three significant catalog acquisitions closed in the past two weeks, and taken together, they paint an interesting — and somewhat contradictory — picture of where the music rights market is heading in 2026.</p>

<p><strong>Deal 1: Hipgnosis Acquires 1990s R&B Catalog — $340M</strong></p>
<p>Hipgnosis Songs Capital (the Blackstone-backed entity, distinct from the original Hipgnosis fund) closed on a catalog of approximately 4,200 songs spanning the golden era of 1990s R&B. The catalog includes writing credits on hits by TLC, Toni Braxton, and Boyz II Men, among others. The reported price of $340 million represents a multiple of approximately 22x net publisher share (NPS) — a premium that raised eyebrows given Hipgnosis's well-publicized financial difficulties over the past 18 months.</p>

<p>The rationale: 1990s R&B is experiencing a dramatic resurgence in sync demand, driven by nostalgia-themed television and film. Sync revenue from the catalog grew 67% year-over-year, and Hipgnosis is betting that this trend has significant runway.</p>

<p><strong>Deal 2: Primary Wave Acquires Classic Rock Catalog — $180M</strong></p>
<p>Primary Wave, the independent publisher known for its brand-building approach to legacy catalogs, acquired a portfolio of classic rock copyrights including songs by three Hall of Fame-inducted bands. The $180M price tag represents approximately 18x NPS — in line with historical norms for blue-chip classic rock catalogs but notably below the peak multiples of 25-30x that were common in 2021-2022.</p>

<p>Primary Wave CEO Larry Mestel has been vocal about his belief that the market correction of 2023-2024 overcorrected, creating buying opportunities for well-capitalized acquirers. "Premium catalogs never went on sale before," he told us. "For about 18 months, they did. That window is closing."</p>

<p><strong>Deal 3: Abu Dhabi Sovereign Wealth Fund Enters Music Rights — $520M</strong></p>
<p>The most surprising deal of the quarter: the Abu Dhabi Investment Authority (ADIA), one of the world's largest sovereign wealth funds, made its first music industry acquisition — a diversified portfolio of approximately 8,000 copyrights spanning pop, hip-hop, and Latin genres, purchased from a mid-size independent publisher. The $520M price represents a multiple of approximately 24x NPS.</p>

<p>This deal is significant not for the catalog itself but for what it signals: sovereign wealth funds — which have largely stayed out of music rights — are now viewing music catalogs as an asset class comparable to real estate, infrastructure, and private equity. ADIA's entrance brings a new category of deep-pocketed buyer into the market, which is likely to push multiples upward.</p>

<p><strong>What it all means:</strong></p>
<p>The three deals suggest that catalog valuations are climbing again after the 2023-2024 correction, but in a more selective way. Premium catalogs with strong sync potential and nostalgia value are commanding 20-25x multiples, while less distinctive catalogs are trading at 12-16x. The entry of sovereign wealth capital adds a new floor to the market. If you're a rights holder considering a sale, the window of attractive valuations appears to be reopening — but buyers are far more disciplined than they were during the 2021 frenzy.</p>"""),
]

def build_sections(data):
    return [{"html": render_section(name, content, headline)} for name, headline, content in data]

editions = [
    ("fan", fan_intro, fan_sections),
    ("artist", artist_intro, artist_sections),
    ("industry", industry_intro, industry_sections),
]

paths = []
for slug, intro, section_data in editions:
    html = render_newsletter(
        newsletter_name="TrueFans DISPATCH",
        tagline="for Industry Professionals, Music Artists and Fans",
        issue_number=42,
        title=f"{slug.title()} Edition Preview",
        sections=build_sections(section_data),
        header_image_url="",
        intro_copy=intro,
        footer_html="",
        ps_closing="Thanks for reading! Hit reply and tell us what you think — we read every response.",
        edition_slug=slug,
        issue_date="March 20, 2026",
    )
    path = os.path.join(tempfile.gettempdir(), f"newsletter_preview_{slug}.html")
    with open(path, "w") as f:
        f.write(html)
    paths.append(path)
    print(f"{slug.title()} Edition: {path}")

for p in paths:
    webbrowser.open(f"file://{p}")

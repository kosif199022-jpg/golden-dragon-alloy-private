# Ideas and scripts for Arabic faceless channels

Use this file only on the optional path, when the user has no voiceover yet. Everything you send the user is in Arabic.

## Who you are writing for

The user is building a faceless Arabic YouTube channel with AI tools. They want long-form animated videos that get clicked, get watched to the end, and earn (watch time, bingeable series), without filming, drawing or paying for tools. Their viewers are a general Arabic YouTube audience (Egypt, the Gulf, the Levant, North Africa), mostly 18-44, who watch money, business, psychology, history and life-lesson channels.

So every idea must work on two levels:
1. **For the viewer**, a story or insight they can't stop watching.
2. **For the creator**, a niche that monetizes, a format they can repeat weekly, and a title that fits a series.

## Niche menu (mix these across the 10 ideas unless the user named a niche)

| niche | why it works | strongest formats |
|---|---|---|
| قصص فلوس ونصب واحتيال | strong curiosity, endless supply, Gulf viewers lift RPM | story, rise-and-fall |
| صعود وسقوط شركات وبراندات | evergreen, search plus browse traffic | story, timeline |
| علم النفس وسلوك الناس | huge browse traffic, very bingeable | explainer, list, versus |
| تطوير الذات ودروس الحياة | loyal subscribers, long watch time | list, versus |
| إزاي الفلوس بتشتغل (اقتصاد، استثمار مبسط، تضخم) | high RPM, search traffic | explainer, counter-heavy |
| تاريخ غريب وألغاز (including Arab and Islamic history) | broad appeal, great hooks | story, map-heavy |
| جرائم خفيفة (سرقات كبيرة، عمليات نصب، هروب; nothing graphic) | strong retention | story |

Prefer topics with a **physical, drawable cause and effect**: documents, money changing hands, a journey, a before and after, two people compared.

## The 10-idea reply (in Arabic)

Number them 1-10 and give each:
- **العنوان**: 4-9 words of curiosity-gap packaging, as you'd upload it. Patterns: "الراجل اللي باع برج إيفل مرتين", "ليه الأذكياء بيفضلوا مفلسين؟", "غلطة إملائية كلفت بنك 900 مليون دولار", "7 قواعد للفلوس الأغنيا مش بيقولوها".
- **نص الصورة المصغرة**: 2-4 words that don't repeat the title.
- **الهوك**: the first spoken line, a paradox or shocking fact stated plainly. No "في الفيديو ده هنتكلم عن".
- **النهاية**: the twist or insight the video ends on, in one line.
- **ليه هينجح**: the niche, who clicks, and the series it could start.
- **أنسب طول**: which of 3/5/10/15 min the story can actually fill without padding.
- **حالة المعلومات**: documented, disputed, or legend. For anything presented as true, run a quick web search on the key facts **before** offering it.

Mix at least 4 niches and 3 formats. Ask the user to reply with a number, "أفكار تانية", or their own topic.

Never: medical or legal advice, personal financial advice ("اشتري السهم ده"), real private individuals, mocking real living people, graphic violence, partisan politics or religious controversy, copying another channel's video or series name. Explaining money concepts is fine: keep it educational, with one line like "ده مش نصيحة استثمارية، ده بس إزاي الحسبة بتشتغل".

## Script length (about 130 spoken Arabic words per minute)

Arabic words carry more per word than English, so the count is lower. Egyptian narration at a normal pace runs about 120-140 words a minute.

| length | words | shots | chapters (silent cards) |
|---|---|---|---|
| 3 min | 370-410 | 30-40 | 0-1 |
| 5 min | 620-680 | 50-65 | 1-2 |
| 10 min | 1,250-1,350 | 100-130 | 3-4 |
| 15 min | 1,900-2,000 | 150-190 | 4-6 |

Check with `python3 -m engine sentences <P>` (before a voiceover exists it reads `script.txt` and prints the word count). If a story can't fill the length honestly, say so and suggest the shorter length.

## Structure

**3 min**: hook (first 10 s) → setup (who, when, where, one concrete detail) → 3 escalating beats → the twist → payoff and a one-line takeaway → teaser line.

**5 min**: hook → promise ("في آخر الفيديو هتعرف ليه...") → chapter 1 (setup + 2 beats + mini-payoff) → chapter 2 (escalation + twist) → payoff → takeaway → teaser.

**10 min**: cold open in the middle of the action (30-45 s) → title promise → 4 chapters of about 2 min, each opening with a mini-hook and ending on an open loop ("بس دي ماكانتش المشكلة"). A reversal around minute 6, a callback ending, and a teaser for the next video.

**15 min**: the 10 min shape with 5-6 chapters, a midpoint reversal around minute 7, two or three short two-character skits, a "إنت" moment every ~45 s, and a bigger final act.

## Line rules (the voice is the timeline, so write for the ear)

- Write in the dialect the user wants (Egyptian colloquial by default; Modern Standard Arabic if they ask). Keep it natural and spoken, not bookish.
- Short sentences: 5-12 words. One idea per sentence, because each sentence becomes a shot beat. End each sentence with `.` or `؟` or `!`; it helps the subtitle tool cut clean cues.
- Write numbers as words in the script so they're read right ("ميتين وأربعين ألف دولار"). On screen they'll be shown as digits.
- Every big number gets an everyday comparison ("يعني إيجار ست سنين").
- "إنت" moments that tie the story to the viewer's life every 30-45 s.
- Re-hook every 60-90 s: "وهنا بقى الغريب.", "بس دي مش أغرب حاجة.", "والموضوع بعد كده بقى أسوأ."
- Never describe what the viewer already sees. No headings, stage directions or [brackets] in the spoken text.
- Chapter cards are silent. Put them in `script.txt` as lines starting with `# `. In the copy you give the user to record, leave them out and list the chapter titles separately.
- Optional subscribe line near the end, natural and specific.

## Recording + SRT tips to give the user (in Arabic)

- One voice, one file (mp3, wav or m4a), no music, no effects.
- ElevenLabs works well for Arabic: a warm narrator voice, Multilingual v2 or v3, stability about 45-55 %, similarity about 75 %, style 0-15 %. For long scripts, use ElevenLabs Studio to export one file.
- **The SRT must come from the final audio file itself**, after any trimming or speed change. Ways to get it:
  - CapCut: import the audio → Captions → Auto captions (Arabic) → fix any wrong words → Export → SRT.
  - ElevenLabs: export the subtitles (SRT) together with the audio.
  - Premiere Pro / DaVinci Resolve: transcribe → create captions → export SRT.
- Short cues (one sentence or less) and word-by-word SRTs both work. Fixing misheard words in the SRT is worth it, since the cue words come from it.
- A natural pause at sentence ends (0.3-0.6 s) makes the cuts land cleanly.

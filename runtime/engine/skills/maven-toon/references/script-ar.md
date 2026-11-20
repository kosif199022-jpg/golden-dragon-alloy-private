# Maven Toon: writing the Arabic script (كتابة السكربت)

Read this before writing any Arabic script. The engine draws what the words say, so a good script is also a good
storyboard: one picture per sentence, things that exist in the kit, light that follows the story.
Check every script with `python toon.py script PROJECT --seconds N` before the voice is made.

## 1. Pick the register first, then never mix

| Register | When | Sounds like |
|---|---|---|
| **Iraqi (default)** | stories, comedy, everyday life, proverbs, the tea house, the family | بس، هسه، شلون، ليش، لعد، چان، هواية، كلش، شكد، اكو، ماكو، گال، يمّه |
| **Simple fusha** | science facts, history, religion-adjacent topics, a pan-Arab audience | لكنّ، ثم، لذلك، في تلك الليلة، هل تعلم |

Ask the user if it is not clear. Keep one register from the first word to the last. Spell Iraqi letters as said:
چ (چاي، چان)، گ (گال، گلبي)، ڤ only in foreign names. The caption font (Lalezar) draws all of them.

## 2. Length = words (Arabic voice ~2.1 words per second)

| Video | Words | Sentences |
|---|---|---|
| 15 s | 28-32 | 5-6 |
| 20 s | 38-44 | 6-8 |
| 30 s | 58-66 | 9-11 |
| 45 s | 88-96 | 13-16 |
| 60 s | 118-128 | 17-21 |

ElevenLabs Arabic voices and Edge TTS at +6 % land at 2.0-2.3 words/s; a slow storyteller is 1.7. A captions-only
Short (no voice) reads at 2.0 words/s. If the user's voice is already recorded, the words are fixed: never change them.

## 3. The shape (micro-fable, 15-60 s)

1. **Hook, first 3.5 s (≤ 7 words):** a strange fact said flatly, inside the action, no teaser. Never open with a
   question, a greeting, "in this video", or "wait until the end".
   - ✓ `الچايچي ما ياخذ فلوس على أول استكان.`
   - ✓ `بغداد چانت تنام كلها فوق السطوح.`
   - ✗ `هل تعرفون ليش...؟` ✗ `اليوم راح أحچيلكم قصة...`
2. **Context (1-2 sentences):** who, where. Straight into the scene.
3. **Escalation (10-60 %):** 3-5 short beats joined by بس / فـ / وبعدين / وبليلة من الليالي / هسه. Side characters
   mock or push: `الكل ضحك عليه.` Rule of three works: three customers, three nights, three tries.
4. **Turn (60-90 %):** the mechanism in 1-3 sentences, opened by `تدري ليش؟` (Iraqi) or `والسبب؟` / `والسرّ؟`
   (fusha). The best turn is an everyday second-person picture: `مثل ما تخلي الچاي يتخدّر على نار هادية...`
5. **Payoff (≤ 9 words):** the twist is the last sentence. A callback to the hook lands hardest.

Devices that work in Arabic: deadpan quoted dialogue (`گال: "باچر."`), understatement (`شوية مشكلة.`), a literal
proverb (show `إيد وحدة ما تصفّگ` with one hand actually trying to clap), repetition with a change on the third time.

## 4. One picture per sentence

Write each sentence so it can be drawn with what the kit has (references/LIBRARY.md):
- a **place**: chaikhana (tea house), souq, shatt (river + palms), classroom, rooftop, street, kitchen, office,
  shop_counter, field, desert_rails, castle_hall, ship_deck, prehistoric, planet_shop, town_top;
- **people**: hajji, hajjiya, mom, grandma, teacher, student, schoolgirl, chaichi, fallah, doctor, footballer,
  shopkeeper (+ worker, boss, cop, cook, knight, king, scientist, cashier, sailor, caveman, kid, alien), animals cat,
  camel, dino;
- **things in hand**: tea, tray, teapot, book, phone, ball, samoon, money, dates, misbaha, sign:نص, tag:نص,
  newspaper:سطر|سطر.
If the story needs something the kit does not have, keep it out of the picture (say it, don't show it) or add a prop
to a set (LIBRARY.md "To add a set").

## 5. Light follows the story (write for it)

Setup in daylight (`day` / `interior`) → the problem or the secret at night (`night`, 50-70 % of the runtime) →
the explanation in warm gold (`golden`, a close-up of the key object) → the ending at sunset or dawn. A memory or a
dream is `dream`. Put a time word in the sentence where the light changes (`بالليل`، `الصبح`، `قبل خمسين سنة`).

## 6. Writing rules

- 5-10 words per sentence, one line each in script.txt. Commas only where the voice breathes.
- Numbers as words in voice scripts (`خمسين سنة`، not `50`), digits only for in-world signs and price tags.
- No voice tags (`[whispers]`, `(بهمس)`): write the feeling into the words.
- No tashkeel except to stop a misreading (`عَلَم` vs `عِلم`).
- Concrete nouns over abstract ones: `استكان`, `سماور`, `بلم`, `مبردة`, `صمّون`, `نخلة`.
- "You" works: speak to the viewer in the turn (`انت هم تسويها كل يوم.`).
- Facts must be true. For science, history or numbers, check them and list the sources under the script for the user
  (not in script.txt).

## 7. Example scripts

**15 s, Iraqi, tea house (28 words)**
```
الچايچي ما ياخذ فلوس على أول استكان.
كل الگهوة گالت: راح يفلس.
بس محلّه صار أزحم محل بالشارع.
تدري ليش؟
اللي يشرب أول استكان، يگعد ويطلب الثاني.
والثالث.
```

**25 s, Iraqi, rooftop memory (50 words)**
```
بغداد چانت تنام كلها فوق السطوح.
بالصيف، البيت يصير فرن.
فكل عائلة تصعد فراشها للسطح.
الناموسيات بيض، والسما مليانة نجوم.
الجيران يحچون من سطح لسطح.
وبعدين جت المبردة.
وبعدين جا المكيف.
ونزلت بغداد من السطوح.
تدري شنو الغريب؟
الحرّ ما تغيّر.
اللي تغيّر... إحنا.
بس جدّتي؟
لهسه تصعد كل ليلة.
```

**25 s, fusha, science (52 words; facts: the date palm has a single growing tip, the heart of palm (جُمّار), and is pollinated by hand in spring)**
```
النخلة تنمو من نقطةٍ واحدة فقط.
إن قطعتَ رأسها، ماتت كلّها.
لذلك لا يقصّ الفلاح قمّة النخلة أبداً.
لكنّه يصعد إليها كلّ ربيع.
يلقّح عذوقها بيده، عذقاً عذقاً.
والسرّ؟
للنخلة قلبٌ واحد، في قمّتها تماماً.
كلّ سعفة، وكلّ تمرة، تخرج من ذلك القلب.
مثل شمعة لها فتيل واحد.
وإن أطفأته، انطفأت الشمعة.
```

## 8. From script to storyboard (what to hand the engine)

For each sentence write one line of shot notes before the JSON: `set / mood / who does what / framing`. Example
for the 15 s tea-house script:
1. chaikhana / interior / chaichi pours, ECU on the istikan / `chaichi:face` then push to the glass
2. chaikhana / interior / three customers laugh (`hajji`, `student`, `shopkeeper`) / `two`
3. souq / day / crowd at his door / wide push-in
4. chaikhana / golden / ECU of the second istikan / calm
5. chaikhana / golden / hajji sits, raises a finger: `talk` / `hajji:face`
6. rooftop or shatt / sunset / chaichi smiles with the tray / pull-out

Then write storyboard.json with the word indices from words.json (SKILL.md step 3).

## 9. Title, description, hashtags (Shorts)

- Title: the hook, shortened to ≤ 6 words, no clickbait the video does not pay off.
- Description: one sentence of the story + `#شورتس #كرتون #قصص_عراقية` + 2-3 topic tags.
- Tell the user where the music should go (the engine mixes `music.*` only if they put their own track in the project).

## 10. Idea starters (when the user has no story yet)

Iraqi proverbs shown literally (`المبلل ما يخاف من المطر`), the wise tea seller, grandma's stories, school-day
situations, the souq and its tricks, weird facts about palms / the Tigris / old Baghdad, inventions from Baghdad's
House of Wisdom, animals people know (cats, camels) with "you" in the hook. Ten ideas per niche, each one line with
its hook; the user picks one, then write it in the shape above.

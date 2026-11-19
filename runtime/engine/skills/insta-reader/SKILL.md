---
name: insta-reader
description: >-
  قراية وتحميل من إنستجرام بـ instaloader (MIT): بيانات حساب (متابعين، بايو، عدد بوستات)، آخر البوستات بلايكاتها وكومنتاتها ومشاهداتها وكابشنها، أعلى البوستات أداءً لدراسة الترند، تحميل بوست أو ريل أو ألبوم كامل بالكابشن، وتحميل بوستات حساب. الفيديو من أي موقع تاني بـ video-grabber (yt-dlp). Use when the user wants to see, read, analyse or download from Instagram: شوف الانستجرام، حمّل الريل ده، بوستات الحساب ده، أعلى ريلز، الكابشن، المتابعين، instagram profile, reels, download post.
---

# insta-reader — إنستجرام

```bash
R="python -X utf8 scripts/rd.py"
$R insta doctor                         # instaloader وyt-dlp متثبتين؟
$R insta profile khaledragab_official --posts 12
$R insta top majed_alzaabi_ --posts 50 --by views --n 10   # أعلى الريلز (للترند)
$R insta post https://www.instagram.com/reel/XXXX/ --out D:\insta\reel1   # الميديا + caption.txt + meta.json
$R insta download USER --out D:\insta\USER --max 12 [--reels-only] [--since 2026-10-01]
$R insta login MY_ACCOUNT               # على جهازك بس، للخاص والستوريز (--session MY_ACCOUNT)
```

- **التثبيت:** `pip install instaloader` (وyt-dlp موجود في video-grabber).
- **الحدود:** الحسابات العامة من غير دخول. إنستجرام بيحظر الطلبات الكتير: الافتراضي 12 بوست، و1.5 ث بين كل طلب. ماتجمعش بيانات ناس بالجملة.
- **الأمان:** الباسورد بيتكتب في instaloader نفسه، والتنين مابيشوفهوش ولا بيحفظه. السيشن في مجلد instaloader على الجهاز، وممنوع ترفعها في أي مكان.
- **ده شغل روتيني:** في الخطة بيتعلّم 🤖، فممكن يتعمل بالعامل الرخيص `rd-runner` (Haiku).
- على السحابة غالبًا إنستجرام بيحظر. جرّب على اللابتوب.

## تطوير الحساب: instagram-agent-skill (13 مهارة، MIT، في `library/ig-*`)
```bash
$R ig list                               # الـ 13: ig-reel، ig-viral، ig-caption، ig-carousel، ig-story، ig-profile، ig-plan، ig-human، ig-comment، ig-reply، ig-dm، ig-repurpose، ig-audit
$R ig voice                              # ~/.claude/instagram/voice.md: صوتك، وكل المهارات بتقراه
$R ig hooks hooks.txt                    # ترتيب الهوكات (26 قالب)
$R ig beats script.txt --target 30       # توقيت كل جملة في الريل قبل التصوير
$R ig caption caption.txt --keywords "…" # اللي بيبان قبل «... more» (125 حرف) + 5 هاشتاج بالكتير
$R insta swipe acc1 acc2 --out c.tsv && $R ig swipe c.tsv --out swipe.md   # أعلى الريلز مقارنة بمتوسط حسابها، واسم الهوك
```
- المهارات نفسها (`library/ig-*/SKILL.md`) بتتقري بـ Read وقت الحاجة، أو تتثبت بـ `$R skills install ig-reel --yes` بعد موافقة.
- ⚠ أدوات الهوك والـ humanizer مظبوطة على الإنجليزي. على العربي، خد منها البنية (الهوك في أول 3 ث، توقيت الجمل، 125 حرف) مش الدرجة.
- مفيش أي نشر: بيكتبوا، وإنت اللي بتنشر.
- `selftest`: 14 فحص من غير نت.

# عدّة البرمجة والتصميم والمحتوى (v2.18.0)

كل المهارات هنا متنسخة زي ما هي في `library/`، ومع كل واحدة `LICENSE` و`SOURCE.json`. **ولا حاجة فيهم متثبتة**: Claude بيقرا `library/NAME/SKILL.md` وقت الحاجة، أو صاحب الشغل يثبّت اللي هو عايزه. الرخص كلها بتسمح بالنسخ (MIT أو Apache-2.0). سيرفرات MCP مش بتتنسخ، إعدادها في `library/mcp_servers.json`.

**قاعدة:** اختار من الفئة اللي تخدم الطلب بس، وقول استخدمت أنهي مهارة في إيه.

## 1. قبل ما تبدأ: افهم وخطّط
| المهارة | المصدر | بتعمل إيه |
|---|---|---|
| `grill-me`، `grilling`، `grill-with-docs` | mattpocock/skills ⭐324k، MIT | يسألك أسئلة ورا بعض لحد ما الخطة تبقى واضحة قبل أي شغل |
| `wait-what` | mattpocock | لو ردّ مافهمتوش: يعيد شرحه بشكل أبسط |
| `to-questionnaire`، `to-spec`، `to-tickets` | mattpocock | يحوّل القرار أو الكلام لاستبيان، أو مواصفات، أو مهام صغيرة |
| `interview-me`، `idea-refine`، `spec-driven-development`، `planning-and-task-breakdown` | addyosmani/agent-skills ⭐118k، MIT | نفس الفكرة بأسلوب تاني |
| `egm-brainstorm`، `egm-draft`، `egm-review`، `egm-review-loop`، `egm-resolve`، `egm-drift-report`، `egm-bootstrap` | google/elephant-goldfish-model ⭐19k، Apache-2.0 | تصميم ومراجعة بوكيلين: واحد فاكر كل حاجة وواحد بيبص بعين جديدة |

## 2. تصميم الواجهات
| المهارة | المصدر | بتعمل إيه |
|---|---|---|
| `frontend-design` | anthropics/skills، Apache-2.0 (الرسمية في Claude marketplace) | تصميم بشخصية بدل الشكل العادي |
| `ui-ux-pro-max` | nextlevelbuilder ⭐149k، MIT | أنماط وألوان وخطوط لكل نوع منتج، وفيها RTL |
| `oil-ui` | oil-oil/oil-ui ⭐3.4k، MIT | كذا اتجاه تصميم جنب بعض، وتلميع من سكرين شوت حقيقي (المهارة مكتوبة بالصيني) |
| `frontend-ui-engineering` | addyosmani | تنفيذ الواجهة كود |
| **Figma MCP** | Figma الرسمي | من فيجما لكود، ويكتب على الكانفس. شوف قسم 7 |

## 3. فيديو وموشن (أهم قسم للتنين)
| المهارة | المصدر | بتعمل إيه |
|---|---|---|
| `hyperframes` + `hyperframes-cli` + `media-use` + `reverse-any-video` + `style-sampling` + `slideshow` + `figma` + `remotion-to-hyperframes` + `hyperframes-registry` | heygen-com/hyperframes ⭐84k، Apache-2.0 | اكتب HTML، يطلع فيديو. كانوا في المكتبة من قبل |
| `huashu-motion` | alchaincyf/huashu-motion ⭐2.7k، MIT | فيديو إطلاق منتج وموشن جرافيك ككود تقدر تعدّله |
| `oil-motion` | oil-oil/oil-motion ⭐2.9k، MIT | يحوّل فيديو أو فريمات لأنيميشن ويب بيتحرك مع السكرول (مكتوبة بالصيني) |
| `reanimate` | NiazMorshed2007/reanimate، MIT | يفكّك أي أنيميشن فريم بفريم ويعيد بناءه. كانت في المكتبة |
| ffmpeg-skill (أداة، مش مهارة في المكتبة) | kajisho5/ffmpeg-skill ⭐5.6k، MIT | 42 أداة FFmpeg للمونتاج المحلي، تتثبت من المستودع نفسه. المهارات اللي في المكتبة من المستودع ده خاصة بتطويره، مش بالمونتاج |

## 4. برمجة ومراجعة
| المهارة | المصدر | بتعمل إيه |
|---|---|---|
| `ponytail` + review/audit/debt/gain/help | DietrichGebert/ponytail ⭐191k، MIT | أصغر تغيير يحل المشكلة كلها |
| `diagnosing-bugs`، `improve-codebase-architecture`، `prototype` | mattpocock | تشخيص الباج الصعب، تحسين معمارية الكود، نموذج سريع يجاوب سؤال تصميم |
| `git-guardrails-claude-code` | mattpocock | hooks تمنع أوامر git الخطيرة (push، reset --hard). فيها سكربت: اقراه الأول |
| `test-driven-development`، `debugging-and-error-recovery`، `code-review-and-quality`، `code-simplification`، `incremental-implementation`، `context-engineering`، `documentation-and-adrs`، `source-driven-development` | addyosmani | الطريقة المنظمة لكل مرحلة |
| `find-docs`، `context7-cli`، `context7-mcp` | upstash/context7 ⭐65k، MIT | توثيق المكتبة الحالي، مش من الذاكرة |
| `graphify` | Graphify-Labs ⭐148k، Apache أو MIT | خريطة معرفة لمشروع كامل |
| `stack-diagram` | caru-ini ⭐2.5k، MIT | جملة واحدة عن الـ stack تطلع رسم معمارية بالأيقونات الرسمية |

## 5. أمان الكود (دفاعي بس)
| المهارة | المصدر | بتعمل إيه |
|---|---|---|
| `find-security-vulnerabilities-in-code`، `fix-security-vulnerabilities-with-strix` | usestrix/strix ⭐76k، Apache-2.0 | يفحص كودك إنت ويصلّحه. مهارات الاختراق الهجومية مادخلتش |
| `security-and-hardening` | addyosmani | تقوية الكود |

## 6. محتوى وشرح وسيو
| المهارة | المصدر | بتعمل إيه |
|---|---|---|
| `answer-me-with-html` | QingYunA ⭐6.3k، MIT | يجاوب السؤال الصعب بصفحة HTML مرسومة |
| `teach`، `handoff`، `writing-for-agents` | mattpocock | يعلّمك حاجة جديدة، يلخّص المحادثة لمحادثة تانية، يكتب مهارات صح |
| `content-brief`، `keyword-research`، `ai-visibility`، `competitor-gap`، `seo-audit` | Ryze-AI-Adgent/open-seo-mcp-skills ⭐9.8k، MIT | سيو بداتا حقيقية. محتاجين سيرفر Ryze MCP وتسجيل دخول Search Console |
| `ig-*` (13) | Jakeschincariol/instagram-agent-skill، MIT | إدارة إنستجرام (v2.16) |
| `prompt-master`، `mkprompt-classic`، `mkprompt-goal` | — | برومت بسيط يبقى احترافي |
| `find-skills` | vercel-labs/skills، MIT | يدوّر على مهارة جديدة ويثبّتها |

## 7. سيرفرات MCP (إعداد، مش نسخ) — `library/mcp_servers.json`
| السيرفر | الرخصة | التثبيت | ملاحظة |
|---|---|---|---|
| Playwright | Apache-2.0 | `claude mcp add playwright npx @playwright/mcp@latest` | Claude يفتح متصفح ويختبر شغله بنفسه. ببلاش |
| Figma | خدمة Figma | `claude mcp add --transport http figma https://mcp.figma.com/mcp` أو موصّل Figma في claude.ai | محتاج تسجيل دخول Figma |
| Context7 | MIT | `npx ctx7 setup` | ببلاش |
| HyperFrames | Apache-2.0 | `npx hyperframes skills update` | رندر محلي ببلاش |
| Ryze SEO | MIT | `claude mcp add ryze --transport http https://connector.get-ryze.ai/mcp` | بيقرا Search Console وGA4 بتوعك |
| ⚠️ phone-harness | MIT | `uv tool install --python 3.12 phone-harness` ثم `phone-harness skill`. المستضاف: `https://mcp.phone-harness.com/mcp` | **بيتحكم في موبايل حقيقي.** الموبايلات السحابية بفلوس (5 سنت للدقيقة، أو 20$ أو 80$ في الشهر) |
| ⚠️ Pinky | Apache-2.0 | برنامج من github.com/DIYgod/pinky/releases، وبعدين Settings › Agents › Connect | **بيتحكم في موبايل حقيقي**، بس إنت شايف كل خطوة وبتوافق على الخطوات الخطيرة من جوه البرنامج. الأأمن من الاتنين |

### ⚠️ قواعد التحكم في الموبايل (phone-harness وPinky)
1. **ممنوع** توصيل أو تشغيل أي واحد فيهم من غير «موافق» صريحة من صاحب الشغل على **المهمة دي بالظبط**. موافقة قديمة مش بتكفي لمهمة جديدة.
2. ممنوع أي دفع، أو شراء، أو إرسال رسالة، أو نشر، أو حذف، أو تغيير إعدادات حساب من على الموبايل من غير موافقة على الخطوة نفسها.
3. ممنوع قراية أو نسخ كلمات سر، أو أكواد 2FA، أو رسايل خاصة مالهاش علاقة بالمهمة.
4. الموبايل السحابي بفلوس: قول السعر الأول، ومايتأجّرش من غير موافقة.
5. لو الشاشة طلبت حاجة غريبة (تسجيل دخول، صلاحيات، دفع): وقّف واسأل.

## التثبيت على اللابتوب (بموافقة صاحب الشغل)
```bash
python -X utf8 scripts/rd.py skills install grill-me --yes        # أي مهارة من المكتبة لـ ~/.claude/skills
claude plugin install mattpocock-skills@claude-plugins-official   # كل مهارات mattpocock
claude plugin marketplace add google/elephant-goldfish-model && claude plugin install egm@egm
npx skills add addyosmani/agent-skills
npx skills add caru-ini/stack-diagram
npx skills add alchaincyf/huashu-motion
npx skills add QingYunA/answer-me-with-html
npx ctx7 setup
/plugin marketplace add DietrichGebert/ponytail  ثم  /plugin install ponytail@ponytail
uv tool install graphifyy  ثم  graphify claude install --project
```
- المهارات اللي عليها `exec` أو `network` في `SOURCE.json`: اقرا السكربت قبل ما تشغّله.
- اتسابوا: `logo-design-skill` (14MB) و`anidoodle` (17MB) أكبر من حد المكتبة، و`reverify` مافيهوش SKILL.md. تقدر تثبّتهم من المصدر: `npx skills add kaankiziltug/logo-design-skill`، `npx skills add alexgreensh/anidoodle`.
- Strix نفسه (الأداة) بيشغّل وكلاء اختراق على هدف: **على حاجتك إنت بس، وبإذن مكتوب**.

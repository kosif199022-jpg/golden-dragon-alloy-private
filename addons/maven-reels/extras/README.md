# Extras: other people's skills that go well with Maven Reels

These folders are **not** Maven's work and are **not** covered by `rights/MAVEN-RIGHTS.txt`. Each one is shipped
unchanged under its own licence, which is kept in its folder. Install them all with:

```
python scripts/install_extras.py
```

| Folder | What it does | By | Licence | Installed as |
|---|---|---|---|---|
| `instagram-agent/` | 13 Instagram skills: reel scripts from 26 scored hook formulas, captions, carousels, stories, profile score, weekly plan, comments, DMs, repurposing, audits, a humanizer | Jake Schincariol, [github.com/Jakeschincariol/instagram-agent-skill](https://github.com/Jakeschincariol/instagram-agent-skill) | MIT | `ig-*` skills |
| `marketingskills/` | 53 marketing skills: social, ad creative, copywriting, launch, pricing, SEO and more | Corey Haines, [github.com/coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | MIT | plugin `marketing-skills` |
| `remocn/` | Ready-made Remotion animations and a brief-to-video workflow; connects to the public server remocn.dev/mcp | Remocn, [github.com/Remocn/remocn](https://github.com/Remocn/remocn) | MIT | plugin `remocn` |
| `skill-creator/` | Makes new skills, e.g. one that writes captions in your own voice from your best posts | Anthropic, [github.com/anthropics/skills](https://github.com/anthropics/skills) | Apache 2.0 | `skill-creator` skill |
| (downloaded) | Remotion's official skills: write videos as React code | Remotion, [github.com/remotion-dev/skills](https://github.com/remotion-dev/skills) | no licence file, so not shipped here | `remotion-*` skills |

## How they fit with Maven Reels
- **Before the reel:** `ig-viral` finds what works in your niche, `ig-reel` writes and scores the hook and script.
- **The reel:** Maven Reels copies the style of a reference and draws it in code. For React/Remotion videos, use
  the Remotion skills and `remocn`.
- **After the reel:** `ig-caption` writes the caption, `ig-human` strips AI tells, `marketing-skills:social` plans
  posting.
- **Your voice:** give `skill-creator` your three best posts and ask for a skill that writes like you.

Read a skill's files before you install it. Versions here were copied on 2026-11-16.

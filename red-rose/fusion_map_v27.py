"""Full-fusion coverage map: legacy Dragon/Alloy units -> native Red Rose adapters.

Every legacy reference unit is classified into a capability family and one
honest category:
  native        a registered Red Rose adapter implements the family natively
  guidance      a method/rule/checklist: kept as searchable knowledge, not code
  meta_catalog  indexing/search/atlas tooling superseded by the registry,
                roadmap and knowledge.store
  network       needs the internet (downloads, scraping); Red Rose is offline
                by decision, so these stay unfused until the owner approves
  paid          needs a paid/external AI service; never fused without approval
  external_app  drives an outside program (Blender, Adobe, MCP bridges)
  missing       no native implementation yet
Classification is keyword/prefix based (a heuristic), and coverage means
"a native adapter exists for the family", not that every legacy behaviour is
reproduced. Pure module: rows are passed in; nothing is read or written here.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

CATEGORIES = ('native', 'guidance', 'meta_catalog', 'playbook', 'native_gated', 'prepared_gated',
              'bridge', 'network', 'paid', 'external_app', 'missing')
# V28: when these adapters exist, the outward-facing categories get an honest Red Rose path:
#   network      -> native_gated   (net.fetch: code exists, every connection needs --approve-write)
#   paid         -> prepared_gated (prompt.prepare: prompts/cost/approval request; never spends)
#   external_app -> bridge         (app.bridge: drives an installed outside program on approval)
#   unrouted catalog/skill/tool rows -> playbook (playbook.library: analysed into followable playbooks)
UPGRADES = {'network': ('native_gated', 'net.fetch'), 'paid': ('prepared_gated', 'prompt.prepare'),
            'external_app': ('bridge', 'app.bridge')}
PLAYBOOK_KINDS = {'catalog-skill', 'skill', 'tool', 'lib', 're', 'program', 'mcp'}

# Numbered-power family prefix -> (category, adapters). Adapters must exist in REGISTRY.
FAMILIES = {
    'TRANS': ('native', ['motion.core', 'video.edit']), 'CAM': ('native', ['motion.core', 'math.geometry']),
    'EASE': ('native', ['motion.core']), 'SHAPE': ('native', ['graphics.motion']),
    'DRAW': ('native', ['graphics.motion', 'style.draw']), 'GLOW': ('native', ['graphics.motion', 'vfx.compose']),
    'TEX': ('native', ['graphics.motion']), 'PART': ('native', ['graphics.motion', 'physics.simulate']),
    'DATA': ('native', ['graphics.motion']), 'MAP': ('native', ['graphics.motion', 'fusion.route']),
    'EXPL': ('native', ['graphics.motion']), 'RETRO': ('native', ['graphics.motion']),
    'UI': ('native', ['graphics.motion']), 'BRAND': ('native', ['graphics.motion', 'design.layout']),
    'TYPE': ('native', ['text.motion']), 'ARAB': ('native', ['text.motion', 'design.layout']),
    'SYNC': ('native', ['text.motion', 'audio.process']), 'FMT': ('native', ['text.motion', 'math.geometry']),
    'CAPTION': ('native', ['text.motion']), 'SUBTITLE': ('native', ['text.motion']),
    'ENG': ('native', ['studio.render']), 'BEAT': ('native', ['studio.render', 'audio.process']),
    'COLOR': ('native', ['studio.render', 'video.edit']), 'COLOUR': ('native', ['style.draw']),
    'LOOK': ('native', ['studio.render']), 'EXPORT': ('native', ['studio.render']),
    'QA': ('native', ['studio.render', 'automation.run', 'video.verify']),
    'CHECK': ('native', ['governance.audit', 'agents.coordinate']),
    'FOOT': ('native', ['audio.process', 'governance.audit']), 'FOOTAGE': ('native', ['video.edit']),
    'STORY': ('native', ['video.edit', 'thinking.reason']), 'CHAR': ('native', ['character.animate']),
    'FULL': ('native', ['character.animate']), 'CHARACTER': ('native', ['character.animate']),
    '3D': ('native', ['model3d.build']), 'NATIVE': ('native', ['model3d.build']),
    'MODEL': ('native', ['thinking.reason']), 'THINK': ('native', ['thinking.reason', 'decision.make']),
    'THINKING': ('native', ['thinking.reason']), 'IDEA': ('native', ['thinking.reason']),
    'DECISION': ('native', ['decision.make', 'thinking.reason']), 'PROD': ('native', ['decision.make']),
    'PLAN': ('native', ['agents.coordinate']), 'AGENT': ('native', ['agents.coordinate']),
    'AMIND': ('native', ['learning.evolve', 'agents.coordinate']), 'ASTRAT': ('native', ['agents.coordinate']),
    'ACODE': ('native', ['code.analyze', 'security.guard']), 'CODE': ('native', ['code.analyze']),
    'ABUILD': ('native', ['app.build']), 'APP': ('native', ['app.build']), 'APPX': ('native', ['app.build', 'motion.core']),
    'ADATA': ('native', ['database.manage', 'architecture.check']), 'ANLY': ('native', ['database.manage']),
    'STATS': ('native', ['science.compute', 'learning.evolve']), 'SYSTEM': ('native', ['science.compute']),
    'ADOCS': ('native', ['app.build']), 'DOC': ('native', ['app.build']), 'WRITE': ('native', ['code.analyze']),
    'WRITING': ('native', ['code.analyze']), 'REWRITE': ('native', ['governance.audit']),
    'SEC': ('native', ['security.guard']), 'SAFE': ('native', ['security.guard']),
    'REA': ('native', ['code.analyze', 'security.guard']), 'CRAFT': ('native', ['code.analyze']),
    'REPOSITORY': ('native', ['security.guard', 'architecture.check']), 'REPO': ('native', ['code.analyze']),
    'MEDIA': ('native', ['video.analyze', 'audio.process']), 'VIDEO_ANALYSIS': ('native', ['video.analyze']),
    'AUDIO': ('native', ['audio.process']), 'WAV': ('native', ['audio.process']), 'MUSIC': ('native', ['video.edit']),
    'FAST': ('native', ['video.edit', 'audio.process']), 'CINEMA': ('native', ['video.edit', 'studio.render']),
    'UNIFIED': ('native', ['studio.render']), 'MONTAGE': ('native', ['studio.render', 'video.edit']),
    'REEL': ('native', ['studio.render']), 'CINEMATIC': ('native', ['studio.render', 'motion.core']),
    'HTML': ('native', ['studio.render']), 'DETERMINISTIC': ('native', ['studio.render']),
    'SVG': ('native', ['motion.core', 'graphics.motion']), 'SEEKABLE': ('native', ['graphics.motion']),
    'MOTION': ('native', ['text.motion']), 'OVERLAPPING': ('native', ['motion.core']), 'THIRD': ('native', ['motion.core']),
    'DOODLE': ('native', ['graphics.motion']), 'DIAGRAM': ('native', ['graphics.motion', 'design.layout']),
    'DESIGN': ('native', ['design.layout']), 'ORIGINAL': ('native', ['design.layout']), 'FONT': ('native', ['design.layout']),
    'ARABIC': ('native', ['library.evaluate']), 'ARL': ('native', ['knowledge.store']),
    'FLEXIBLE': ('native', ['math.geometry']), 'PHOTO': ('native', ['video.analyze']),
    'HAND': ('native', ['style.draw']), 'STAGED': ('native', ['style.draw']), 'ACRAFT': ('native', ['design.layout']),
    'MEMORY': ('native', ['learning.evolve', 'knowledge.store']), 'SOURCES': ('native', ['knowledge.store']),
    'LESSON': ('native', ['science.compute']), 'BACKGROUND': ('native', ['automation.run']),
    'MACHINE': ('native', ['architecture.check']), 'PYTHON': ('native', ['library.evaluate']),
    'INSTALLER': ('native', ['security.guard']), 'DIFFERENTIAL': ('native', ['learning.evolve']),
    'API': ('native', ['app.build']), 'TTS': ('native', ['text.motion']), 'QURAN': ('native', ['audio.process']),
    'INVENTION': ('native', ['thinking.reason']), 'BRIEF': ('native', ['governance.audit']),
    'BLENDER': ('external_app', []), 'CYCLES': ('external_app', []), 'CREATE': ('external_app', []),
    'ADOBE': ('external_app', []), 'PHOTOCRAFT': ('external_app', []), 'NLE': ('external_app', []),
    'REMOTION': ('external_app', []), 'LOCAL': ('external_app', []), 'MOSAMEM': ('external_app', []),
    'GEN': ('paid', []), 'AMEDIA': ('paid', []), 'SUNO': ('paid', []), 'GEMINI': ('paid', []),
    'PROMPT': ('guidance', []), 'PROMPTSMOTION': ('network', []), 'FUTUREPEDIA': ('guidance', []),
    'VOICE': ('external_app', []),
    'DL': ('network', []), 'VIDEO': ('network', []), 'TIKTOK': ('network', []), 'INSTAGRAM': ('network', []),
    'KEYLESS': ('network', []), 'DASH/HLS': ('network', []), 'AWEB': ('network', []), 'WEB': ('network', []),
    'COLLECT': ('network', []), 'PERMITTED': ('network', []), 'BROWSER': ('network', []), 'WEBSITE': ('network', []),
    'GITHUB': ('network', []), 'OFFICIAL': ('network', []), 'FREE': ('network', []), 'LICENSED': ('guidance', []),
    'SELF': ('guidance', []), 'BOOK': ('guidance', []), 'PRO': ('guidance', []), 'MANDATORY': ('guidance', []),
    'CHARTER': ('guidance', []), 'DRAWING': ('guidance', []), 'SOURCE': ('guidance', []), 'AI': ('guidance', []),
    'WEDNESDAY': ('guidance', []), 'GRAPH': ('external_app', []),
}
META_PREFIXES = {'TOOL', 'ATLAS', 'KOSIF', 'CREATIVE', 'REFERENCE', 'CAPABILITY', 'SKILL', 'FUSIONFORGE',
                 'STYLE', 'SEE', 'BLACK', 'TASK', 'USIP', 'POWER', 'SMART', '100', 'OFFLINE', 'REVIEWED',
                 'SESSION', 'FAMILY', 'CATALOG', 'GROUP', 'MICRO', 'OWNED', 'SUPERPOWERS', 'REBALANCE', 'PROOF',
                 'UNIVERSAL', 'LIGHT', 'COMMUNITY', 'SUPERPOWER', 'EXTERNAL', 'PROCESS', 'MISC', 'SCRIPT'}

# Keyword routing for unnumbered units (catalog skills, skills, tools, references...).
DOMAINS = [
    ('paid', [], r'\b(suno|elevenlabs|kling|higgsfield|runway|midjourney|openai|gemini|fal\.ai|replicate|stripe)\b'),
    ('network', [], r'\b(google|gws|drive|calendar|gmail|posthog|espn|serpapi|safari|browser|webhook\w*|oauth|salesforce|zendesk|fullstory|sentry|datadog|vercel|netlify|cloudflare|aws|azure|gcp|firebase|supabase)\b'),
    ('guidance', [], r'\b(git|branch(es)?|pull request|prs?|worktree\w*|merge queue|commit\w*|rebase|graphite|handover|digest|clinic|patient|hospital|oee|takt|manufactur\w*|referral\w*|exam)\b'),
    ('external_app', [], r'\b(piper|tts engine|text-to-speech model|voice clon\w*)\b'),
    ('network', [], r'\b(scrap\w*|crawl\w*|download\w*|yt-dlp|youtube|tiktok|instagram|twitter|linkedin|facebook|slack|gmail|notion|jira|salesforce|hubspot|shopify|airbnb|amazon|booking)\b'),
    ('external_app', [], r'\b(blender|photoshop|after effects|premiere|3ds ?max|maya|unity|unreal|figma|davinci|krita|gimp|inkscape)\b'),
    ('native', ['studio.render', 'video.edit'], r'\b(montage|edit(ing)?|reel|shorts|cut|timeline|render|b-roll|trailer|vlog)\b|مونتاج|ريل'),
    ('native', ['motion.core', 'graphics.motion', 'text.motion'], r'\b(motion|animat\w*|transition|kinetic|typography|lottie|gsap|easing|svg)\b|موشن|تحريك'),
    ('native', ['audio.process'], r'\b(audio|sound|music|voice|podcast|loudness|lufs|mix(ing)?|transcri\w*|whisper)\b|صوت'),
    ('native', ['video.analyze'], r'\b(video analysis|frame|scene detect\w*|image analysis|ocr|vision|thumbnail)\b'),
    ('native', ['style.draw', 'design.layout'], r'\b(design|logo|brand\w*|poster|palette|colou?r|illustrat\w*|draw\w*|art|style|ui|ux)\b|تصميم|رسم'),
    ('native', ['character.animate'], r'\b(character|rig\w*|lip ?sync|avatar)\b'),
    ('native', ['model3d.build'], r'\b(3d|mesh|gltf|obj|three\.js|webgl)\b'),
    ('native', ['physics.simulate', 'science.compute', 'math.geometry'], r'\b(physics|math\w*|geometry|simulation|statistic\w*|fft|signal)\b|فيزياء|رياضيات'),
    ('native', ['accounting.check'], r'\b(accounting|invoice|ledger|ifrs|audit\w*|payroll|tax|finance|budget|reconcil\w*)\b|محاسب'),
    ('native', ['database.manage', 'knowledge.store'], r'\b(database|sql\w*|data|csv|excel|etl|dbt|analytics|search|knowledge|rag|memory)\b'),
    ('native', ['security.guard'], r'\b(security|secret\w*|vulnerab\w*|pentest|privacy|owasp|threat)\b'),
    ('native', ['code.analyze'], r'\b(code review|lint\w*|refactor\w*|debug\w*|bug|test(ing|s)?|static analysis)\b'),
    ('native', ['app.build', 'architecture.check'], r'\b(app|api|backend|frontend|react|next\.?js|python|node|cli|deploy\w*|docker|kubernetes|ci|devops|architecture|sdk|mcp|plugin)\b'),
    ('native', ['agents.coordinate', 'decision.make', 'thinking.reason'], r'\b(agent\w*|plan\w*|decision|strategy|think\w*|brainstorm\w*|critique|council|workflow|orchestrat\w*)\b'),
    ('guidance', [], r'\b(marketing|seo|copy\w*|sales|ads?|campaign|content|social|email|growth|coach\w*|career|interview|meeting|writing)\b'),
]
_COMPILED = [(c, a, re.compile(rx, re.I)) for c, a, rx in DOMAINS]


def classify(kind, title, summary='', *, registry=None):
    """Return (family, category, adapters) for one legacy unit."""
    text = f'{title or ""} {summary or ""}'
    if kind in ('lesson', 'rule'):
        return ('OWNER_LESSONS', 'native', ['learning.evolve', 'memory.recall'])
    if kind == 'power':
        prefix = re.split(r'[-_ ]', title or '')[0].upper()
        if prefix in META_PREFIXES:
            fam = (prefix, 'meta_catalog', ['knowledge.store', 'roadmap.status'])
        elif prefix in FAMILIES:
            cat, adapters = FAMILIES[prefix]
            fam = (prefix, cat, list(adapters))
        else:
            fam = (prefix, 'missing', [])
    elif kind in ('reference', 'road', 'thinking'):
        fam = (kind.upper(), 'guidance', ['knowledge.store'])
    elif kind == 'superpower':
        # SP-xxxx records are groupings of other powers ("N members"), i.e. catalog structure.
        fam = ('SUPERPOWER_GROUPS', 'meta_catalog', ['knowledge.store'])
    elif kind in ('script', 'cmd', 'engine'):
        # Legacy runtime internals: independence forbids shipping them as code.
        fam = ('LEGACY_RUNTIME', 'meta_catalog', ['governance.audit'])
    else:
        fam = None
        for cat, adapters, rx in _COMPILED:
            if rx.search(text):
                fam = (kind.upper() + ':' + (adapters[0] if adapters else cat), cat, list(adapters))
                break
        if fam is None:
            fam = (kind.upper() + ':unrouted', 'missing', [])
    if registry is not None and fam[1] == 'native':
        absent = [a for a in fam[2] if a not in registry]
        if absent:
            fam = (fam[0], 'missing', [a for a in fam[2] if a in registry])
    if registry is not None:
        if fam[1] in UPGRADES and UPGRADES[fam[1]][1] in registry:
            cat, adapter = UPGRADES[fam[1]]
            fam = (fam[0], cat, [adapter])
        elif fam[1] == 'missing' and kind in PLAYBOOK_KINDS and 'playbook.library' in registry:
            fam = (fam[0], 'playbook', ['playbook.library'])
    return fam


def coverage(rows, *, registry=None):
    """rows: iterable of (kind, title, summary). Aggregate counts only."""
    by_cat, by_kind, fam_counts, fam_cat = Counter(), defaultdict(Counter), Counter(), {}
    adapters_used = Counter()
    total = 0
    for kind, title, summary in rows:
        fam, cat, adapters = classify(kind, title, summary, registry=registry)
        total += 1
        by_cat[cat] += 1
        by_kind[kind][cat] += 1
        fam_counts[fam] += 1
        fam_cat[fam] = cat
        for a in adapters:
            adapters_used[a] += 1
    fusable = total - by_cat['network'] - by_cat['paid'] - by_cat['external_app']
    native = by_cat['native'] + by_cat['meta_catalog'] + by_cat['guidance']
    absorbed = native + by_cat['playbook']
    gated = by_cat['native_gated'] + by_cat['prepared_gated'] + by_cat['bridge']
    missing_fams = sorted(((f, n) for f, n in fam_counts.items() if fam_cat[f] == 'missing'), key=lambda x: -x[1])
    return {
        'total_units': total,
        'by_category': {c: by_cat.get(c, 0) for c in CATEGORIES},
        'by_kind': {k: dict(v) for k, v in sorted(by_kind.items(), key=lambda x: -sum(x[1].values()))},
        'fusable_units': fusable,
        'fused_or_absorbed_units': native,
        'fusion_ratio_of_fusable': round(native / fusable, 4) if fusable else None,
        'units_with_red_rose_path': absorbed + gated,
        'path_ratio_of_all_units': round((absorbed + gated) / total, 4) if total else None,
        'path_breakdown': {'native_or_absorbed': native, 'playbook': by_cat['playbook'],
                           'gated_or_bridged': gated, 'missing': by_cat['missing']},
        'missing_families_top': missing_fams[:25],
        'adapters_used': dict(adapters_used.most_common()),
        'method': 'keyword/prefix classification (heuristic); native = adapter exists, not every legacy behaviour reproduced',
    }

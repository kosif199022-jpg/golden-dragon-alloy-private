"""Text-only Kling prompt-pack planner; does NOT generate media or spend credits."""
from __future__ import annotations
import math, re

ASPECTS={'9:16','16:9','21:9','1:1','2.39:1'}

def make_pack(spec:dict) ->dict:
    required=('title','goal','obstacle','reversal','value_before','value_after','character','location','duration_s')
    missing=[k for k in required if not str(spec.get(k,'')).strip()]
    if missing: raise ValueError('missing required spec keys: '+', '.join(missing))
    seconds=int(spec['duration_s'])
    if not (3<=seconds<=600):raise ValueError('duration_s must be an integer in 3..600')
    if seconds!=float(spec['duration_s']):raise ValueError('duration_s must be a whole second')
    aspect=str(spec.get('aspect','9:16'))
    if aspect not in ASPECTS:raise ValueError('unsupported aspect ratio')
    flash=bool(spec.get('flash',False)); limit=20 if flash else 30
    if flash and seconds>20 and not spec.get('allow_multiblock',True):raise ValueError('Flash blocks limited to 20s')
    lengths=[limit]*(seconds//limit)
    remainder=seconds%limit
    if remainder:
        if remainder<3 and lengths:
            lengths[-1] -= 3-remainder
            lengths.append(3)
        else:
            lengths.append(remainder)
    blocks=[]
    start=0
    for index,duration in enumerate(lengths,1):
        name=f"{spec['title']} / Block {index}"
        prompt=(f"SCENE CONTEXT\n{name}. {duration} seconds, {aspect}. A cinematic scene following {spec['character']} "
                f"at {spec['location']}. Goal: {spec['goal']}. Obstacle: {spec['obstacle']}. "
                f"Reversal: {spec['reversal']}.\n\n"
                f"ACTIVE REFERENCES\n@Image1 — CHARACTER — {spec['character']}: identity and wardrobe only; location, pose and light are not inherited.\n"
                f"@Image2 — LOCATION — {spec['location']}: geometry and materials only; camera framing is not inherited.\n"
                f"@Image3 — STORYBOARD: controls shot order. Do not render the storyboard itself.\n\n"
                f"LOCATION MAP\nOne hero enters from frame-right; the room is fixed and the key prop remains on the same side.\n\n"
                f"FIRST FRAME AND SPATIAL BLOCKING\nExactly 1 person on screen, in a natural pose, spatial continuity preserved.\n\n"
                f"FORMAT MODE\nSingle continuous take with physical continuity.\n\n"
                f"OPTICS\nNatural portrait perspective and believable depth of field.\n\n"
                f"CAMERA\nOne motivated, stable dolly movement per phase.\n\n"
                f"ACTION TIMING\n0.0-{duration:.1f}s — The character attempts the goal, encounters "
                f"a meaningful obstacle and a credible reversal that changes the audience's verdict.\n\n"
                f"ACTING TASK\nPerformance moves from {spec['value_before']} to {spec['value_after']}.\n\n"
                f"PHYSICS\nNatural weight, contact, cloth motion and practical light interactions.\n\n"
                f"LIGHTING\nReal-world practical lights with motivated soft fill and consistent exposure through the block.\n\n"
                f"AUDIO\nNo subtitles. No background music. Arabic voiceover is added during authorized post-production if needed.\n\n"
                f"STYLE\nCinematic naturalism with coherent composition, real skin and fabric detail, measured contrast.\n\n"
                f"QUALITY\nConsistent character identity, realistic texture, motivated lighting and coherent screen direction.\n\n"
                f"POSITIVE CONSTRAINTS\nThe subject remains physically continuous and clearly separated from the background; "
                f"all props keep fixed positions and the shot remains grounded in the scene geometry.")
        blocks.append({'block':index,'start_s':start,'end_s':start+duration,'duration_s':duration,
                       'continuity_from_previous':'Keep previous block final pose, screen direction and prop placement.' if index>1 else 'Establish stable hero identity and location.',
                       'prompt':prompt,'storyboard_3x3':f"Create a 3x3 contact sheet for {name}, 9 distinct sequential camera phases, "
                                         f"{aspect} cells, consistent protagonist and setting, no embedded labels, "
                                         "for planning only; do not render the storyboard itself."})
        start+=duration
    # This is pure text lint, not a call to the remote Kling service.
    from engines.kling_director.lint import lint
    for block in blocks:
        tests=lint(block['prompt'],duration=block['duration_s'],flash=flash)
        block['local_prompt_lint']={
            'pass':all(t['status']!='FAIL' for t in tests),
            'failures':[t for t in tests if t['status']=='FAIL'],
            'warnings':[t for t in tests if t['status']=='warn']}
    return {'kind':'black-dragon.v10/kling-text-pack','name':spec['title'],'aspect':aspect,
            'duration_s':seconds,'mode':'Flash' if flash else 'standard','block_limit_s':limit,
            'story_engine':{'goal':spec['goal'],'obstacle':spec['obstacle'],'reversal':spec['reversal'],
                            'value_shift':[spec['value_before'],spec['value_after']]},
            'elements':{'character_id':'@char_hero_v1','location_id':'@loc_scene_v1'},
            'blocks':blocks,'actual_generation':False,'paid_credits_spent':0,
            'rights_and_consent':'Require authority for provided faces/voices, and explicit approval for external upload and generation.',
            'fact_status':'Kling product limits recorded from user-supplied October 2026 skill; reverify on the live service before spending.'}

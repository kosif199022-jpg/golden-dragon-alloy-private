"""Deterministic art-identity profiles for original stylized 2D characters.

A palette lock is not photoreal identity preservation or face recognition.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
from camera import _color

IDENTITY_FIELDS = ('skin', 'hair', 'coat', 'trousers')
IDENTIFIER = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$')


def validate_profiles(profiles):
    """Validate untrusted JSON, normalize hex codes and produce stable hashes."""
    if not isinstance(profiles, dict) or not 1 <= len(profiles) <= 64:
        raise ValueError('profiles must contain 1..64 named characters')
    result = {}
    for ident, profile in profiles.items():
        if not isinstance(ident, str) or not IDENTIFIER.fullmatch(ident):
            raise ValueError('invalid character profile identifier')
        if not isinstance(profile, dict) or not set(profile).issubset(IDENTITY_FIELDS):
            raise ValueError('profile must specify only identity palette fields')
        if not all(field in profile for field in IDENTITY_FIELDS):
            raise ValueError('profile must include all four palette fields')
        normalized = {field: _color(profile[field]).lower() for field in IDENTITY_FIELDS}
        digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        result[ident] = {'palette': normalized, 'sha256': digest}
    return result


def apply_profiles(shots, profiles):
    """Deep copy shots, lock actor palette, return profiles' stable checksums.

    A conflicting color in a shot is rejected, not silently substituted.
    """
    checked = validate_profiles(profiles)
    updated = copy.deepcopy(shots)
    used = {}
    for shot in updated:
        recipe = shot.get('recipe', {})
        if recipe.get('mode') != 'director2d':
            continue
        actor = recipe.get('actor', {})
        ident = actor.get('character_id')
        if ident is None:
            continue
        if ident not in checked:
            raise ValueError('missing character profile: '+str(ident))
        if actor.get('rig', 'ik2d') != 'ik2d':
            raise ValueError('character profiles require rig=ik2d')
        actor['rig'] = 'ik2d'
        for field, value in checked[ident]['palette'].items():
            if field in actor and _color(actor[field]).lower() != value:
                raise ValueError(f'character identity drift: {ident}.{field}')
            actor[field] = value
        actor['profile_sha256'] = checked[ident]['sha256']
        used[ident] = checked[ident]['sha256']
    return updated, used

#!/usr/bin/env python3
"""Standalone opt-in, side-effect-limited contract and SEE package audit.

Distilled engineering patterns informed by ECC (MIT): https://github.com/affaan-m/ECC
Does not connect to MCP/providers, run any external command, or install hooks.
"""
import json
import re

SECRET=re.compile(r'(?i)(?:sk-[a-z0-9_-]{15,}|(?:api[_-]?key|password|private[_-]?key|auth(?:orization)?)\s*[:=]\s*[^\s,;]{8,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)')
RECEIPT_KEYS={'status','summary','owner','evidence','artifacts','next_actions','retryable','verified'}
STATES={'success','warning','error'}



def validate_receipt(x):
    reasons=[]
    if not isinstance(x,dict):return {'status':'error','issues':['NOT_OBJECT']}
    if not RECEIPT_KEYS.issubset(x):reasons.append('MISSING_FIELDS:'+','.join(sorted(RECEIPT_KEYS-set(x))))
    if x.get('status') not in STATES:reasons.append('INVALID_STATUS')
    if not isinstance(x.get('owner'),str) or not x.get('owner'):reasons.append('OWNER_REQUIRED')
    for k in ('evidence','artifacts','next_actions'):
        if not isinstance(x.get(k),list):reasons.append(k.upper()+'_MUST_BE_ARRAY')
    if type(x.get('verified')) is not bool or type(x.get('retryable')) is not bool:reasons.append('BOOLEANS_REQUIRED')
    if x.get('verified') is True and (x.get('status')!='success' or not x.get('evidence')):reasons.append('UNVERIFIED_SUCCESS_CLAIM')
    if x.get('status')=='error' and x.get('verified') is True:reasons.append('ERROR_CANNOT_BE_VERIFIED_SUCCESS')
    return {'status':'success' if not reasons else 'error','issues':reasons}

def plan_learning(record,consent):
    issues=[]
    if not consent:issues.append('EXPLICIT_CONSENT_REQUIRED')
    if not isinstance(record,dict):return {'status':'error','issues':['NOT_OBJECT']}
    for key in ['project_id','trigger','action','evidence','observed_at']:
        if not isinstance(record.get(key),str) or not record[key].strip():issues.append('MISSING_'+key.upper())
    if not re.fullmatch(r'[a-zA-Z0-9_-]{3,80}',record.get('project_id','')):issues.append('PROJECT_ID_UNSAFE')
    if record.get('scope','project')!='project':issues.append('GLOBAL_PROMOTION_REQUIRES_SEPARATE_REVIEW')
    if not issues and SECRET.search(json.dumps(record,ensure_ascii=False)):issues.append('POSSIBLE_SECRET_INPUT')
    if issues:return {'status':'error','issues':issues}
    return {'status':'success','proposal':{key:record[key] for key in ['project_id','trigger','action','evidence','observed_at']} | {'scope':'project','status':'proposed_not_published','promotion':'manual_review_required'}}


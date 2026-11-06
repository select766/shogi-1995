"""Descriptive accuracy and paired comparisons; HCPE has no game cluster IDs."""
import math
import numpy as np


def wilson(matches,total):
    if not total:return None
    z=1.959963984540054;p=matches/total;d=1+z*z/total
    center=(p+z*z/(2*total))/d
    half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return {'lower':center-half,'upper':center+half}


def summary(rows,total):
    correct=sum(bool(r.get('match')) for r in rows)
    return {'total':total,'measured':len(rows),'matches':correct,'accuracy':correct/total if total else None,
            'wilson_95':wilson(correct,total),'errors':sum(r.get('error') is not None for r in rows),
            'illegal_moves':sum(r.get('legal') is False for r in rows),
            'time_overruns':sum(r.get('time_overrun',False) for r in rows),
            'resignations':sum(r.get('action')=='resign' for r in rows),
            'declarations':sum(r.get('action')=='declaration' for r in rows)}


def paired(baseline,candidate,seed=20261106,replicates=10000):
    if len(baseline)!=len(candidate):raise ValueError('different sample count')
    counts={'both_correct':0,'baseline_only':0,'candidate_only':0,'both_wrong':0}
    for a,b in zip(baseline,candidate):
        if (a['id'],a['sfen'],a['expected'])!=(b['id'],b['sfen'],b['expected']):raise ValueError('different evaluation positions')
        name='both_correct' if a['match'] and b['match'] else 'baseline_only' if a['match'] else 'candidate_only' if b['match'] else 'both_wrong'
        counts[name]+=1
    n=len(baseline)
    if not n:raise ValueError('empty comparison')
    # Multinomial counts are exactly the paired, position-level empirical bootstrap.
    probabilities=np.array([counts['baseline_only'],counts['candidate_only'],n-counts['baseline_only']-counts['candidate_only']])/n
    draws=np.random.default_rng(seed).multinomial(n,probabilities,size=replicates)
    differences=(draws[:,1]-draws[:,0])/n
    return {**counts,'difference':(counts['candidate_only']-counts['baseline_only'])/n,
            'bootstrap_95':dict(zip(('lower','upper'),map(float,np.quantile(differences,[.025,.975])))),
            'replicates':replicates,'seed':seed,
            'limitation':'position bootstrap; unknown within-game correlation is not accounted for'}

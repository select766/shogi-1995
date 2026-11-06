"""Auxiliary score-to-Elo conversion with paired-opening uncertainty."""
from collections import Counter, defaultdict
import math

FAILURES=('illegal_move','illegal_declaration','time_forfeit','engine_failure')


def elo(score):
    if score==0:return None,'-infinity'
    if score==1:return None,'+infinity'
    return 400*math.log10(score/(1-score)),None


def match_summary(games,rating_enabled=False):
    completed=[g for g in games if 'outcome' in g]
    counts=Counter();groups=defaultdict(list)
    failures={name:{reason:0 for reason in FAILURES} for name in ('baseline','candidate')}
    for game in completed:
        color=game['candidate_color'];winner=game['outcome']['winner']
        if color not in (0,1) or winner not in (None,0,1):raise ValueError('invalid game colors')
        result='draw' if winner is None else 'win' if winner==color else 'loss'
        if game['candidate_result']!=result:raise ValueError('game result disagrees with referee')
        counts[result]+=1;groups[game['opening_id']].append(game)
        reason=game['outcome']['reason']
        if reason in FAILURES:
            if winner is None:raise ValueError('operational failure requires a losing side')
            loser='baseline' if winner==color else 'candidate';failures[loser][reason]+=1
    pairs=[]
    for group in groups.values():
        if len(group)>2 or (len(group)==2 and {g['candidate_color'] for g in group}!={0,1}):
            raise ValueError('opening must be played once with each color')
        if len({g['start_sfen'] for g in group})!=1:raise ValueError('same opening ID has different starting positions')
        if len(group)==2:
            pairs.append(sum({'win':1,'draw':.5,'loss':0}[g['candidate_result']] for g in group)/2)
    n=len(completed);p=(counts['win']+.5*counts['draw'])/n if n else None
    operational_pass=not any(count for engine in failures.values() for count in engine.values())
    eligible=bool(rating_enabled and pairs and 2*len(pairs)==n and operational_pass)
    result={'games':n,'wins':counts['win'],'draws':counts['draw'],'losses':counts['loss'],
            'score_rate':p,'completed_opening_pairs':len(pairs),'operational_failures':failures,
            'operational_pass':operational_pass,'rating_eligible':eligible,
            'elo_difference_estimate':None,'elo_difference_boundary':None,
            'score_rate_95':None,'elo_difference_95':None,
            'scope':'score-to-Elo conversion against this frozen opponent and time setting; not a league rating',
            'interval_method':'Hoeffding 95% bound on independent opening-pair scores; each pair contains both colors',
            'limitation':'small auxiliary sample; unknown correlations across different source openings are not modeled'}
    if eligible:
        result['elo_difference_estimate'],result['elo_difference_boundary']=elo(p)
        # Pair scores lie in [0,1]. Keeping colors together allows arbitrary
        # dependence within an opening; independence between openings is an
        # explicit assumption. Unlike empirical percentile bootstrap, this
        # bound does not collapse to certainty after an observed clean sweep.
        radius=math.sqrt(math.log(2/.05)/(2*len(pairs)))
        lower=max(0,p-radius);upper=min(1,p+radius)
        lo,lo_boundary=elo(lower);hi,hi_boundary=elo(upper)
        result['score_rate_95']={'lower':lower,'upper':upper}
        result['elo_difference_95']={'lower':lo,'upper':hi,
                                     'lower_boundary':lo_boundary,'upper_boundary':hi_boundary}
    return result

"""Opponent-aware form adjustments from observed, completed fixtures only.

This is a heuristic improvement to a short-form Poisson baseline, NOT a
calibrated probability model. No additional APIs, private keys or guesses.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from math import exp


def opponent_indices(fixtures, cutoff, days=180):
    """Return heavily regularized opponent attack/defence multipliers.

    Uses all *completed* matches before cutoff, never future match results.
    Scores from a single fixture cannot create an extreme club rating.
    """
    from build_data import iso_datetime
    stats = defaultdict(lambda: [0, 0.0, 0.0])
    oldest = cutoff - timedelta(days=days)
    for match in fixtures:
        if match.get('status') != 'FINISHED':
            continue
        try:
            kickoff = iso_datetime(match['utcDate'])
        except (KeyError, TypeError, ValueError):
            continue
        if not oldest <= kickoff < cutoff:
            continue
        h, a = (match.get('homeTeam') or {}).get('id'), (match.get('awayTeam') or {}).get('id')
        result = (match.get('score') or {}).get('fullTime') or {}
        hg, ag = result.get('home'), result.get('away')
        if h is None or a is None or type(hg) is not int or type(ag) is not int or min(hg, ag) < 0:
            continue
        stats[h][0] += 1
        stats[h][1] += hg
        stats[h][2] += ag
        stats[a][0] += 1
        stats[a][1] += ag
        stats[a][2] += hg
    # Aggressive shrinkage guards against weak competition/coverage and
    # prevents one-sided rankings from turning a single high score into a pick.
    baseline = 1.35
    prior_games = 10
    result = {}
    for tid, (n, scored, conceded) in stats.items():
        if n < 4:
            continue
        attack = (scored + prior_games * baseline) / (n + prior_games) / baseline
        defence = (conceded + prior_games * baseline) / (n + prior_games) / baseline
        result[tid] = {'attack': max(.72, min(1.35, attack)),
                       'defence': max(.72, min(1.35, defence)),
                       'matches': n}
    return result


def adjusted_form(form, indices, cutoff):
    """Adjust goals against the opponent, retaining stable W/D/L data.

    A row without verifiable opponent ID passes through unmodified.
    Unverified opponent strengths *never* invent match scores.
    """
    result = []
    for row in form:
        date, scored, conceded, outcome = row[:4]
        opponent = row[4] if len(row) >= 5 else None
        source = indices.get(opponent) or {}
        if source.get('matches', 0) >= 4:
            gf = scored / source['defence']
            ga = conceded / source['attack']
        else:
            gf, ga = scored, conceded
        result.append((date, gf, ga, outcome))
    return result


def effective_form_sample(form, cutoff, *, half_life_days=100):
    """Discount old observations when judging *confidence*, not selection count."""
    weights = []
    for row in form:
        try:
            days = max(0.0, (cutoff - row[0]).total_seconds() / 86400)
        except (TypeError, ValueError, IndexError):
            continue
        weights.append(exp(-.69314718056 * days / half_life_days))
    return round(sum(weights), 2)

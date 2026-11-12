"""Estimate national-team scoring rates on a shared opponent network."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import exp, expm1, log

from form_history_v38 import regular_time_score, utc
from national_form_v48 import HISTORY_DAYS, OSLO, result_weight

METHOD = 'national_strength_v49'


@dataclass(frozen=True)
class NationalStrength:
    baseline: float
    home_advantage: float
    attack: dict[str, float]
    goals_allowed: dict[str, float]

    def scoring_rates(self, home: str, away: str, *, neutral: bool = False):
        if home == away or home not in self.attack or away not in self.attack:
            return None
        venue = 0.0 if neutral else self.home_advantage / 2
        home_rate = exp(self.baseline + venue + self.attack[home] + self.goals_allowed[away])
        away_rate = exp(self.baseline - venue + self.attack[away] + self.goals_allowed[home])
        # Beyond this range a 30-goal grid does not reliably capture the tails.
        if max(home_rate, away_rate) > 12:
            return None
        return home_rate, away_rate


def _fit_poisson(columns, weights, targets):
    """Minimize weighted Poisson loss plus a ridge penalty on team effects.

    Each coordinate has a convex, one-dimensional objective. Backtracking
    accepts a Newton step only if it decreases that objective.
    """
    parameters = [log(1.3)] + [0.0] * (len(columns) - 1)
    penalties = [0.0, 0.1] + [1.0] * (len(columns) - 2)
    fitted = [1.3 * weight for weight in weights]
    observed = [weight * goals for weight, goals in zip(weights, targets, strict=True)]
    tolerance = 1e-6
    for _ in range(1200):
        biggest_step = 0.0
        for i, (column, penalty) in enumerate(zip(columns, penalties, strict=True)):
            value = parameters[i]
            gradient = penalty * value
            curvature = penalty
            for row, coefficient in column:
                gradient += coefficient * (fitted[row] - observed[row])
                curvature += coefficient**2 * fitted[row]
            step = max(-1.0, min(1.0, -gradient / curvature))
            step = max(-3.0 - value, min(3.0 - value, step))
            while abs(step) >= tolerance:
                change = penalty * step * (value + step / 2)
                for row, coefficient in column:
                    offset = coefficient * step
                    change += fitted[row] * expm1(offset) - observed[row] * offset
                if change <= 0:
                    parameters[i] += step
                    for row, coefficient in column:
                        fitted[row] *= exp(coefficient * step)
                    biggest_step = max(biggest_step, abs(step))
                    break
                step /= 2
        if biggest_step < tolerance:
            return parameters
    return None


def fit_national_strength(fixtures: list[dict], before: datetime) -> NationalStrength | None:
    if before.tzinfo is None:
        raise ValueError('National model requires an analysis time with a timezone')
    cutoff = before.astimezone(OSLO).date()
    start = cutoff - timedelta(days=HISTORY_DAYS)
    matches = []
    for match in fixtures:
        if match.get('status') != 'FINISHED':
            continue
        kickoff = utc(match.get('utcDate'))
        if kickoff is None:
            continue
        day = kickoff.astimezone(OSLO).date()
        if not start <= day < cutoff:
            continue
        home = (match.get('homeTeam') or {}).get('id')
        away = (match.get('awayTeam') or {}).get('id')
        score = regular_time_score(match)
        if not isinstance(home, str) or not isinstance(away, str) or home == away or score is None:
            continue
        venue = 0 if match.get('neutralVenue') is True else 0.5
        weight = result_weight(day, (match.get('competition') or {}).get('name'), cutoff)
        matches.append((home, away, score, venue, weight))
    if not matches:
        return None

    teams = {team: i for i, team in enumerate(sorted({t for h, a, *_ in matches for t in (h, a)}))}
    size = len(teams)
    columns = [[] for _ in range(2 + 2 * size)]
    weights, targets = [], []
    for home, away, (hg, ag), venue, weight in matches:
        for attack, defence, goals, advantage in ((home, away, hg, venue), (away, home, ag, -venue)):
            row = len(targets)
            weights.append(weight)
            targets.append(goals)
            columns[0].append((row, 1))
            if advantage:
                columns[1].append((row, advantage))
            columns[2 + teams[attack]].append((row, 1))
            columns[2 + size + teams[defence]].append((row, 1))
    parameters = _fit_poisson(columns, weights, targets)
    if parameters is None:
        return None
    return NationalStrength(
        baseline=parameters[0], home_advantage=parameters[1],
        attack={team: parameters[2 + i] for team, i in teams.items()},
        goals_allowed={team: parameters[2 + size + i] for team, i in teams.items()},
    )

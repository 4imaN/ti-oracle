from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


GLICKO2_SCALE = 173.7178


@dataclass(frozen=True)
class GlickoRating:
    rating: float = 1500.0
    deviation: float = 350.0
    volatility: float = 0.06


@dataclass(frozen=True)
class GlickoResult:
    opponent: GlickoRating
    score: float


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _expectation(mu: float, opponent_mu: float, opponent_phi: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(opponent_phi) * (mu - opponent_mu)))


def win_probability(player: GlickoRating, opponent: GlickoRating) -> float:
    mu_difference = (player.rating - opponent.rating) / GLICKO2_SCALE
    player_phi = player.deviation / GLICKO2_SCALE
    opponent_phi = opponent.deviation / GLICKO2_SCALE
    combined_phi = math.sqrt(player_phi * player_phi + opponent_phi * opponent_phi)
    return 1.0 / (1.0 + math.exp(-_g(combined_phi) * mu_difference))


def advance_inactivity(rating: GlickoRating, periods: int) -> GlickoRating:
    if periods <= 0:
        return rating
    phi = rating.deviation / GLICKO2_SCALE
    expanded = math.sqrt(phi * phi + periods * rating.volatility * rating.volatility)
    return GlickoRating(
        rating=rating.rating,
        deviation=min(350.0, expanded * GLICKO2_SCALE),
        volatility=rating.volatility,
    )


def rate_period(
    rating: GlickoRating,
    results: Iterable[GlickoResult],
    tau: float = 0.5,
    epsilon: float = 0.000001,
) -> GlickoRating:
    observations = list(results)
    if not observations:
        return advance_inactivity(rating, 1)

    mu = (rating.rating - 1500.0) / GLICKO2_SCALE
    phi = rating.deviation / GLICKO2_SCALE
    converted: list[tuple[float, float, float]] = []
    for result in observations:
        opponent_mu = (result.opponent.rating - 1500.0) / GLICKO2_SCALE
        opponent_phi = result.opponent.deviation / GLICKO2_SCALE
        converted.append((opponent_mu, opponent_phi, result.score))

    variance_inverse = 0.0
    improvement_sum = 0.0
    for opponent_mu, opponent_phi, score in converted:
        g_value = _g(opponent_phi)
        expected = _expectation(mu, opponent_mu, opponent_phi)
        variance_inverse += g_value * g_value * expected * (1.0 - expected)
        improvement_sum += g_value * (score - expected)
    variance = 1.0 / variance_inverse
    delta = variance * improvement_sum

    sigma = rating.volatility
    a = math.log(sigma * sigma)

    def objective(x: float) -> float:
        exponent = math.exp(x)
        numerator = exponent * (delta * delta - phi * phi - variance - exponent)
        denominator = 2.0 * (phi * phi + variance + exponent) ** 2
        return numerator / denominator - (x - a) / (tau * tau)

    lower = a
    if delta * delta > phi * phi + variance:
        upper = math.log(delta * delta - phi * phi - variance)
    else:
        step = 1
        while objective(a - step * tau) < 0.0:
            step += 1
        upper = a - step * tau

    f_lower = objective(lower)
    f_upper = objective(upper)
    while abs(upper - lower) > epsilon:
        candidate = lower + (lower - upper) * f_lower / (f_upper - f_lower)
        f_candidate = objective(candidate)
        if f_candidate * f_upper <= 0.0:
            lower, f_lower = upper, f_upper
        else:
            f_lower /= 2.0
        upper, f_upper = candidate, f_candidate

    new_volatility = math.exp(lower / 2.0)
    pre_rating_phi = math.sqrt(phi * phi + new_volatility * new_volatility)
    new_phi = 1.0 / math.sqrt(1.0 / (pre_rating_phi * pre_rating_phi) + 1.0 / variance)
    new_mu = mu + new_phi * new_phi * improvement_sum
    return GlickoRating(
        rating=new_mu * GLICKO2_SCALE + 1500.0,
        deviation=new_phi * GLICKO2_SCALE,
        volatility=new_volatility,
    )

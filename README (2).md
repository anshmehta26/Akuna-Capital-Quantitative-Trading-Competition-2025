# Akuna Capital Quant Trading Competition — Options Market Making

## Overview

This project documents my market-making strategy for Akuna Capital's quantitative trading competition. The challenge involved pricing European-style options on simulated underlyings and continuously quoting bid/ask markets against competing market makers.

The objective was not simply to estimate fair value. A successful strategy also had to balance quote competitiveness, option inventory, volatility, time to expiry, adverse selection, and bankruptcy risk.

I finished as a **Top 10 finalist** and advanced directly to the final-round interview for Akuna Capital's 2026 Junior Quant Developer & Strategist role.

> This repository documents my own pricing and market-making logic. It does not include private test cases or proprietary competition infrastructure.

---

## Competition Setup

Each simulated underlying followed a discrete random walk. At every step, the price could move upward or downward by fixed amounts, with an additional Gaussian noise component.

Options were cash-settled European calls and puts. The market maker was repeatedly asked to quote a bid and ask for each option while competing against other market makers.

The two core tasks were:

1. **Estimate the fair value of each option**
2. **Construct bid/ask quotes around that value while controlling risk**

The competition evaluated performance across multiple randomized sessions, so the strategy needed to perform consistently rather than rely on a single favorable path.

---

## Final Strategy

My final approach had two main components:

1. An **additive binomial option-pricing model**
2. A **volatility-scaled, inventory-aware market-making model**

I also tested a more active strategy that hedged with the underlying after fills. The hedge-based version was theoretically appealing, but it performed worse in the competition tests. I therefore kept the simpler inventory-aware quoting model as the final strategy.

---

## 1. Option Pricing

The simulator used additive price movements rather than the multiplicative movements normally assumed by the standard Cox-Ross-Rubinstein model.

For an underlying with current value \(S_0\):

- an up move adds \(u\),
- a down move subtracts \(d\).

After \(n\) steps, if \(k\) of those steps are upward moves, the terminal underlying value is

$$
S_T = S_0 + ku - (n-k)d
$$

### Risk-Neutral Probability

I used a zero-drift risk-neutral probability

$$
p = \frac{d}{u+d}
$$

with

$$
q = 1-p
$$

so that

$$
pu - qd = 0
$$

This gives a zero expected move under the simplified pricing model.

### Terminal Payoff

For a call option,

$$
C_T = \max(S_T-K, 0)
$$

and for a put option,

$$
P_T = \max(K-S_T, 0)
$$

where \(K\) is the strike price.

I calculated the payoff at every terminal node and then used backward induction:

$$
V_t = pV_{\text{up}} + qV_{\text{down}}
$$

until reaching the present option value.

Because the options were European-style, the model only needed to evaluate the payoff at expiration.

---

## 2. Volatility-Scaled Market Making

The pricing model produces a theoretical midpoint

$$
m = V_{\text{option}}
$$

The next problem is deciding how far away from that midpoint to place the bid and ask.

A quote that is too wide rarely trades. A quote that is too tight wins more order flow but increases adverse-selection and inventory risk.

My strategy therefore made the spread depend on the uncertainty remaining before expiration.

### Per-Step Variance

I estimated the per-step variance using the underlying's upward move, downward move, and Gaussian noise:

$$
\sigma_{\text{step}}^2
=
pu^2 + qd^2 + \sigma_{\text{noise}}^2
$$

The approximate uncertainty over the remaining lifetime of the option was then

$$
\sigma_{\text{total}}
=
\sqrt{n\sigma_{\text{step}}^2}
$$

where \(n\) is the number of steps until expiry.

This risk estimate becomes larger when:

- the underlying's possible moves are larger,
- the noise term is larger,
- or more time remains until expiration.

---

## 3. Base Spread

I centered the market around the model price and used a volatility-scaled half-spread:

$$
h_{\text{base}}
=
0.16\sigma_{\text{total}}
$$

The initial market is therefore approximately

$$
\text{bid} = m-h_{\text{base}}
$$

$$
\text{ask} = m+h_{\text{base}}
$$

The coefficient \(0.16\) was a tunable competition parameter rather than a theoretical constant. It controls the tradeoff between execution frequency and expected profit per trade.

---

## 4. Numerical Delta

I estimated each option's delta numerically by perturbing the underlying price slightly in both directions:

$$
\Delta
\approx
\frac{V(S+h)-V(S-h)}{2h}
$$

This finite-difference estimate provides a simple measure of how sensitive the option value is to movements in the underlying.

Using delta also makes the inventory adjustment more risk-aware: ten contracts of a low-delta option do not represent the same directional exposure as ten contracts of a high-delta option.

---

## 5. Inventory-Aware Quote Skew

A market maker should avoid continuously accumulating the same exposure.

I therefore adjusted the center of the quoted market according to the current option position and estimated delta.

The inventory skew was proportional to

$$
\text{skew}
=
0.02
\,
\sigma_{\text{total}}
\,
Q
\,
\Delta
$$

where \(Q\) is the current option inventory.

The effective half-spread was also widened as the absolute inventory skew increased:

$$
h
=
h_{\text{base}}
+
0.5|\text{skew}|
$$

The final quote was then

$$
\text{bid}
=
\max(0,\;m-h-\text{skew})
$$

$$
\text{ask}
=
\max(\text{bid}+\varepsilon,\;m+h-\text{skew})
$$

This produces useful behavior automatically:

- If inventory becomes too long, the quoted market shifts downward.
- If inventory becomes too short, the quoted market shifts upward.
- Higher-volatility options receive wider markets.
- Longer-dated options receive wider markets.
- Low-risk or near-expiry options receive tighter markets.

---

## Alternative Strategy: Fill-by-Fill Underlying Hedging

I also tested a second approach using the optional fill callbacks.

After a bid or offer was hit, the strategy attempted to offset some of the newly acquired option exposure by trading the underlying.

Conceptually:

```python
def on_bid_hit(...):
    update_option_position()
    estimate_exposure()
    trade_underlying_to_reduce_exposure()

def on_offer_hit(...):
    update_option_position()
    estimate_exposure()
    trade_underlying_to_reduce_exposure()
```

The motivation was standard delta-risk management: if an option position creates directional exposure, an offsetting underlying position can reduce the sensitivity of total P&L to the next price move.

In an idealized setting, the portfolio target would be approximately

$$
\Delta_{\text{portfolio}}
=
\Delta_{\text{options}}
+
Q_{\text{underlying}}
\approx 0
$$

and a partial hedge could be expressed as

$$
Q_{\text{hedge}}
=
-\lambda\Delta_{\text{options}}
$$

for some hedge fraction \(0 < \lambda \le 1\).

---

## Why I Did Not Use the Hedge-Based Version

The hedge-based implementation performed **worse in the competition tests** than the inventory-aware quoting strategy.

The main issue was that active hedging introduced another source of P&L. A hedge is beneficial only if the option exposure is estimated accurately and the hedge size is appropriate. Otherwise, it can turn relatively controlled option inventory into an additional directional position in the underlying.

In testing, the hedge-based version could:

- react too strongly to individual fills,
- create unnecessary underlying exposure,
- increase the variance of session P&L,
- compound errors across repeated trades,
- and increase bankruptcy risk.

Since the competition score rewarded consistent session performance and penalized bankruptcies, this mattered more than making the strategy theoretically more sophisticated.

The final version therefore used **inventory-aware quote skewing instead of automatic fill-by-fill hedging**, because that version produced better empirical test performance.

This was one of the most useful lessons from the challenge:

> **A model improvement should be judged by out-of-sample performance, not by theoretical complexity alone.**

---

## Implementation Flow

```text
Current underlying state
        |
        v
Additive binomial tree
        |
        v
Theoretical option value
        |
        v
Estimate remaining volatility
        |
        v
Estimate option delta
        |
        v
Measure current inventory
        |
        v
Compute spread + inventory skew
        |
        v
Return bid / ask
```

---

## Final Strategy Pseudocode

```python
mid = price_option(option)

variance = (
    p * up_move ** 2
    + q * down_move ** 2
    + noise_std ** 2
)

remaining_volatility = sqrt(
    steps_until_expiry * variance
)

base_half_spread = 0.16 * remaining_volatility

delta = (
    price_option_at_S_plus_h
    - price_option_at_S_minus_h
) / (2 * h)

inventory_skew = (
    0.02
    * remaining_volatility
    * option_position
    * delta
)

half_spread = (
    base_half_spread
    + 0.5 * abs(inventory_skew)
)

bid = max(
    0,
    mid - half_spread - inventory_skew
)

ask = max(
    bid + epsilon,
    mid + half_spread - inventory_skew
)
```

---

## Key Technical Ideas

The project combines several concepts used in quantitative trading:

- discrete-time stochastic processes,
- binomial option pricing,
- risk-neutral valuation,
- backward induction,
- European option payoffs,
- finite-difference Greeks,
- volatility estimation,
- inventory-aware market making,
- spread optimization,
- experimental strategy comparison,
- and risk/reward tuning under randomized simulation.

The most important part of the challenge was not implementing the pricing formula itself, but translating a theoretical fair value into a quoting strategy that remained competitive across many simulated market paths.

---

## What I Learned

**Pricing and market making are different problems.**  
A good estimate of fair value does not automatically produce a profitable trading strategy.

**Risk management can matter more than model complexity.**  
A simpler strategy that survives difficult paths can outperform one that adds theoretically attractive but noisy hedging logic.

**Inventory should influence price.**  
Continuing to quote symmetrically while accumulating exposure creates unnecessary risk.

**Model changes need to be evaluated empirically.**  
The active hedge implementation appeared stronger in theory, but competition testing showed that the inventory-skew strategy performed better.

**Simple models can be effective when they match the simulation.**  
The additive binomial tree closely matched the underlying dynamics and was computationally inexpensive enough to evaluate repeatedly during market making.

---

## Result

**Top 10 Finalist — Akuna Capital Quant Trading Competition**

The competition result led directly to a final-round interview for Akuna Capital's **2026 Junior Quant Developer & Strategist** position.

---

## Disclaimer

This repository is intended as a portfolio description of my own quantitative modeling and market-making work. Competition-provided proprietary infrastructure, hidden tests, and confidential materials are not reproduced here.

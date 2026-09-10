# Akuna Capital Quant Trading Competition — Options Market Making

## Overview

This project documents my market-making strategy for Akuna Capital's quantitative trading competition. The challenge involved pricing European-style options on simulated underlyings and continuously quoting bid/ask markets against competing market makers.

The objective was not simply to estimate fair value. A successful strategy also had to balance quote competitiveness, option inventory, volatility, time to expiry, adverse selection, and bankruptcy risk.

I finished as a **Top 10 finalist** and advanced directly to the final-round interview for Akuna Capital's **2026 Junior Quant Developer & Strategist** role.

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

- an up move adds \(u\)
- a down move subtracts \(d\)

After \(n\) steps, if \(k\) of those steps are upward moves, the terminal underlying value is:

$$
S_T = S_0 + ku - (n-k)d
$$

### Risk-Neutral Probability

I used a zero-drift risk-neutral probability:

$$
p = \frac{d}{u+d}
$$

with:

$$
q = 1-p
$$

so that:

$$
pu - qd = 0
$$

This gives a zero expected move under the simplified pricing model.

### Terminal Payoff

For a call option:

$$
C_T = \max(S_T-K, 0)
$$

For a put option:

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

The pricing model produces a theoretical midpoint:

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

The approximate uncertainty over the remaining lifetime of the option was:

$$
\sigma_{\text{total}}
=
\sqrt{n\sigma_{\text{step}}^2}
$$

where \(n\) is the number of steps until expiry.

This risk estimate becomes larger when the underlying's possible moves are larger, the noise term is larger, or more time remains until expiration.

---

## 3. Base Spread

I centered the market around the model price and used a volatility-scaled half-spread:

$$
h_{\text{base}}
=
0.16\sigma_{\text{total}}
$$

The initial market is therefore approximately:

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

The inventory skew was proportional to:

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

The final quote was then:

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

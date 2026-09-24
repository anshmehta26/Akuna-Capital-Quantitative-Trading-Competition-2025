# Akuna Capital Quant Trading Competition — Options Market Making

## Result

**Top 10 Finalist — Akuna Capital Quant Trading Competition**

The competition result led directly to a final-round interview for Akuna Capital's **2026 Junior Quant Developer & Strategist** position.

---

## Verification

Proof of results is available in this [Google Drive folder](https://drive.google.com/drive/folders/1KVhutssEUYTBR5nzS5x-9TCZ4-Jmc9Wo?usp=sharing). It contains:

- A congratulatory email from an Akuna Capital recruiter for my **Top 10 worldwide** placement in the Akuna Capital 2025 Quantitative Trading Challenge 

---

## Overview

This project documents my market-making strategy for Akuna Capital's quantitative trading competition. The challenge involved pricing European-style options on simulated underlyings and continuously quoting bid/offer markets against competing market makers.

The objective was not simply to estimate fair value. A successful strategy also had to balance:

- quote competitiveness
- option inventory
- volatility
- time to expiry
- adverse selection
- bankruptcy risk

My final strategy combined an **additive binomial option-pricing model** with **volatility-scaled, inventory-aware market making**.

I also experimented with active underlying hedging after trades. Although theoretically attractive, the hedge-based approach performed worse during competition testing, so I retained the inventory-aware quoting strategy.

> This repository documents my own pricing and market-making logic. Competition-provided infrastructure, private test cases, and confidential materials are not reproduced.

---

## Competition Interface

Akuna provided the simulation environment and a `BaseMarketMaker` class responsible for exchange interaction, position bookkeeping, and maintaining the current market state.

My implementation inherited from that framework:

```python
class MarketMaker(BaseMarketMaker):
    ...
```

The two primary methods I was responsible for implementing were:

- `price_option(option)` — estimate the theoretical value of an option
- `make_market(option)` — return a `(bid, offer)` quote for that option

The framework also exposed optional event callbacks:

- `on_bid_hit(...)` — called when another participant sells into my bid, meaning my market maker buys the option
- `on_offer_hit(...)` — called when another participant buys at my offer, meaning my market maker sells the option
- `on_step_advance(...)` — called after the simulation advances to the next time step

The base framework maintained the current underlying states, active option contracts, positions, and trade bookkeeping.

---

## Simulation Loop

Each session contained one or more underlyings and options and ran for a fixed number of discrete time steps.

At each step:

1. The exchange requested quotes from every market maker.
2. Each market maker returned a bid and offer.
3. Buy orders were matched with the lowest offer and sell orders with the highest bid.
4. The underlying prices advanced according to the simulated random walk.
5. Expiring options were cash-settled and P&L was recorded.
6. Each market maker received the updated state for the next step.

This meant the strategy repeatedly had to solve two related problems:

**What is the option worth?**

and

**How aggressively should I trade around that value?**

---

## Final Strategy

The final strategy had two main components:

1. **Additive binomial option pricing**
2. **Volatility-scaled, inventory-aware bid/offer generation**

The pricing model produced a theoretical fair value, while the market-making layer determined how far from that value to quote based on risk.

---

## 1. Option Pricing

The simulator used additive price movements rather than the multiplicative movements normally assumed by the standard Cox-Ross-Rubinstein model.

For an underlying with current value $S_0$:

- an up move adds $u$
- a down move subtracts $d$

After $n$ steps, if $k$ of those steps are upward moves, the terminal underlying value is:

```math
S_T = S_0 + ku - (n-k)d
```

### Risk-Neutral Probability

I used a zero-drift risk-neutral probability:

```math
p = \frac{d}{u+d}
```

with:

```math
q = 1-p
```

so that:

```math
pu - qd = 0
```

This matches the zero-drift assumption of the simplified underlying process.

### Terminal Payoff

For a call option:

```math
C_T = \max(S_T-K, 0)
```

For a put option:

```math
P_T = \max(K-S_T, 0)
```

where $K$ is the strike price.

I computed the payoff at each terminal node and then worked backward through the tree using:

```math
V_t = pV_{\text{up}} + qV_{\text{down}}
```

until reaching the present option value.

Because the options were European-style and cash-settled, only the payoff at expiry needed to be considered.

---

## 2. Volatility-Scaled Market Making

The pricing model produces a theoretical midpoint:

```math
m = V_{\text{option}}
```

The next problem is determining the bid/offer spread around that midpoint.

A market that is too wide rarely trades.

A market that is too tight wins more order flow but increases adverse-selection and inventory risk.

I therefore scaled the spread according to the uncertainty remaining before expiration.

### Per-Step Variance

I estimated the per-step variance using the upward move, downward move, and Gaussian noise:

```math
\sigma_{\text{step}}^2
=
pu^2 + qd^2 + \sigma_{\text{noise}}^2
```

The approximate uncertainty over the remaining lifetime of the option was:

```math
\sigma_{\text{total}}
=
\sqrt{n\sigma_{\text{step}}^2}
```

where $n$ is the number of steps until expiry.

The resulting spread therefore increased when:

- underlying moves became larger
- Gaussian noise increased
- more time remained until expiration

---

## 3. Base Spread

I used the option's theoretical value as the center of the market and applied a volatility-scaled half-spread:

```math
h_{\text{base}}
=
0.16\sigma_{\text{total}}
```

giving an initial market approximately equal to:

```math
\text{bid}
=
m-h_{\text{base}}
```

```math
\text{offer}
=
m+h_{\text{base}}
```

The coefficient $0.16$ was a tunable competition parameter rather than a theoretical constant.

It controlled the tradeoff between quote competitiveness and compensation for taking risk.

---

## 4. Numerical Delta

I estimated option delta numerically by slightly perturbing the underlying value in both directions:

```math
\Delta
\approx
\frac{V(S+h)-V(S-h)}{2h}
```

This finite-difference estimate measures the sensitivity of the option price to a change in the underlying.

Using delta made the inventory adjustment more risk-aware: the same number of contracts can represent very different exposure depending on the option's sensitivity to the underlying.

---

## 5. Inventory-Aware Quote Skew

Continuing to quote symmetrically while accumulating a large position can create unnecessary risk.

I therefore shifted my quotes according to both current inventory and estimated delta.

The inventory skew was:

```math
\text{skew}
=
0.02
\,
\sigma_{\text{total}}
\,
Q
\,
\Delta
```

where $Q$ represents the current option position.

The effective half-spread was also widened as inventory risk increased:

```math
h
=
h_{\text{base}}
+
0.5|\text{skew}|
```

The final quotes became:

```math
\text{bid}
=
\max(0,\;m-h-\text{skew})
```

```math
\text{offer}
=
\max(\text{bid}+\varepsilon,\;m+h-\text{skew})
```

This created several useful behaviors:

- Long inventory shifted the market downward, discouraging additional purchases.
- Short inventory shifted the market upward, encouraging purchases and discouraging additional sales.
- High-volatility options received wider markets.
- Options with more time remaining received wider markets.
- Lower-risk and near-expiry options received tighter markets.

---

## Alternative Strategy — Underlying Hedging

I also experimented with using the fill callbacks to hedge option exposure by trading the underlying.

Conceptually:

```python
def on_bid_hit(...):
    update_position()
    estimate_exposure()
    hedge_with_underlying()

def on_offer_hit(...):
    update_position()
    estimate_exposure()
    hedge_with_underlying()
```

The theoretical objective of delta hedging is to move total portfolio exposure toward:

```math
\Delta_{\text{portfolio}}
=
\Delta_{\text{options}}
+
Q_{\text{underlying}}
\approx 0
```

A partial hedge could therefore be represented as:

```math
Q_{\text{hedge}}
=
-\lambda\Delta_{\text{options}}
```

where:

```math
0 < \lambda \le 1
```

---

## Why I Chose the Inventory-Skew Strategy

The hedge-based version appeared more sophisticated theoretically, but it produced **worse performance in competition testing**.

Trading the underlying after individual fills introduced an additional source of P&L variance. If exposure estimates or hedge sizing were imperfect, the hedge itself could become a directional position.

During testing, the approach could:

- react too aggressively to individual trades
- create unnecessary underlying exposure
- amplify P&L swings
- compound positioning errors
- increase bankruptcy risk

Because the scoring system rewarded consistent performance across randomized sessions and penalized bankruptcies, the simpler inventory-aware quoting strategy performed better.

I therefore used the strategy that produced the stronger empirical results rather than choosing the more complex model solely because it was theoretically appealing.

> **A model improvement should be judged by empirical performance, not by complexity alone.**

---

## Strategy Flow

```text
Current underlying state
        |
        v
Additive binomial model
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
Return bid / offer
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

offer = max(
    bid + epsilon,
    mid + half_spread - inventory_skew
)
```

---

## Key Technical Concepts

This project involved:

- Discrete-time stochastic processes
- Binomial option pricing
- Risk-neutral valuation
- Backward induction
- European option payoffs
- Finite-difference Greeks
- Volatility estimation
- Inventory-aware market making
- Dynamic bid/offer spreads
- Risk management
- Experimental strategy comparison
- Optimization under randomized simulation

---

## What I Learned

**Pricing and market making are separate problems.**

Estimating fair value correctly does not automatically produce a profitable trading strategy.

**Inventory should influence quotes.**

Continuing to quote symmetrically while accumulating exposure can substantially increase risk.

**Risk management can matter more than complexity.**

The more sophisticated hedge-based approach performed worse than the simpler inventory-aware strategy.

**Simulation results should drive strategy selection.**

I iterated on the strategy based on observed test performance rather than assuming that additional mathematical sophistication would necessarily improve results.

**Simple models can work well when they match the environment.**

The additive binomial model closely matched the structure of the simulated underlying process while remaining computationally inexpensive enough to evaluate repeatedly.

---

## Repository Structure

```text
Akuna-Capital-Quantitative-Trading-Competition-2025/
├── README.md
├── market_maker.py
└── binomial_pricing_model.py
```

`market_maker.py` contains the quoting and inventory-management strategy.

`binomial_pricing_model.py` contains the option-pricing implementation.

The competition-provided `BaseMarketMaker`, exchange simulator, and supporting data structures are intentionally not reproduced.

---

## Disclaimer

This repository is intended as a portfolio description of my own quantitative modeling and market-making work. Competition-provided proprietary infrastructure, hidden test cases, and confidential materials are not included.

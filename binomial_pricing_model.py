def price_option(self, option: Option) -> float:
    """
    Prices a European call/put using an additive binomial model.
    Assumptions per prompt:
      - Discrete steps (+u or -d) with zero expected drift
      - No early exercise, cash-settled at expiry
      - No discounting (r ~ 0)
      - Gaussian noise has mean 0 -> ignored for the recombining tree
    """
    # --- find the underlying for this option ---
    U = next(u for u in self.underlying_state
             if u.underlying_id == option.underlying_id)

    S0 = U.valuation
    u_step = float(U.up_move_step)
    d_step = float(U.down_move_step)
    n = int(option.steps_until_expiry)
    K = float(option.strike)

    if n <= 0:
        # already at expiry
        if option.option_type.name.lower() == "call":
            return max(S0 - K, 0.0)
        else:
            return max(K - S0, 0.0)

    # --- risk-neutral up probability ---
    # The spec enforces E[M]=0 with up_prob + down_prob = 1,
    # which implies p*u = (1-p)*d -> p = d/(u + d)
    # (use given prob if present & consistent; fall back to zero-drift p)
    p_zero_drift = d_step / (u_step + d_step) if (u_step + d_step) != 0 else 0.5
    p_given = float(getattr(U, "up_move_probability", p_zero_drift))
    # choose the one that keeps us in [0,1] and close to zero-drift
    p = min(1.0, max(0.0, p_zero_drift if 0.0 <= p_zero_drift <= 1.0 else p_given))
    q = 1.0 - p

    # --- terminal payoffs (additive tree) ---
    # After n steps with k ups, price = S0 + k*u - (n-k)*d
    # We’ll compute terminal node payoffs and roll back.
    # V[i] will hold payoffs at time layer i (from the end)
    V = [0.0] * (n + 1)
    is_call = option.option_type.name.lower() == "call"

    for k in range(n + 1):
        St = S0 + k * u_step - (n - k) * d_step
        if is_call:
            V[k] = max(St - K, 0.0)
        else:
            V[k] = max(K - St, 0.0)

    # --- backward induction (no discounting) ---
    for t in range(n - 1, -1, -1):
        for k in range(t + 1):
            V[k] = p * V[k + 1] + q * V[k]

    return V[0]
class MarketMaker(BaseMarketMaker):

    @property
    def name(self) -> str:
        return "Ansh Mehta"


    def _price_from_spot(self, option: Option, S0: float) -> float:
        U = next(
            u for u in self.underlying_state
            if u.underlying_id == option.underlying_id
        )

        u = float(U.up_move_step)
        d = float(U.down_move_step)
        n = int(option.steps_until_expiry)
        K = float(option.strike)

        is_call = option.option_type.name.lower() == "call"

        if n <= 0:
            if is_call:
                return max(S0 - K, 0.0)
            return max(K - S0, 0.0)

        p = float(U.up_move_probability)
        q = float(U.down_move_probability)

        total_probability = p + q

        if total_probability != 0:
            p /= total_probability
            q /= total_probability
        else:
            p = 0.5
            q = 0.5

        V = [0.0] * (n + 1)

        for k in range(n + 1):
            St = S0 + k * u - (n - k) * d

            if is_call:
                V[k] = max(St - K, 0.0)
            else:
                V[k] = max(K - St, 0.0)

        for t in range(n - 1, -1, -1):
            for k in range(t + 1):
                V[k] = p * V[k + 1] + q * V[k]

        return V[0]


    def price_option(self, option: Option) -> float:
        U = next(
            u for u in self.underlying_state
            if u.underlying_id == option.underlying_id
        )

        return self._price_from_spot(
            option,
            float(U.valuation)
        )


    def make_market(
        self,
        option: Option
    ) -> tuple[float, float]:

        U = next(
            u for u in self.underlying_state
            if u.underlying_id == option.underlying_id
        )

        mid = float(self.price_option(option))

        n = max(
            1,
            int(option.steps_until_expiry)
        )

        p = float(U.up_move_probability)
        q = float(U.down_move_probability)

        total_probability = p + q

        if total_probability != 0:
            p /= total_probability
            q /= total_probability
        else:
            p = 0.5
            q = 0.5

        variance = (
            p * float(U.up_move_step) ** 2
            + q * float(U.down_move_step) ** 2
            + float(U.noise_std_dev) ** 2
        )

        std_total = (n * variance) ** 0.5

        base_half_spread = (
            0.16 * std_total
            + 1e-6
        )

        S0 = float(U.valuation)

        h = max(
            1e-5,
            0.25 * (
                abs(float(U.up_move_step))
                + abs(float(U.down_move_step))
                + float(U.noise_std_dev)
            )
        )

        S_up = S0 + h
        S_down = max(0.0, S0 - h)

        price_up = self._price_from_spot(
            option,
            S_up
        )

        price_down = self._price_from_spot(
            option,
            S_down
        )

        if S_up != S_down:
            delta = (
                price_up - price_down
            ) / (
                S_up - S_down
            )
        else:
            delta = 0.0

        inventory = getattr(
            self,
            "_option_inventory",
            {}
        )

        qty = float(
            inventory.get(
                option.option_id,
                0.0
            )
        )

        skew = (
            0.02
            * std_total
            * qty
            * delta
        )

        half_spread = (
            base_half_spread
            + 0.5 * abs(skew)
        )

        bid = max(
            0.0,
            mid
            - half_spread
            - skew
        )

        ask = max(
            bid + 1e-6,
            mid
            + half_spread
            - skew
        )

        return bid, ask


    def on_bid_hit(
        self,
        option: Option,
        bid_price: float
    ) -> None:

        super().on_bid_hit(
            option,
            bid_price
        )

        if not hasattr(
            self,
            "_option_inventory"
        ):
            self._option_inventory = {}

        self._option_inventory[
            option.option_id
        ] = (
            self._option_inventory.get(
                option.option_id,
                0.0
            )
            + 1.0
        )


    def on_offer_hit(
        self,
        option: Option,
        offer_price: float
    ) -> None:

        super().on_offer_hit(
            option,
            offer_price
        )

        if not hasattr(
            self,
            "_option_inventory"
        ):
            self._option_inventory = {}

        self._option_inventory[
            option.option_id
        ] = (
            self._option_inventory.get(
                option.option_id,
                0.0
            )
            - 1.0
        )


    def on_step_advance(
        self,
        new_underlying_state: list[Underlying],
        new_option_state: list[Option]
    ) -> None:

        super().on_step_advance(
            new_underlying_state,
            new_option_state
        )

        if hasattr(
            self,
            "_option_inventory"
        ):
            active_ids = {
                option.option_id
                for option in new_option_state
            }

            self._option_inventory = {
                option_id: quantity
                for option_id, quantity
                in self._option_inventory.items()
                if option_id in active_ids
            }
from models import Asset, Contract, Contracts, Balances, PartyName


class Ledger:
    """
    Wraps Manager().dict() proxies for balances and contracts.

    All mutating methods reassign the top-level key rather than mutating nested
    values in place — this is required so the Manager server process sees changes.
    (proxy["key"]["nested"] = x does NOT propagate; proxy["key"] = new_dict does.)
    """

    def __init__(self, balances: Balances, contracts: Contracts) -> None:
        self._balances = balances
        self._contracts = contracts

    # --- Balance helpers ---

    def get_balance(self, party: PartyName, asset: Asset) -> float:
        return self._balances.get(party, {}).get(asset, 0.0)

    def debit(self, party: PartyName, asset: Asset, amount: float) -> None:
        """Deduct funds from a party. Raises ValueError if insufficient."""
        snapshot = dict(self._balances.get(party, {}))
        current = snapshot.get(asset, 0.0)
        if current < amount:
            raise ValueError(
                f"{party} has insufficient {asset}: {current:.1f} < {amount:.1f}"
            )
        snapshot[asset] = current - amount
        self._balances[party] = snapshot

    def credit(self, party: PartyName, asset: Asset, amount: float) -> None:
        """Add funds to a party's balance."""
        snapshot = dict(self._balances.get(party, {}))
        snapshot[asset] = snapshot.get(asset, 0.0) + amount
        self._balances[party] = snapshot

    def snapshot_balances(self) -> dict[str, dict[str, float]]:
        """Return a plain str-keyed copy (not a proxy) suitable for printing."""
        return {
            party.value: {asset.value: amount for asset, amount in coins.items()}
            for party, coins in self._balances.items()
        }

    # --- Contract helpers ---

    def add_contract(self, contract: Contract) -> None:
        """Lock sender's funds and register the contract."""
        self.debit(contract["sender"], contract["asset"], contract["amount"])
        self._contracts[contract["contract_id"]] = contract

    def get_contract(self, contract_id: str) -> Contract | None:
        return self._contracts.get(contract_id)

    def update_contract(self, contract: Contract) -> None:
        """Write back an updated contract dict. Must reassign the top-level key."""
        self._contracts[contract["contract_id"]] = contract

    def settle_redeem(self, contract: Contract) -> None:
        """Credit receiver and write back REDEEMED contract."""
        self.credit(contract["receiver"], contract["asset"], contract["amount"])
        self.update_contract(contract)

    def settle_refund(self, contract: Contract) -> None:
        """Return funds to sender and write back REFUNDED contract."""
        self.credit(contract["sender"], contract["asset"], contract["amount"])
        self.update_contract(contract)

    def snapshot_contracts(self) -> list[dict]:
        """Return a plain-list copy of all contracts."""
        return [dict(c) for c in self._contracts.values()]

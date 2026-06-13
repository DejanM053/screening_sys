"""Tether/Circle on-chain blacklist checks (Section 11.1, 11.2).

Read-only RPC queries only — no private keys, no signing. If the chain
client library is unavailable or the RPC call fails (e.g. no network access
in this environment), the check fails safe to `frozen=False` rather than
blocking the screening pipeline.
"""
from __future__ import annotations

import logging

from app.config import settings
from app.models import IssuerBlacklistResult

logger = logging.getLogger("crypto-screener.issuer_blacklist")

# isBlackListed(address) / isBlacklisted(address) selectors (TRC-20 / ERC-20)
_TRON_BLACKLIST_FN = "isBlackListed"
_ETH_USDT_BLACKLIST_FN = "isBlackListed"
_ETH_USDC_BLACKLIST_FN = "isBlacklisted"


class IssuerBlacklistChecker:
    async def check(self, address: str, chain: str, stablecoin: str) -> IssuerBlacklistResult:
        chain = chain.lower()
        stablecoin = stablecoin.upper()

        if chain == "tron" and stablecoin == "USDT":
            return await self._check_tron_usdt(address)
        if chain == "ethereum" and stablecoin == "USDT":
            return await self._check_eth_contract(
                address, settings.usdt_eth_contract, _ETH_USDT_BLACKLIST_FN, issuer="tether"
            )
        if chain == "ethereum" and stablecoin == "USDC":
            return await self._check_eth_contract(
                address, settings.usdc_eth_contract, _ETH_USDC_BLACKLIST_FN, issuer="circle"
            )

        return IssuerBlacklistResult(frozen=False, chain=chain, issuer=None)

    async def _check_tron_usdt(self, address: str) -> IssuerBlacklistResult:
        try:
            from tronpy import Tron  # type: ignore

            client = Tron(network="mainnet")
            contract = client.get_contract(settings.usdt_tron_contract)
            frozen = bool(contract.functions.get(_TRON_BLACKLIST_FN)(address))
            return IssuerBlacklistResult(frozen=frozen, chain="tron", issuer="tether")
        except Exception as exc:  # pragma: no cover - exercised only without network/tronpy
            logger.warning("TRON USDT blacklist check unavailable for %s: %s", address, exc)
            return IssuerBlacklistResult(frozen=False, chain="tron", issuer="tether")

    async def _check_eth_contract(
        self, address: str, contract_address: str, fn_name: str, issuer: str
    ) -> IssuerBlacklistResult:
        try:
            from web3 import Web3  # type: ignore

            w3 = Web3(Web3.HTTPProvider(settings.ethereum_rpc_url))
            abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_account", "type": "address"}],
                    "name": fn_name,
                    "outputs": [{"name": "", "type": "bool"}],
                    "type": "function",
                }
            ]
            contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)
            frozen = bool(getattr(contract.functions, fn_name)(Web3.to_checksum_address(address)).call())
            return IssuerBlacklistResult(frozen=frozen, chain="ethereum", issuer=issuer)
        except Exception as exc:  # pragma: no cover - exercised only without network/web3
            logger.warning("Ethereum %s blacklist check unavailable for %s: %s", issuer, address, exc)
            return IssuerBlacklistResult(frozen=False, chain="ethereum", issuer=issuer)

"""Tether/Circle on-chain blacklist checks via direct HTTP (no tronpy/web3 required).

TronGrid: JSON-RPC eth_call at /jsonrpc — calls isBlackListed(address) on USDT-TRON contract
Etherscan: V2 proxy eth_call with ABI-encoded selector

Fails safe to frozen=False on any error so the screening pipeline always completes.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.models import IssuerBlacklistResult

logger = logging.getLogger("crypto-screener.issuer_blacklist")

# isBlackListed(address) function selectors
_USDT_SELECTOR = "0x26758a48"   # USDT TRON + ETH
_USDC_SELECTOR = "0xfe575a87"   # USDC ETH


def _tron_b58_to_hex(addr: str) -> str:
    """Base58Check decode a TRON address → 20-byte hex (no 0x41 prefix)."""
    ALPHA = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for ch in addr:
        n = n * 58 + ALPHA.index(ch)
    raw = n.to_bytes(25, "big")      # 1-byte version + 20-byte addr + 4-byte checksum
    return raw[1:21].hex()           # drop version byte and checksum


def _eth_encode_address(address: str) -> str:
    """ABI-encode an Ethereum address: pad to 32 bytes."""
    return address.lower().replace("0x", "").zfill(64)


class IssuerBlacklistChecker:
    async def check(self, address: str, chain: str, stablecoin: str) -> IssuerBlacklistResult:
        chain = chain.lower()
        stablecoin = stablecoin.upper()

        if chain == "tron" and stablecoin == "USDT":
            return await self._trongrid_blacklist(address)
        if chain == "ethereum" and stablecoin == "USDT":
            return await self._etherscan_blacklist(address, settings.usdt_eth_contract, _USDT_SELECTOR, "tether")
        if chain == "ethereum" and stablecoin == "USDC":
            return await self._etherscan_blacklist(address, settings.usdc_eth_contract, _USDC_SELECTOR, "circle")

        return IssuerBlacklistResult(frozen=False, chain=chain, issuer=None)

    async def _trongrid_blacklist(self, address: str) -> IssuerBlacklistResult:
        try:
            # Convert TRON base58 address to 20-byte hex for ABI encoding
            addr_hex = _tron_b58_to_hex(address)
            contract_hex = "0x" + _tron_b58_to_hex(settings.usdt_tron_contract)
            calldata = _USDT_SELECTOR + "000000000000000000000000" + addr_hex

            headers = {"Content-Type": "application/json"}
            if settings.trongrid_api_key:
                headers["TRON-PRO-API-KEY"] = settings.trongrid_api_key

            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{settings.tron_rpc_url}/jsonrpc",
                    json={
                        "jsonrpc": "2.0",
                        "method": "eth_call",
                        "params": [{"to": contract_hex, "data": calldata}, "latest"],
                        "id": 1,
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                result = data.get("result", "0x")
                # 32-byte result: non-zero = blacklisted; revert = not blacklisted
                frozen = bool(result and result != "0x" and int(result, 16) != 0)
                return IssuerBlacklistResult(frozen=frozen, chain="tron", issuer="tether")

        except Exception as exc:
            logger.warning("TronGrid isBlackListed check failed for %s: %s", address, exc)
            return IssuerBlacklistResult(frozen=False, chain="tron", issuer="tether")

    async def _etherscan_blacklist(
        self, address: str, contract: str, selector: str, issuer: str
    ) -> IssuerBlacklistResult:
        try:
            data = selector + _eth_encode_address(address)
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    f"{settings.etherscan_api_url}/api",
                    params={
                        "chainid": "1",
                        "module": "proxy",
                        "action": "eth_call",
                        "to": contract,
                        "data": data,
                        "apikey": settings.etherscan_api_key,
                    },
                )
                resp.raise_for_status()
                result = resp.json().get("result", "0x")
                frozen = int(result, 16) != 0 if result and result != "0x" else False
                return IssuerBlacklistResult(frozen=frozen, chain="ethereum", issuer=issuer)

        except Exception as exc:
            logger.warning("Etherscan %s blacklist check failed for %s: %s", issuer, address, exc)
            return IssuerBlacklistResult(frozen=False, chain="ethereum", issuer=issuer)

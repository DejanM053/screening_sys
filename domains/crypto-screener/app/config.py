from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379"
    audit_trail_url: str = "http://audit-trail:8008"
    regulatory_engine_url: str = "http://regulatory-engine:8003"

    tron_rpc_url: str = "https://api.trongrid.io"
    ethereum_rpc_url: str = "https://eth.llamarpc.com"
    tronscan_api_url: str = "https://apilist.tronscanapi.com"
    etherscan_api_url: str = "https://api.etherscan.io"
    etherscan_api_key: str = ""

    # TRC-20 USDT contract on TRON (Section 11.2)
    usdt_tron_contract: str = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    # ERC-20 USDT contract on Ethereum
    usdt_eth_contract: str = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    # USDC contract on Ethereum (Circle)
    usdc_eth_contract: str = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"

    hop_cache_ttl_seconds: int = 24 * 60 * 60
    freeze_register_ttl_seconds: int = 90 * 24 * 60 * 60

    class Config:
        env_file = ".env"


settings = Settings()

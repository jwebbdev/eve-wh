"""Fetch ore and ice prices from EVE ESI public market API."""
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

# The Forge region (Jita)
FORGE_REGION_ID = 10000002
JITA_STATION_ID = 60003760

# Cache — 1 hour for ore prices (less volatile than gas)
_price_cache: dict | None = None
_cache_time: float = 0
_cache_updated_at: str = ""
CACHE_TTL = 3600  # 1 hour

DATA_DIR = Path(__file__).parent.parent / "data"


def _load_ore_type_info() -> dict[str, dict]:
    """Load ore/ice name → {type_id, volume} mapping from YAML."""
    path = DATA_DIR / "ore_types.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    mapping = {}
    for ore in data.get("ore_types", []):
        mapping[ore["name"]] = {"type_id": ore["type_id"], "volume": ore["volume"]}
    for ice in data.get("ice_types", []):
        mapping[ice["name"]] = {"type_id": ice["type_id"], "volume": ice["volume"]}
    return mapping


def fetch_ore_prices(force_refresh: bool = False) -> tuple[dict, str]:
    """Fetch current Jita ore/ice prices (buy and sell) from ESI.

    Returns:
        Tuple of (prices dict, updated_at ISO string).
        Prices dict: {ore_name: {"buy": float, "sell": float}}
        Falls back to stale cache on error.
    """
    global _price_cache, _cache_time, _cache_updated_at

    if not force_refresh and _price_cache and (time.time() - _cache_time) < CACHE_TTL:
        return _price_cache, _cache_updated_at

    ore_info = _load_ore_type_info()
    prices = {}

    for name, info in ore_info.items():
        type_id = info["type_id"]
        volume = info["volume"]
        buy_price = 0.0
        sell_price = 0.0

        try:
            url = (
                f"https://esi.evetech.net/latest/markets/{FORGE_REGION_ID}/orders/"
                f"?type_id={type_id}&order_type=sell&datasource=tranquility"
            )
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            orders = resp.json()
            jita_orders = [o for o in orders if o.get("location_id") == JITA_STATION_ID]
            if not jita_orders:
                jita_orders = orders
            if jita_orders:
                sell_price = min(o["price"] for o in jita_orders)
        except Exception:
            pass

        try:
            url = (
                f"https://esi.evetech.net/latest/markets/{FORGE_REGION_ID}/orders/"
                f"?type_id={type_id}&order_type=buy&datasource=tranquility"
            )
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            orders = resp.json()
            jita_orders = [o for o in orders if o.get("location_id") == JITA_STATION_ID]
            if not jita_orders:
                jita_orders = orders
            if jita_orders:
                buy_price = max(o["price"] for o in jita_orders)
        except Exception:
            pass

        prices[name] = {"buy": round(buy_price, 2), "sell": round(sell_price, 2), "volume": volume}

    updated_at = datetime.now(timezone.utc).isoformat()

    valid = any(p["buy"] > 0 or p["sell"] > 0 for p in prices.values())
    if valid:
        _price_cache = prices
        _cache_time = time.time()
        _cache_updated_at = updated_at

    if _price_cache:
        return _price_cache, _cache_updated_at

    return prices, updated_at

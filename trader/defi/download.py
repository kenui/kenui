"""Download pool snapshot history. Usage: python -m defi.download [days] [step_seconds]"""
import sys
import time

from .chain import download_pool

AERO_EXTRA = ["3ab04b20", "57806ada", "ddca3f43"]  # stakedLiquidity, rewardGrowthGlobalX128, fee

POOLS = {
    # name: (address, token0 decimals, token1 decimals, fee, tick spacing, is_aerodrome)
    "uni_weth_usdc_005": ("0xd0b53d9277642d899df5c87a3966a349a798f224", 18, 6, 0.0005, 10, False),
    # token0 is USDC here, so prices and back-test values for this pool are in BTC, not USD
    "uni_cbbtc_usdc_005": ("0xfbb6eed8e7aa03b138556eedaf5d271a5e1e43ef", 6, 8, 0.0005, 10, False),
    "uni_weth_usdc_030": ("0x6c561b446416e1a00e8e93e221854d6ea4171372", 18, 6, 0.003, 60, False),
    "aero_weth_usdc_old": ("0xb2cc224c1c9feE385f8ad6a55b4d94E92359DC59", 18, 6, None, 100, True),
    "aero_weth_usdc_new": ("0x4a7af46bc8abc00048c6c7920a1488daf568366c", 18, 6, None, 50, True),
}

if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 370
    step = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    names = sys.argv[3:] or list(POOLS)
    end = int(time.time()) // step * step
    for name in names:
        addr, *_rest, aero = POOLS[name]
        extra = [(addr, s) for s in AERO_EXTRA] if aero else None
        download_pool(name, addr, end - days * 86400, end, step, extra=extra)

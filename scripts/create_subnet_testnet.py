"""
Create Engram subnet on Bittensor testnet.
Uses Python API directly — no btcli interactive prompts.

Run:
    .venv/bin/python scripts/create_subnet_testnet.py
"""

import sys
import bittensor as bt
from loguru import logger

WALLET_NAME   = "engram"
WALLET_HOTKEY = "default"
NETWORK       = "test"   # Bittensor testnet


def main() -> None:
    wallet    = bt.Wallet(name=WALLET_NAME, hotkey=WALLET_HOTKEY)
    subtensor = bt.Subtensor(network=NETWORK)

    coldkey = wallet.coldkey.ss58_address
    balance = subtensor.get_balance(coldkey)
    burn    = subtensor.get_subnet_burn_cost()

    logger.info(f"Network  : {NETWORK}")
    logger.info(f"Coldkey  : {coldkey}")
    logger.info(f"Balance  : {balance} TAO")
    logger.info(f"Burn cost: {burn} TAO")

    if balance < burn:
        logger.error(f"Insufficient balance: have {balance}, need {burn}")
        sys.exit(1)

    confirm = input(f"\nBurn {burn} TAO to register Engram subnet on testnet? [y/n]: ")
    if confirm.strip().lower() != "y":
        logger.info("Aborted.")
        sys.exit(0)

    logger.info("Registering subnet…")
    # Get total subnets before so we can find the new one
    before = set(subtensor.get_all_subnets_netuid())

    response = subtensor.register_subnet(wallet=wallet)
    success, message = response[0], response[1]

    if not success:
        logger.error(f"Subnet registration failed: {message}")
        sys.exit(1)

    logger.success(f"Registration tx confirmed: {message}")

    # Find the new netuid
    after = set(subtensor.get_all_subnets_netuid())
    new_netuids = after - before
    if new_netuids:
        netuid = max(new_netuids)
    else:
        # Fallback: find our subnet by owner hotkey
        all_info = subtensor.get_all_subnets_info()
        hotkey = wallet.hotkey.ss58_address
        owned = [s.netuid for s in all_info if hasattr(s, 'owner_ss58') and s.owner_ss58 == hotkey]
        if not owned:
            logger.error("Could not determine new NETUID — check 'btcli subnet list --network test'")
            sys.exit(1)
        netuid = max(owned)

    logger.success(f"Subnet registered! NETUID = {netuid}")

    # Update .env
    import os
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            content = f.read()
        # Replace whatever NETUID line is there
        import re
        content = re.sub(r"^NETUID=\S+.*$", f"NETUID={netuid}", content, flags=re.MULTILINE)
        with open(env_path, "w") as f:
            f.write(content)
        logger.success(f".env updated → NETUID={netuid}")

    print(f"\nNext steps:")
    print(f"  .venv/bin/python scripts/register_neurons_testnet.py --netuid {netuid}")


if __name__ == "__main__":
    main()

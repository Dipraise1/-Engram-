"""
Engram — Subnet Registration Script

Run this once you have testnet TAO to register the Engram subnet.

Usage:
    python scripts/register_subnet.py

Requires:
    - Wallet 'engram' created (btcli wallet new-coldkey)
    - ~1000 TAO on testnet for subnet registration burn
    - SUBTENSOR_NETWORK=test in .env
"""

import os
import sys

import bittensor as bt
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


def main() -> None:
    wallet_name = os.getenv("WALLET_NAME", "engram")
    wallet_hotkey = os.getenv("WALLET_HOTKEY", "default")
    network = os.getenv("SUBTENSOR_NETWORK", "test")

    logger.info(f"Registering Engram subnet on {network}...")

    wallet = bt.wallet(name=wallet_name, hotkey=wallet_hotkey)
    subtensor = bt.subtensor(network=network)

    # Check balance
    balance = subtensor.get_balance(wallet.coldkey.ss58_address)
    logger.info(f"Coldkey: {wallet.coldkey.ss58_address}")
    logger.info(f"Balance: {balance} TAO")

    burn_cost = subtensor.get_subnet_burn_cost()
    logger.info(f"Subnet registration cost: {burn_cost} TAO")

    if balance < burn_cost:
        logger.error(
            f"Insufficient balance. Need {burn_cost} TAO, have {balance} TAO.\n"
            f"Get testnet TAO from Bittensor Discord #faucet channel.\n"
            f"Your address: {wallet.coldkey.ss58_address}"
        )
        sys.exit(1)

    confirm = input(f"\nRegister subnet for {burn_cost} TAO? [y/n]: ")
    if confirm.lower() != "y":
        logger.info("Aborted.")
        sys.exit(0)

    # Register the subnet
    netuid = subtensor.register_network(wallet=wallet)

    if netuid is None:
        logger.error("Subnet registration failed.")
        sys.exit(1)

    logger.success(f"Subnet registered! NETUID = {netuid}")
    logger.info(f"Update your .env: NETUID={netuid}")

    # Auto-update .env
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            content = f.read()
        content = content.replace("NETUID=99", f"NETUID={netuid}")
        with open(env_path, "w") as f:
            f.write(content)
        logger.success(f".env updated with NETUID={netuid}")

    print(f"\n✓ Next step: register your validator hotkey on netuid {netuid}")
    print(f"  btcli subnet register --netuid {netuid} --wallet.name {wallet_name} --subtensor.network {network}")


if __name__ == "__main__":
    main()

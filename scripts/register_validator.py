"""
Engram — Validator Registration Script

Run after subnet is registered to register your validator hotkey on the subnet.

Usage:
    python scripts/register_validator.py --netuid <NETUID>
"""

import argparse
import os
import sys

import bittensor as bt
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--netuid", type=int, default=int(os.getenv("NETUID", "99")))
    args = parser.parse_args()

    wallet_name = os.getenv("WALLET_NAME", "engram")
    wallet_hotkey = os.getenv("WALLET_HOTKEY", "default")
    network = os.getenv("SUBTENSOR_NETWORK", "test")

    wallet = bt.wallet(name=wallet_name, hotkey=wallet_hotkey)
    subtensor = bt.subtensor(network=network)

    logger.info(f"Registering validator on netuid={args.netuid} | network={network}")
    logger.info(f"Hotkey: {wallet.hotkey.ss58_address}")

    # Check if already registered
    if subtensor.is_hotkey_registered(netuid=args.netuid, hotkey_ss58=wallet.hotkey.ss58_address):
        logger.success("Hotkey already registered on this subnet.")
        return

    balance = subtensor.get_balance(wallet.coldkey.ss58_address)
    logger.info(f"Balance: {balance} TAO")

    confirm = input(f"Register hotkey on netuid {args.netuid}? [y/n]: ")
    if confirm.lower() != "y":
        sys.exit(0)

    success = subtensor.register(
        wallet=wallet,
        netuid=args.netuid,
        wait_for_inclusion=True,
        wait_for_finalization=True,
    )

    if success:
        logger.success(f"Validator registered on netuid {args.netuid}")
        logger.info("You can now run: python neurons/validator.py")
    else:
        logger.error("Registration failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()

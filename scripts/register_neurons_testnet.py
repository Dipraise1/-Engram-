"""
Register miner + validator hotkeys on the Engram subnet (testnet).

Run after create_subnet_testnet.py:
    .venv/bin/python scripts/register_neurons_testnet.py --netuid <NETUID>
"""

import argparse
import sys
import bittensor as bt
from loguru import logger

WALLET_NAME = "engram"
NETWORK     = "test"


def register_hotkey(subtensor, wallet, netuid: int, role: str) -> int:
    hk = wallet.hotkey.ss58_address
    if subtensor.is_hotkey_registered(netuid=netuid, hotkey_ss58=hk):
        uid = subtensor.get_uid_for_hotkey_on_subnet(hotkey_ss58=hk, netuid=netuid)
        logger.info(f"{role} already registered → uid={uid}")
        return uid

    cost = subtensor.get_neuron_certificate_cost(netuid=netuid) if hasattr(subtensor, "get_neuron_certificate_cost") else None
    if cost:
        logger.info(f"{role} registration cost: {cost} TAO")

    logger.info(f"Registering {role} ({hk[:12]}…) on netuid={netuid}…")
    result = subtensor.burned_register(wallet=wallet, netuid=netuid)

    if not result:
        logger.error(f"{role} registration failed.")
        return -1

    uid = subtensor.get_uid_for_hotkey_on_subnet(hotkey_ss58=hk, netuid=netuid)
    logger.success(f"{role} registered → uid={uid}")
    return uid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--netuid", type=int, required=True, help="Subnet UID from create_subnet_testnet.py")
    args = parser.parse_args()

    subtensor = bt.Subtensor(network=NETWORK)
    logger.info(f"Network: {NETWORK} | netuid: {args.netuid}")

    # Register validator (default hotkey)
    validator_wallet = bt.Wallet(name=WALLET_NAME, hotkey="default")
    logger.info(f"Validator coldkey balance: {subtensor.get_balance(validator_wallet.coldkey.ss58_address)} TAO")
    v_uid = register_hotkey(subtensor, validator_wallet, args.netuid, "Validator")

    # Register miner (miner2 hotkey)
    miner_wallet = bt.Wallet(name=WALLET_NAME, hotkey="miner2")
    m_uid = register_hotkey(subtensor, miner_wallet, args.netuid, "Miner")

    if v_uid >= 0 and m_uid >= 0:
        logger.success(f"Both neurons registered on netuid={args.netuid}")
        print(f"\nNext step: start the miner and validator")
        print(f"  NETUID={args.netuid} .venv/bin/python neurons/miner.py")
        print(f"  NETUID={args.netuid} .venv/bin/python neurons/validator.py")
    else:
        logger.error("One or more registrations failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Engram — Local Subnet Registration Script

Registers the Engram subnet on a local subtensor chain (free).

Prerequisites:
    1. Local subtensor running: bash /path/to/subtensor/scripts/localnet.sh
    2. Wallet 'engram' exists: btcli wallet new-coldkey --wallet.name engram

Usage:
    python scripts/register_local_subnet.py

The local chain Alice account funds your wallet automatically.
"""

import os
import sys
import time

import bittensor as bt
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

LOCAL_ENDPOINT = "ws://127.0.0.1:9944"


def wait_for_chain(subtensor: bt.subtensor, timeout: int = 30) -> bool:
    """Wait up to `timeout` seconds for the local chain to become reachable."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            subtensor.block
            return True
        except Exception:
            time.sleep(2)
    return False


def main() -> None:
    wallet_name = os.getenv("WALLET_NAME", "engram")
    wallet_hotkey = os.getenv("WALLET_HOTKEY", "default")

    logger.info(f"Connecting to local subtensor at {LOCAL_ENDPOINT}...")
    subtensor = bt.subtensor(network=LOCAL_ENDPOINT)

    if not wait_for_chain(subtensor):
        logger.error(
            "Cannot reach local subtensor. Make sure it's running:\n"
            "  bash /Users/divine/Documents/subtensor/scripts/localnet.sh"
        )
        sys.exit(1)

    logger.info(f"Connected. Block: {subtensor.block}")

    wallet = bt.wallet(name=wallet_name, hotkey=wallet_hotkey)
    coldkey_addr = wallet.coldkey.ss58_address
    logger.info(f"Wallet coldkey: {coldkey_addr}")

    balance = subtensor.get_balance(coldkey_addr)
    logger.info(f"Balance: {balance} TAO")

    # On local chain, registration burn is 100 TAO by default
    # Alice key is pre-funded — transfer to our wallet if needed
    if balance.tao < 200:
        logger.warning("Low balance — you may need to transfer from Alice.")
        logger.info(
            "Run:\n"
            "  btcli wallet transfer \\\n"
            "    --wallet.name Alice \\\n"
            f"    --dest {coldkey_addr} \\\n"
            "    --amount 1000 \\\n"
            "    --subtensor.chain_endpoint ws://127.0.0.1:9944"
        )

    burn_cost = subtensor.get_subnet_burn_cost()
    logger.info(f"Subnet burn cost: {burn_cost} TAO")

    confirm = input(f"\nRegister Engram subnet on local chain for {burn_cost} TAO? [y/n]: ")
    if confirm.lower() != "y":
        logger.info("Aborted.")
        sys.exit(0)

    netuid = subtensor.register_network(wallet=wallet)

    if netuid is None:
        logger.error("Registration failed — check wallet balance and chain connectivity.")
        sys.exit(1)

    logger.success(f"Subnet registered! NETUID = {netuid}")

    # Auto-update .env
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            content = f.read()

        import re
        content = re.sub(r"^NETUID=\S+", f"NETUID={netuid}", content, flags=re.MULTILINE)
        content = re.sub(r"^SUBTENSOR_NETWORK=\S+", "SUBTENSOR_NETWORK=local", content, flags=re.MULTILINE)

        with open(env_path, "w") as f:
            f.write(content)
        logger.success(f".env updated: NETUID={netuid}, SUBTENSOR_NETWORK=local")

    print(f"\n✓ Next steps:")
    print(f"  1. Register validator hotkey:")
    print(f"     btcli subnet register --netuid {netuid} --wallet.name {wallet_name} --subtensor.chain_endpoint ws://127.0.0.1:9944")
    print(f"  2. Generate ownership proof:")
    print(f"     python scripts/generate_ownership_proof.py --netuid {netuid}")
    print(f"  3. Start miner:")
    print(f"     python neurons/miner.py")


if __name__ == "__main__":
    main()

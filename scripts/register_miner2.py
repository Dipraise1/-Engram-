"""
Register a second miner hotkey on Engram subnet (local chain).

Creates wallet: engram / miner2
Funds it from Alice, then burns-registers on netuid=2.
"""
import subprocess
import sys
import bittensor as bt

WALLET_NAME = "engram"
HOTKEY_NAME = "miner2"
NETUID = 2
NETWORK = "ws://127.0.0.1:9944"
FUND_AMOUNT = 500  # TAO


def main() -> None:
    s = bt.Subtensor(network=NETWORK)
    w = bt.Wallet(name=WALLET_NAME, hotkey=HOTKEY_NAME)

    # Create hotkey if it doesn't exist
    if not w.hotkey_file.exists():
        print(f"Creating hotkey '{HOTKEY_NAME}' for wallet '{WALLET_NAME}'...")
        w.create_new_hotkey(use_password=False, overwrite=False)
        print(f"Hotkey created: {w.hotkey.ss58_address}")
    else:
        print(f"Hotkey already exists: {w.hotkey.ss58_address}")

    print(f"Block: {s.block}")

    # Fund from Alice
    print(f"\nFunding {w.coldkey.ss58_address} with {FUND_AMOUNT} TAO from Alice...")
    alice = bt.Wallet(name="Alice")
    try:
        s.transfer(
            wallet=alice,
            dest=w.coldkey.ss58_address,
            amount=FUND_AMOUNT,
        )
        print("Funded ✓")
    except Exception as e:
        print(f"Fund skipped (may already have balance): {e}")

    bal = s.get_balance(w.coldkey.ss58_address)
    print(f"Balance: {bal}")

    # Check if already registered
    if s.is_hotkey_registered(netuid=NETUID, hotkey_ss58=w.hotkey.ss58_address):
        uid = s.get_uid_for_hotkey_on_subnet(hotkey_ss58=w.hotkey.ss58_address, netuid=NETUID)
        print(f"\nAlready registered → uid={uid}")
        return

    # Burn-register
    print(f"\nRegistering on netuid={NETUID}...")
    result = s.burned_register(wallet=w, netuid=NETUID)
    print("Result:", result)

    if result:
        uid = s.get_uid_for_hotkey_on_subnet(hotkey_ss58=w.hotkey.ss58_address, netuid=NETUID)
        print(f"Registered ✓ uid={uid}")
    else:
        print("Registration failed — check balance and subnet registration cost")
        sys.exit(1)


if __name__ == "__main__":
    main()

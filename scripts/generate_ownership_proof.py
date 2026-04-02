"""
Engram — Subnet Ownership Proof Generator

Generates message_and_signature.txt required for Bittensor Discord
channel registration.

Run AFTER your subnet is registered on local/testnet.

Usage:
    python scripts/generate_ownership_proof.py --netuid <NETUID>

Output:
    message_and_signature.txt  ← DM this file to @kat_defiants on Discord
"""

import argparse
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Engram subnet ownership proof.")
    parser.add_argument("--netuid", type=int, required=True, help="Your registered subnet UID.")
    parser.add_argument("--wallet", type=str, default=os.getenv("WALLET_NAME", "engram"))
    args = parser.parse_args()

    import bittensor as bt

    wallet = bt.Wallet(name=args.wallet)
    keypair = wallet.coldkey

    timestamp = datetime.now()
    timezone = timestamp.astimezone().tzname()

    message = (
        "<Bytes>"
        + f"On {timestamp} {timezone} "
        + f"I am the owner of Engram subnet (netuid={args.netuid}) "
        + f"on Bittensor. GitHub: https://github.com/Dipraise1/-Engram-"
        + "</Bytes>"
    )

    signature = keypair.sign(data=message)

    file_contents = (
        f"{message}\n"
        f"\tSigned by: {keypair.ss58_address}\n"
        f"\tSignature: {signature.hex()}"
    )

    output_path = "message_and_signature.txt"
    with open(output_path, "w") as f:
        f.write(file_contents)

    print(file_contents)
    print(f"\n✓ Saved to {output_path}")
    print(f"\nNext steps:")
    print(f"  1. Join discord.gg/bittensor")
    print(f"  2. Post in #1107738550373454028 mentioning @kat_defiants")
    print(f"     'Requesting subnet channel for Engram (netuid={args.netuid})'")
    print(f"  3. DM her the file: message_and_signature.txt")
    print(f"  4. Include GitHub: https://github.com/Dipraise1/-Engram-")


if __name__ == "__main__":
    main()

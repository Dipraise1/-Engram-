"""
Fund engram wallet from Alice dev account on local chain.

Alice is the pre-funded dev account on every local Substrate chain.
Her keypair is derived from the well-known dev mnemonic and is
accessible without a wallet file.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

ALICE_MNEMONIC = "bottom drive obey lake curtain smoke basket hold race lonely fit walk"
LOCAL_ENDPOINT  = "ws://127.0.0.1:9944"
AMOUNT_TAO      = 2_000  # enough for subnet burn + fees


def main() -> None:
    import bittensor as bt
    from substrateinterface import SubstrateInterface, Keypair

    dest_wallet_name = os.getenv("WALLET_NAME", "engram")

    # Load destination address from wallet (public key only — no password needed)
    wallet = bt.Wallet(name=dest_wallet_name)
    dest_addr = wallet.coldkeypub.ss58_address
    print(f"Destination: {dest_addr}")

    substrate = SubstrateInterface(url=LOCAL_ENDPOINT)

    alice = Keypair.create_from_uri("//Alice")
    print(f"Alice:       {alice.ss58_address}")

    # Check balances before
    before = substrate.query("System", "Account", [dest_addr])
    before_free = int(before["data"]["free"].value) / 1e9
    print(f"Balance before: τ{before_free:,.4f}")

    amount_rao = AMOUNT_TAO * 10**9  # TAO → RAO (smallest unit)

    call = substrate.compose_call(
        call_module="Balances",
        call_function="transfer_keep_alive",
        call_params={"dest": dest_addr, "value": amount_rao},
    )

    extrinsic = substrate.create_signed_extrinsic(call=call, keypair=alice)
    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)

    if receipt.is_success:
        after = substrate.query("System", "Account", [dest_addr])
        after_free = int(after["data"]["free"].value) / 1e9
        print(f"Transfer SUCCESS")
        print(f"Balance after:  τ{after_free:,.4f}")
    else:
        print(f"Transfer FAILED: {receipt.error_message}")
        sys.exit(1)


if __name__ == "__main__":
    main()

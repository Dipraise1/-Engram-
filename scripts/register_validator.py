"""Register validator hotkey on Engram subnet (local chain)."""
import bittensor as bt

s = bt.Subtensor(network="ws://127.0.0.1:9944")
w = bt.Wallet(name="engram", hotkey="default")

print(f"Hotkey: {w.hotkey.ss58_address}")
print(f"Block:  {s.block}")

result = s.burned_register(wallet=w, netuid=2)
print("Result:", result)

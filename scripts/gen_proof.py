import bittensor as bt
from datetime import datetime

wallet = bt.Wallet(name="engram")
keypair = wallet.coldkey
ts = datetime.now()
tz = ts.astimezone().tzname()
message = (
    "<Bytes>"
    + f"On {ts} {tz} "
    + "I am the owner of Engram subnet (netuid=2) "
    + "on Bittensor. GitHub: https://github.com/Dipraise1/-Engram-"
    + "</Bytes>"
)
sig = keypair.sign(data=message)
out = f"{message}\n\tSigned by: {keypair.ss58_address}\n\tSignature: {sig.hex()}"
open("message_and_signature.txt", "w").write(out)
print(out)
print("\n✓ Saved to message_and_signature.txt")

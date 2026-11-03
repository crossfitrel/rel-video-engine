"""L175: מפענח את טוקן הג'וב שה-edge שולח מוצפן ב-inputs (ריפו ציבורי). x1:<hex> = token XOR HMAC-SHA256(PAT, job_id)."""
import hashlib, hmac, os, sys
t, k, j = os.environ.get("T", ""), os.environ.get("K", ""), os.environ.get("J", "")
if not t.startswith("x1:"):
    print(t); sys.exit(0)
if not k:
    sys.exit("LIBS_TOKEN חסר ב-Secrets של rel-video-engine")
pad = hmac.new(k.encode(), j.encode(), hashlib.sha256).digest()
raw = bytes.fromhex(t[3:])
print(bytes(a ^ b for a, b in zip(raw, pad)).hex())

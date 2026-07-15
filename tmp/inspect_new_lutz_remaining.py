import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))

from app.services.email.lutz_parser import LutzEmailParser

folder = root / "Email Samples" / "NEW LUTZ SAMPLES"
names = [
    "#1025337 Bestellung QPQ8LN von Lutz (10!2026062929334).eml",
    "#1029213 Bestellung PRKMJW von Lutz (10!2026070827933).eml",
    "#1024704 Bestellung DGRNS von Lutz (10!2026062621667).eml",
]

for name in names:
    message = BytesParser(policy=policy.default).parsebytes((folder / name).read_bytes())
    print("=" * 100)
    print(name)
    print(LutzEmailParser._get_message_body(message)[:12000])

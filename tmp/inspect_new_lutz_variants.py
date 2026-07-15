import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))

from app.services.email.lutz_parser import LutzEmailParser

folder = root / "Email Samples" / "NEW LUTZ SAMPLES"
names = [
    "#1018591 Bestellung PRKLYQ von Lutz (10!202606143289).eml",
    "#1021649 Bestellung ZPNWLH von Lutz (10!2026061826417).eml",
    "#1024683 Bestellung DGRPQ von Lutz (10!2026062621666).eml",
    "#1022274 Bestellung BCRKE6 von Lutz (10!202606208391).eml",
    "#1025745 MAIL VON S LUTZ  (A! S 2026063026804).eml",
]

for name in names:
    message = BytesParser(policy=policy.default).parsebytes((folder / name).read_bytes())
    print("=" * 100)
    print(name)
    print("FROM:", message.get("From"))
    print("TO:", message.get("To"))
    print("SUBJECT:", message.get("Subject"))
    print("BODY:")
    print(LutzEmailParser._get_message_body(message)[:6000])
    for part in message.iter_attachments():
        if (part.get_filename() or "").casefold().endswith(".xml"):
            print("XML:", part.get_filename())
            print((part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")[:6000])

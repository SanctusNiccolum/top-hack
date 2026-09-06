import sys, json, re

GARBAGE = [
    r"=> =>", r"PS D:\\", r"docker compose", r"Get-Content", r"SELECT ",
    r"chat_id \|", r"^\|$", r"\(1 row\)", r"---", r"sha256:",
    r"exporting ", r"unpacking to", r"resolving provenance",
    r"transferring context", r"WORKDIR|COPY|RUN pip|useradd",
]

def is_garbage(t: str) -> bool:
    if not t or not t.strip(): return True
    s = t.strip()
    return any(re.search(p, s) for p in GARBAGE)

data = json.load(sys.stdin)
texts = data if isinstance(data, list) else data.get("texts", [])
clean = [t for t in texts if not is_garbage(t)]
seen = set()
uniq = [x for x in clean if not (x in seen or seen.add(x))]
payload = {"user_id": 5270187642, "texts": uniq}
json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
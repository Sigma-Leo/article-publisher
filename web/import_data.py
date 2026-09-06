import getpass
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
base_url = input("Render 后端地址: ").strip().rstrip("/")
token = getpass.getpass("ADMIN_TOKEN: ")
articles = json.loads((ROOT / "articles.json").read_text(encoding="utf-8"))
cookies = json.loads((ROOT / "cookies_store.json").read_text(encoding="utf-8"))
response = requests.post(
    f"{base_url}/api/admin/import",
    headers={"X-Admin-Token": token},
    json={"articles": articles, "cookies": cookies},
    timeout=60,
)
response.raise_for_status()
print(response.json())

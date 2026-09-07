"""データベース接続先の組み立て。

ローカルは POSTGRES_*、Render など本番は DATABASE_URL を使う。
"""

import os
from urllib.parse import parse_qs, unquote, urlparse


def database_config():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return database_from_url(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "hospital_timer"),
        "USER": os.environ.get("POSTGRES_USER", "hospital_timer"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "hospital_timer"),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "55432"),
    }


def database_from_url(url):
    parsed = urlparse(url)
    name = unquote(parsed.path.lstrip("/"))
    options = {}
    query = parse_qs(parsed.query)
    if "sslmode" in query:
        options["sslmode"] = query["sslmode"][0]
    # URL に sslmode が無いときは付けない。
    # Render の Internal Database URL は同一リージョン内の平文接続で、
    # require を付けると起動時の migrate が待たされて画面が開き続けない。
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": name,
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or "5432"),
        "OPTIONS": options,
    }

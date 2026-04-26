from __future__ import annotations

import re
import time
import urllib.request
from bs4 import BeautifulSoup


def fetch_url(url: str, max_chars: int = 8000) -> str | None:
    """Fetch raw text from a URL. Returns None on any failure."""
    headers = {"User-Agent": "EvidenceGraph-Bot/0.1 (+https://github.com/machachlouei/evidence-graph)"}
    req = urllib.request.Request(url, headers=headers)

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "html" in content_type or "text" in content_type:
                    raw = resp.read().decode("utf-8", errors="ignore")
                    
                    # Parse HTML safely and remove noisy elements like scripts and styles
                    soup = BeautifulSoup(raw, "html.parser")
                    for element in soup(["script", "style", "nav", "footer", "header"]):
                        element.decompose()
                        
                    text = soup.get_text(separator=" ", strip=True)
                    text = re.sub(r"\s+", " ", text).strip()
                    return text[:max_chars]
                return None
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)

    return None

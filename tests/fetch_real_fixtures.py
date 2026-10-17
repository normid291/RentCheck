"""
Re-download the real fixture documents from their public sources.

The fixtures themselves are committed to the repo, so you only need this if you
want to refresh them. Network access is required; sites that block automated
downloads are skipped with a warning (the committed copy stays in place).

Run from the repo root:

    python tests/fetch_real_fixtures.py
"""
from __future__ import annotations

import os
import re
import html as htmllib

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.join(HERE, "fixtures", "real")
os.makedirs(REAL, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (RentCheck fixture research)"}

# Direct file downloads. (filename, url)
FILES = [
    ("ng_deed_of_lease.pdf", "https://nigerianlawguru.com/wp-content/uploads/2024/06/DEED-OF-LEASE.pdf"),
    ("ng_yearly_tenancy_adoghe.pdf", "https://ngfrepository.org.ng:8443/jspui/bitstream/123456789/2332/1/THE%20AGREEMENT%20BTW%20CHIEF%20ALEX%20ADOGHE%20AND%20NGF.pdf"),
    ("uk_ast_nla.pdf", "https://burnley.gov.uk/wp-content/uploads/2022/01/NLA-Assured-Shorthold-Tenancy-Agreement.pdf"),
    ("uk_ast_crisis.pdf", "https://www.crisis.org.uk/media/237919/sample-tenancy-agreement-and-s21.pdf"),
    ("uk_licence_to_occupy.pdf", "https://magdalenroadstudios.squarespace.com/s/Sample-Studio-Licence-to-Occupy.pdf"),
    ("in_leave_and_license.pdf", "https://pkgoyalandassociates.com/forms/2277.pdf"),
    ("us_simple_lease_esign.pdf", "https://esign.com/wp-content/uploads/Simple-1-Page-Residential-Lease-Agreement.pdf"),
    ("fr_bail_service_public.pdf", "https://www.service-public.pf/dhv/wp-content/uploads/sites/56/2022/05/Modele-contrat-de-location-.pdf"),
    ("bt_employment_sample.pdf", "https://www.moice.gov.bt/wp-content/uploads/2017/07/COE-Sample.pdf"),
]

# SEC EDGAR full-text search -> download the matching exhibit and strip HTML to text.
SEC_UA = {"User-Agent": "RentCheck fixture research contact@example.com"}
SEC_TARGETS = [
    ("us_employment_agreement.txt", "employment agreement", "8-K", ["employment agreement"], ["form 8-k"]),
    ("us_loan_agreement.txt", "loan agreement", "8-K", ["agreement"], ["form 8-k"]),
    ("us_nda.txt", "non-disclosure agreement", None, ["non-disclosure agreement", "confidential information"], ["form 8-k"]),
    ("us_sale_agreement.txt", "asset purchase agreement", "8-K", ["purchase agreement"], ["form 8-k"]),
]


def download_files() -> None:
    for name, url in FILES:
        dest = os.path.join(REAL, name)
        try:
            r = requests.get(url, headers=UA, timeout=90)
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                open(dest, "wb").write(r.content)
                print(f"OK   {name} ({len(r.content)} bytes)")
            else:
                print(f"SKIP {name} -> HTTP {r.status_code}")
        except Exception as exc:
            print(f"SKIP {name} -> {type(exc).__name__}: {exc}")


def _strip(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"[ \t\xa0]+", " ", htmllib.unescape(s)).strip()


def download_sec() -> None:
    for name, query, forms, must, avoid in SEC_TARGETS:
        dest = os.path.join(REAL, name)
        try:
            url = "https://efts.sec.gov/LATEST/search-index?q=" + requests.utils.quote(f'"{query}"')
            if forms:
                url += f"&forms={forms}"
            hits = requests.get(url, headers=SEC_UA, timeout=40).json()["hits"]["hits"][:40]
            saved = False
            for h in hits:
                cik = h["_source"]["ciks"][0]
                acc, fn = h["_id"].split(":")
                if not re.search(r"\.(?:htm|html|txt)$", fn, re.I):
                    continue
                u = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{fn}"
                r = requests.get(u, headers=SEC_UA, timeout=60)
                if r.status_code != 200:
                    continue
                text = _strip(r.text) if fn.lower().endswith(("htm", "html")) else r.text
                low = text.lower()[:4000]
                if len(text.split()) < 400:
                    continue
                if not all(m in low for m in must) or any(a in low for a in avoid):
                    continue
                open(dest, "w", encoding="utf-8").write(text)
                print(f"OK   {name} ({len(text.split())} words)")
                saved = True
                break
            if not saved:
                print(f"SKIP {name} -> no suitable EDGAR match")
        except Exception as exc:
            print(f"SKIP {name} -> {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    download_files()
    download_sec()
    print("done (run tests/make_generated_fixtures.py to rebuild derived scans)")

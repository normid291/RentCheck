# Legal pages

The privacy policy and terms of service, and the pages the app serves from them.

| Document | Markdown — edit this | Served at | Generated page |
| --- | --- | --- | --- |
| Privacy Policy | `privacy-policy.md` | `/privacy` | `app/static/privacy.html` |
| Terms of Service | `terms-of-service.md` | `/terms` | `app/static/terms.html` |

## Single source of truth

The Markdown files are the source. `app/static/privacy.html` and
`app/static/terms.html` are **generated** — do not edit them by hand. Edit the
Markdown, then:

```bash
python scripts/build_legal_pages.py
```

Commit both the Markdown and the regenerated pages together.

## Before you rely on these

These drafts were written to describe what the code *actually does* — the AI
flow, the storage, the rejection behaviour are all read from the source, not
guessed. They have **not been reviewed by a lawyer**. Before relying on them,
and certainly before a public launch, have a Nigerian lawyer read them. The open
items:

- **Confirm where Rumpty Cloud hosts** the app and its database, and where
  Rumpty AI Inference runs. Section 7 of the privacy policy assumes data may
  leave Nigeria and leans on the NDPA's transfer safeguards. If it stays in
  Nigeria, say so — that is a better answer and a shorter section.
- **Decide on retention.** Section 8 is deliberately honest that there is no
  automatic expiry. Either keep that wording, or implement a retention window
  and update the section to match. Do not promise a period the code does not
  enforce.
- **Closing an account is still manual.** Deleting a saved analysis is
  self-service from `/history`, but closing the account itself means emailing us
  (privacy §8). If you add an account-delete endpoint, update §8 and §10.
- **Consider whether a Data Protection Officer is required.** The NDPA requires
  one in some circumstances; a project this size may not, but it is worth
  checking.
- **Check the liability cap** in section 8 of the Terms (₦10,000) and the
  free-service framing with that lawyer.

## Keeping them accurate

Both documents describe real behaviour, so they drift when the behaviour
changes. The claims most likely to go stale:

- **The AI flow** (privacy §5 and §6): individual clause text, plus a
  1,800-character excerpt *only* when the document type is ambiguous. That
  excerpt length is `EXCERPT_CHARS` in `app/services/document_classifier.py`.
- **Rejected uploads are not stored** (privacy §3.1): a rejection writes no
  `Agreement` row — see `_rejection_response` in `app/routers/agreements.py`.
- **Document text is stored only for signed-in users** (privacy §3.1):
  `Agreement.raw_text` in `app/models/db.py`, written from
  `app/routers/agreements.py` only when a run is authenticated. Guest analyses
  are not persisted at all, so the policy is simpler for them.
- **"One session cookie, no analytics, no third-party scripts"** (privacy
  §3.2): `tenura_session` is the only cookie, set in `app/services/auth.py`.
  This holds because `app/static/index.html` loads nothing external. Keep it
  that way, or soften the sentence.
- **"Uploads are never written to disk"** (privacy §3.1, §9): uploads are read
  into memory in `app/routers/agreements.py` and passed as bytes.

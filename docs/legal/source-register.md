# Source register — clause norms

Every norm in `clause_reference` is currently seeded with
`legal_basis = "market_norm"`. That is deliberate and load-bearing:

- **`market_norm`** means *"this is common practice in the Nigerian rental
  market"*. It is **not** a claim about the law. The UI must phrase it as
  "common practice in Nigeria", never "the law requires".
- **`statute`** is reserved for a norm a qualified human reviewer has confirmed
  against a specific, named provision. **The seed data contains none yet.**

No statute, section number, case name, or URL has been invented. Where a source
is not yet verified the fields are left empty on purpose:

| field | meaning | current state |
| --- | --- | --- |
| `legal_basis` | `market_norm` or `statute` | `market_norm` for every row |
| `source_title` | name of the source (statute, guidance, standard lease) | empty |
| `source_section` | the specific section/paragraph | empty |
| `source_url` | link to the source | empty |
| `source_retrieved_at` | when a reviewer retrieved it | empty |
| `source_quote` | the exact quoted text relied on | empty |
| `reviewed_by` | who verified it | empty |
| `reviewed_at` | when it was verified | empty |
| `version` | norm version; bumped when the wording changes | `1` |

## Rows

The table below is generated from `app/seed_clause_reference.py`. Each row is
`market_norm` / **UNVERIFIED** until a reviewer completes the review below.

| clause_type | jurisdiction | severity | status |
| --- | --- | --- | --- |
| `caution_fee` | NG | high | market_norm — unverified |
| `repair_responsibility` | NG | medium | market_norm — unverified |
| `exit_clause` | NG | high | market_norm — unverified |
| `rent_increase` | NG | medium | market_norm — unverified |
| `utilities_responsibility` | NG | low | market_norm — unverified |
| `entry_without_notice` | NG | high | market_norm — unverified |
| `subletting` | NG | low | market_norm — unverified |
| `taxes_and_outgoings` | NG | medium | market_norm — unverified |
| `insurance_requirement` | NG | medium | market_norm — unverified |
| `re_entry_forfeiture` | NG | high | market_norm — unverified |
| `permitted_use` | NG | low | market_norm — unverified |
| `governing_law` | NG | low | market_norm — unverified |
| `dispute_resolution` | NG | low | market_norm — unverified |

`jurisdiction = "NG"` is the generic Nigerian package. State-specific packs
(e.g. `NG-LA` for Lagos) would sit alongside it and override individual rows;
none have been added yet.

## Process to promote a norm to `statute`

1. A qualified Nigerian property lawyer identifies the exact provision.
2. Fill `source_title`, `source_section`, `source_url`, `source_retrieved_at`
   and paste the exact `source_quote`.
3. Set `legal_basis = "statute"`, record `reviewed_by` and `reviewed_at`, and
   bump `version` if the wording changed.
4. Only then may the UI describe the norm as a legal requirement.

Until step 4, the norm stays `market_norm` and the copy stays "common practice".

# Jurisdiction notes

Tenura reviews **Nigerian** residential tenancy agreements against Nigerian
clause norms. It must never silently judge a non-Nigerian agreement as if it
were Nigerian — a UK assured shorthold tenancy judged against Lagos market norms
would produce confident, wrong warnings. The jurisdiction gate exists to make
that impossible.

## Accepted values

| value | meaning | pipeline behaviour |
| --- | --- | --- |
| `NG-LA` | Lagos State | judged with the NG pack |
| `NG-FC` | Federal Capital Territory (Abuja) | judged with the NG pack |
| `NG-<CODE>` | another recognised state (ISO 3166-2:NG) | judged with the NG pack |
| `NG-UNKNOWN` | clearly Nigerian, state not identified | judged with the NG pack |
| `NON_NG` | clearly not Nigerian | **refused** — `200 {status: "out_of_scope"}` |
| `UNKNOWN` | not enough signal to tell | **asks** — `200 {status: "needs_jurisdiction"}` |

`NG-*` (anything starting with `NG`) is the pipeline's "is Nigerian" predicate
(`app/services/jurisdiction.py::is_nigerian`).

## How the value is decided

Deterministic first, model second, and never a guess:

1. **Text markers.** Strong signals settle it alone: the naira sign `₦`, "naira",
   "NGN", "Lagos State Tenancy Law", "Recovery of Premises Act". Medium signals
   corroborate: Nigerian states/cities, "caution fee", "quit notice", "yearly
   rent", "Nigeria". Foreign signals work the same way: `£`, "assured shorthold",
   "section 21", "Housing Act", `€`, "Mietvertrag", "arrendamiento", "contrat de
   location", `$`.
2. **Only if the text is ambiguous** (no signals, weak signals, or signals from
   both sides) is the model asked, in **one** call, and only to choose
   `NG` / `NON_NG` / `UNKNOWN`.
3. **If the model is unavailable or unsure**, the answer is `UNKNOWN`. The
   pipeline asks the user rather than guessing.

The currency symbol is one of the strongest signals, so jurisdiction detection
uses its own normaliser that keeps `₦ / £ / € / $` (the document classifier's
normaliser strips them, which is fine for keyword counting and wrong here).

## Injection resistance

Agreement text is untrusted content. If it contains instructions ("ignore the
above", "return NON_NG"), they are ignored: the deterministic markers are read
from the text as data, and the model prompt states plainly that everything
between the markers is data, never instructions. A Nigerian agreement carrying
an injected "return NON_NG" line is still detected as Nigerian.

## What the user sees

- **`out_of_scope`** — "This looks like a non-Nigerian agreement." No analysis,
  nothing stored. The message tells the user that judging it against Nigerian
  rules would be misleading.
- **`needs_jurisdiction`** — "Which country is this agreement for?" The user is
  asked to add the Nigerian state or the rent in naira and try again.

Neither response is ever written to an account, so it never counts as a
completed analysis.

## Coverage and honesty

Once an agreement is accepted as Nigerian, each clause is matched to a norm. A
run that checks too few clauses (or whose model calls failed) is reported with
**coverage** and is banded `unknown` — never "low risk" (`app/services/scoring.py`).

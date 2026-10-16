"""
Standalone test script — run this LOCALLY (not in a sandbox) once you have
your Rumpty AI Inference credentials from the console.

Usage:
    pip install requests
    python test_ai_inference.py

Fill in the three values below first, or set them as environment variables:
    RUMPTY_AI_BASE_URL, RUMPTY_AI_KEY, RUMPTY_AI_MODEL

This tests the exact same prompt structure the real app uses
(app/services/ai_inference.py), against one of the real clauses we already
confirmed gets matched correctly by the clause_matcher — the insurance
clause from the Deed of Lease sample.
"""
import os
import json
import requests

BASE_URL = os.environ.get("RUMPTY_AI_BASE_URL", "PASTE_BASE_URL_HERE")
API_KEY = os.environ.get("RUMPTY_AI_KEY", "PASTE_API_KEY_HERE")
MODEL = os.environ.get("RUMPTY_AI_MODEL", "PASTE_MODEL_NAME_HERE")

# Same few-shot format as the real app
FEW_SHOT_EXAMPLES = """\
Example 1:
Clause: "Tenant shall pay a caution fee of 50% of annual rent, non-refundable under any circumstance."
Known norm: Caution fees are typically refundable minus damages, usually 10-20% of annual rent.
Answer: {"flag": true, "severity": "high", "reason": "Caution fee is unusually high and explicitly non-refundable, which is not standard."}

Example 2:
Clause: "Tenant shall keep the interior of the premises in good repair, fair wear and tear excepted."
Known norm: Standard clause — tenant handles interior upkeep, landlord handles structural repairs.
Answer: {"flag": false, "severity": "low", "reason": "Standard repair clause, matches common practice."}
"""

# Real clause from the Deed of Lease test document, matched to insurance_requirement
TEST_CLAUSE = (
    'To keep the demised premises insured against loss or damage by fire in '
    'any office approved by the Landlord in the sum of N... and upon request '
    'to produce the insurance policy and receipt for the premium paid in '
    'respect of the year.'
)
CLAUSE_TYPE = "insurance_requirement"
NORM_DESCRIPTION = (
    "Tenant may be required to insure the premises against fire/damage, "
    "with proof of policy provided on request."
)
RED_FLAG_PATTERN = (
    "Tenant forced to use an insurer solely chosen/approved by the landlord "
    "(no independent choice), or insurance sum set unreasonably high relative "
    "to property value."
)


def main():
    if "PASTE_" in BASE_URL or "PASTE_" in API_KEY or "PASTE_" in MODEL:
        print("Fill in BASE_URL, API_KEY, and MODEL at the top of this file first.")
        return

    prompt = f"""{FEW_SHOT_EXAMPLES}
Now evaluate this clause the same way. Respond with ONLY a JSON object, no other text.

Clause: "{TEST_CLAUSE}"
Known norm for this clause type ({CLAUSE_TYPE}): {NORM_DESCRIPTION}
Known red-flag pattern: {RED_FLAG_PATTERN}

Answer:"""

    print("=" * 60)
    print("SENDING PROMPT:")
    print("=" * 60)
    print(prompt)
    print("=" * 60)
    print()

    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 150,
            },
            timeout=30,
        )
        print(f"HTTP status: {response.status_code}")
        print()

        if response.status_code != 200:
            print("RAW RESPONSE BODY:")
            print(response.text)
            return

        data = response.json()
        print("FULL RESPONSE JSON:")
        print(json.dumps(data, indent=2))
        print()

        raw_content = data["choices"][0]["message"]["content"].strip()
        print("MODEL'S RAW TEXT OUTPUT:")
        print(raw_content)
        print()

        # Try parsing it the way our real app does
        try:
            start = raw_content.index("{")
            end = raw_content.rindex("}") + 1
            parsed = json.loads(raw_content[start:end])
            print("PARSED SUCCESSFULLY:")
            print(json.dumps(parsed, indent=2))
        except (ValueError, json.JSONDecodeError) as e:
            print(f"PARSING FAILED: {e}")
            print("This means our _parse_model_json fallback would kick in —")
            print("worth seeing WHY it failed (extra text? malformed JSON? different format?)")

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    main()

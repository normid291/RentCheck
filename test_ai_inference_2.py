"""
Test 2: verify the model correctly does NOT flag a standard, fair clause.
This matters because small models can be overly cautious and flag
everything by default — if this test also comes back flag:true, that's
a sign the prompt needs tightening, not that every clause really is risky.

Fill in your credentials below (same ones from test_ai_inference.py), then run:
    python test_ai_inference_2.py
"""
import os
import json
import requests

BASE_URL = os.environ.get("RUMPTY_AI_BASE_URL", "PASTE_BASE_URL_HERE")
API_KEY = os.environ.get("RUMPTY_AI_KEY", "PASTE_API_KEY_HERE")
MODEL = os.environ.get("RUMPTY_AI_MODEL", "llama3.2:3b")

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

# Real clause from the Deed of Lease, matched to repair_responsibility.
# This is a FAIR, standard clause — the model should say flag: false.
TEST_CLAUSE = (
    "TO KEEP the demised premises and any additions thereto and the "
    "fixtures in good condition and repair."
)
CLAUSE_TYPE = "repair_responsibility"
NORM_DESCRIPTION = (
    "Tenant handles interior/day-to-day upkeep; landlord handles structural "
    "repairs and major systems."
)
RED_FLAG_PATTERN = (
    "All repairs (including structural/major) pushed onto tenant with no "
    "landlord obligation at all."
)


def main():
    if "PASTE_" in BASE_URL or "PASTE_" in API_KEY:
        print("Fill in BASE_URL and API_KEY at the top of this file first.")
        return

    prompt = f"""{FEW_SHOT_EXAMPLES}
Now evaluate this clause the same way. Respond with ONLY a JSON object, no other text.

Clause: "{TEST_CLAUSE}"
Known norm for this clause type ({CLAUSE_TYPE}): {NORM_DESCRIPTION}
Known red-flag pattern: {RED_FLAG_PATTERN}

Answer:"""

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
    if response.status_code != 200:
        print(response.text)
        return

    data = response.json()
    raw_content = data["choices"][0]["message"]["content"].strip()
    print("MODEL'S RAW TEXT OUTPUT:")
    print(raw_content)
    print()

    try:
        start = raw_content.index("{")
        end = raw_content.rindex("}") + 1
        parsed = json.loads(raw_content[start:end])
        print("PARSED:")
        print(json.dumps(parsed, indent=2))
        print()
        if parsed.get("flag") is False:
            print("PASS — model correctly did NOT flag a standard clause.")
        else:
            print("CHECK THIS — model flagged a clause that should be fine. "
                  "May need prompt tightening (e.g. stronger 'only flag real deviations' instruction).")
    except (ValueError, json.JSONDecodeError) as e:
        print(f"PARSING FAILED: {e}")


if __name__ == "__main__":
    main()

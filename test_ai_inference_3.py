"""
Test 3: same repair clause as test 2, but with the fixed prompt that
explicitly tells the model not to assume the red-flag pattern is present
unless the clause's own words say so.

Fill in credentials, then run: python test_ai_inference_3.py
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

    # UPDATED prompt with the anti-hallucination instruction
    prompt = f"""{FEW_SHOT_EXAMPLES}
Now evaluate this clause the same way. Respond with ONLY a JSON object, no other text.

IMPORTANT: Base your answer ONLY on what the clause text actually says. Do not
assume the clause contains something from the "red-flag pattern" description
unless the clause's own words actually say it. If the clause does not mention
something (e.g. does not mention "structural"), do not claim that it does.

Clause: "{TEST_CLAUSE}"
Known norm for this clause type ({CLAUSE_TYPE}): {NORM_DESCRIPTION}
Known red-flag pattern to check AGAINST (not assume is present): {RED_FLAG_PATTERN}

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
            print("PASS — fix worked, model correctly did NOT flag this clause.")
        else:
            print("STILL FLAGGING — check if 'reason' still mentions things the clause doesn't say.")
    except (ValueError, json.JSONDecodeError) as e:
        print(f"PARSING FAILED: {e}")


if __name__ == "__main__":
    main()

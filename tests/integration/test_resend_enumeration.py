"""resend-otp must not work as an account-existence oracle.

An attacker can submit an address they do not own and read the response. If the
response (status or body) differs between an unknown address, a known-unverified
address, and a known-verified address - and especially if it differs between the
first and second call - the endpoint enumerates accounts. This test freezes the
response as identical for all three.
"""
from __future__ import annotations

from conftest import requires_db

pytestmark = requires_db


def _body(resp) -> bytes:
    return resp.content


def test_resend_response_is_identical_for_all_address_states(client, make_user):
    # A verified account (real, and already past the verify step).
    verified_email = make_user()
    client.post("/api/auth/logout")

    # A known but unverified account.
    unverified_email = "oracle-unverified@example.com"
    client.post(
        "/api/auth/signup",
        json={"email": unverified_email, "password": "correct-horse-battery"},
    )

    # An address that was never registered.
    unknown_email = "oracle-unknown@example.com"

    responses = {}
    for label, address in (
        ("unknown", unknown_email),
        ("unverified", unverified_email),
        ("verified", verified_email),
    ):
        first = client.post("/api/auth/resend-otp", json={"email": address})
        second = client.post("/api/auth/resend-otp", json={"email": address})
        responses[label] = (first.status_code, _body(first), second.status_code, _body(second))

    reference = responses["unknown"]
    for label, value in responses.items():
        assert value == reference, f"{label} response differs: {value!r} != {reference!r}"

    # And specifically: an existing address is not refused on the second call
    # (the old code returned 429 only for a real account).
    assert responses["unverified"][2] == 200
    assert responses["verified"][2] == 200

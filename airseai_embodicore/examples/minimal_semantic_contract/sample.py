#!/usr/bin/env python3
"""
Minimal AIRSEAI EmbodiCore example.

No model checkpoint or hardware is required.
The goal is to demonstrate the difference between:
  - a resource/structure choice, and
  - whether that choice is semantically legal.

Execution domains:
    scan < denoise < policy < episode
"""

DOMAIN_RANK = {
    "scan": 0,
    "denoise": 1,
    "policy": 2,
    "episode": 3,
}

# Frozen simplified contract:
# - scan state must not outlive one scan invocation;
# - global condition may be reused inside one policy invocation
#   but must be invalidated when a new observation starts a new policy call.
CONTRACT = {
    "scan_state_max_lifetime": "scan",
    "condition_max_lifetime": "policy",
}

DESIGNS = [
    {
        "name": "Matched-NoReuse",
        "scan_lifetime": "scan",
        "condition_lifetime": "denoise",
    },
    {
        "name": "EmbodiCore-759",
        "scan_lifetime": "scan",
        "condition_lifetime": "policy",
    },
    {
        "name": "Agnostic-4087",
        "scan_lifetime": "episode",
        "condition_lifetime": "episode",
    },
]


def at_most(actual, maximum):
    return DOMAIN_RANK[actual] <= DOMAIN_RANK[maximum]


def is_legal(design):
    return (
        at_most(design["scan_lifetime"], CONTRACT["scan_state_max_lifetime"])
        and at_most(
            design["condition_lifetime"],
            CONTRACT["condition_max_lifetime"],
        )
    )


def main():
    print("AIRSEAI EmbodiCore minimal sample")
    print("--------------------------------")

    observed = {}
    for d in DESIGNS:
        legal = is_legal(d)
        observed[d["name"]] = legal
        state = "LEGAL" if legal else "ILLEGAL"
        print(f"{d['name']:<16}: {state}")

    assert observed["Matched-NoReuse"] is True
    assert observed["EmbodiCore-759"] is True
    assert observed["Agnostic-4087"] is False

    print()
    print("Semantic legality check: PASS")


if __name__ == "__main__":
    main()

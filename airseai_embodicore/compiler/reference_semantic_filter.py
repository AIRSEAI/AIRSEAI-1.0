#!/usr/bin/env python3
"""Minimal reference implementation of the EmbodiCore semantic-legality layer.

This is a public reference for the contract interface. It is intentionally
small and does not reconstruct a missing historical Part-III cost model.
"""
from dataclasses import dataclass
from typing import Iterable, Mapping, Any

ORDER = {"scan": 0, "denoise": 1, "policy": 2, "episode": 3}

@dataclass(frozen=True)
class ExecutionContract:
    lifetime: str
    reset_event: str
    update_event: str
    reuse_scope: str

def no_broader_than(proposed: str, allowed: str) -> bool:
    return ORDER[proposed] <= ORDER[allowed]

def candidate_is_legal(candidate: Mapping[str, Any],
                       scan_contract: ExecutionContract,
                       condition_contract: ExecutionContract) -> bool:
    return (
        no_broader_than(candidate["scan_lifetime"], scan_contract.reuse_scope)
        and no_broader_than(candidate["condition_lifetime"], condition_contract.reuse_scope)
    )

def filter_legal(candidates: Iterable[Mapping[str, Any]],
                 scan_contract: ExecutionContract,
                 condition_contract: ExecutionContract):
    return [c for c in candidates if candidate_is_legal(c, scan_contract, condition_contract)]

if __name__ == "__main__":
    scan = ExecutionContract("scan", "each independent scan", "scan call", "scan")
    cond = ExecutionContract("policy", "observation update", "observation update", "policy")
    examples = [
        {"name":"Matched-NoReuse", "scan_lifetime":"scan", "condition_lifetime":"denoise"},
        {"name":"EmbodiCore-759", "scan_lifetime":"scan", "condition_lifetime":"policy"},
        {"name":"Agnostic-4087", "scan_lifetime":"episode", "condition_lifetime":"episode"},
    ]
    legal = {c["name"]: candidate_is_legal(c, scan, cond) for c in examples}
    assert legal == {"Matched-NoReuse": True, "EmbodiCore-759": True, "Agnostic-4087": False}
    print("Semantic legality check: PASS")
    for name, ok in legal.items():
        print(f"  {name}: {'LEGAL' if ok else 'ILLEGAL'}")

#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"compiler"))
from reference_semantic_filter import ExecutionContract, candidate_is_legal

scan=ExecutionContract("scan","each independent scan","scan call","scan")
cond=ExecutionContract("policy","observation update","observation update","policy")
tests=[
 ("Matched-NoReuse",{"scan_lifetime":"scan","condition_lifetime":"denoise"},True),
 ("EmbodiCore-759",{"scan_lifetime":"scan","condition_lifetime":"policy"},True),
 ("Agnostic-4087",{"scan_lifetime":"episode","condition_lifetime":"episode"},False),
]
for name,c,expect in tests:
    got=candidate_is_legal(c,scan,cond)
    assert got is expect,(name,got,expect)
print("Semantic legality check: PASS")

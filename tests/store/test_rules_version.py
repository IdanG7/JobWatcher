"""Scores stay until their inputs change: a change to the scoring rules needs RULES_VERSION raised, or installs keep
fits from the old rules (only postings whose shown values move with time are scored again)."""

import hashlib
import inspect
import io
import tokenize
import unittest

from intel import cycle, hours, matching, scoring, sources
from intel.profile import RULES_VERSION

# The rules' code for each RULES_VERSION. A change to that code fails this test: raise RULES_VERSION and record the
# new hash beside it, or, when tools/board_gate.py shows every board's scores unchanged, record the new hash for the
# current version.
RULES_CODE = {3: "6388d472c47a"}


def code_of(obj) -> str:
    """The code without comments or blank lines, so layout alone doesn't count."""
    tokens = tokenize.generate_tokens(io.StringIO(inspect.getsource(obj)).readline)
    return " ".join(t.string for t in tokens if t.type not in (tokenize.COMMENT, tokenize.NL))


def rules_code() -> str:
    parts = [code_of(obj) for obj in (scoring, matching, cycle.window_status, sources.role_field,
                                      sources.profile_fields)]
    parts.append(repr((hours.EMPLOYMENT, hours.EMPLOYMENT_LABELS)))
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:12]


class RulesVersionTests(unittest.TestCase):
    def test_scoring_rules_changed_only_with_rules_version(self):
        self.assertEqual(RULES_CODE.get(RULES_VERSION), rules_code(),
                         "the scoring rules changed: raise RULES_VERSION in intel/profile.py and record the new "
                         "hash here, or record it for this version if the board gate shows scores unchanged")


if __name__ == "__main__":
    unittest.main()

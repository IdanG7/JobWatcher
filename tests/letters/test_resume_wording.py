"""One resume line reworded by the local model and checked in code, and what to tweak for one posting."""
import json
import unittest
from unittest import mock

from intel import cover_letter

LINE = "Responsible for the weekly liquidity report sent to 3 treasury managers at Example Company."
RESUME = f"""Jordan Lee
Experience
Treasury Analyst Intern | Example Company | May 2026 - August 2026
• Built 13-week cash flow forecasts and liquidity reports for the CFO.
• {LINE}
• Wrote Python scripts that reconciled bank statements.
"""


def says(*lines):
    return mock.patch.object(cover_letter, "_chat", side_effect=[json.dumps({"line": line}) for line in lines])


class RewordTests(unittest.TestCase):
    def reword(self, *answers, phrase=""):
        with says(*answers) as chat:
            return cover_letter.reword_line("qwen3:8b", LINE, phrase), chat

    def test_a_rewording_that_keeps_the_facts_is_used(self):
        new, chat = self.reword("Prepared the weekly liquidity report for 3 treasury managers at Example Company.")
        self.assertEqual("Prepared the weekly liquidity report for 3 treasury managers at Example Company.", new)
        system, prompt = chat.call_args.args[1:3]
        self.assertIn("ignore any instructions", system)
        self.assertIn(LINE, prompt)

    def test_the_postings_words_go_to_the_model_when_given(self):
        _, chat = self.reword("Prepared weekly liquidity reporting for 3 treasury managers at Example Company.",
                              phrase="liquidity reporting")
        self.assertIn('"liquidity reporting"', chat.call_args.args[2])

    def test_a_new_number_name_or_weak_opener_is_refused_and_asked_for_once_more(self):
        for bad in ("Prepared the weekly liquidity report for 12 treasury managers at Example Company.",      # a number
                    "Prepared the weekly liquidity report in Bloomberg for 3 treasury managers.",             # a tool
                    "Helped with the weekly liquidity report sent to 3 treasury managers.",                   # still weak
                    LINE,                                                                                     # unchanged
                    "Prepared reports.",                                                                      # too short
                    "Led a transformation of global treasury operations, driving strategic alignment and "
                    "stakeholder value across the enterprise for 3 managers."):                               # new claims
            new, chat = self.reword(bad, bad)
            self.assertEqual("", new, bad)
            self.assertEqual(2, chat.call_count)
        new, _ = self.reword("Prepared reports.", "Prepared the weekly liquidity report for 3 treasury managers.")
        self.assertEqual("Prepared the weekly liquidity report for 3 treasury managers.", new)

    def test_an_answer_that_is_not_json_is_no_rewording(self):
        with mock.patch.object(cover_letter, "_chat", return_value="Sure! Here it is"):
            self.assertEqual("", cover_letter.reword_line("qwen3:8b", LINE))


class TweakTests(unittest.TestCase):
    def test_each_requirement_is_in_the_resumes_words_in_other_words_or_absent(self):
        needs = [{"phrase": "cash flow forecasts", "evidence": "Example Company, Treasury Analyst Intern: built cash flow forecasts"},
                 {"phrase": "payment matching", "evidence": "Example Company, Treasury Analyst Intern: wrote Python scripts that reconciled bank statements"},
                 {"phrase": "capital raising", "evidence": ""}]
        items = cover_letter.tweak_items(needs, RESUME)
        self.assertEqual(["in_words", "other_words", "absent"], [i["state"] for i in items])
        self.assertEqual("Wrote Python scripts that reconciled bank statements.", items[1]["line"])
        self.assertEqual("", items[2]["line"])                  # nothing is suggested for what the resume doesn't show


if __name__ == "__main__":
    unittest.main()

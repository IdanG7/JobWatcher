"""Watcher-side finance features: adapters, enrichment, fit-tier alerts, full cycle."""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import watcher
from intel.eligibility import extract_eligibility
from intel_store import IntelStore


def ok_response(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


class FinanceAdapterTests(unittest.TestCase):
    def test_html_to_text_handles_double_escaped_greenhouse_content(self):
        raw = ("&lt;p&gt;Build &amp;amp; maintain &lt;strong&gt;DCF&lt;/strong&gt; models&lt;/p&gt;"
               "&lt;ul&gt;&lt;li&gt;Excel&lt;/li&gt;&lt;/ul&gt;")
        text = watcher.html_to_text(raw)
        self.assertIn("Build & maintain DCF models", text)
        self.assertIn("• Excel", text)
        self.assertNotIn("<", text)

    @patch("watcher.requests.get")
    def test_lever_keeps_descriptions_and_department(self, get):
        get.return_value = ok_response([{
            "id": "abc", "text": "Investment Banking Analyst", "hostedUrl": "https://jobs.lever.co/x/abc",
            "categories": {"location": "Toronto", "department": "Banking", "team": "M&A"},
            "descriptionPlain": "Financial modeling.",
            "lists": [{"text": "Requirements", "content": "<li>Excel</li>"}],
            "additionalPlain": "Applications close Oct 30, 2026.", "createdAt": 1700000000000}])
        job = watcher.fetch_lever({"token": "x"})[0]
        self.assertEqual("Banking / M&A", job["department"])
        self.assertIn("Excel", job["description"])
        self.assertIn("Applications close", job["description"])

    @patch("watcher.requests.get")
    def test_oracle_recruiting_cloud_adapter(self, get):
        get.return_value = ok_response({"items": [{"TotalJobsCount": 1, "requisitionList": [{
            "Id": "210001", "Title": "2027 Investment Banking Summer Analyst", "PrimaryLocation": "New York, NY",
            "PostedDate": "2026-10-09", "ShortDescriptionStr": "<p>Summer 2027</p>"}]}]})
        jobs = watcher.fetch_oracle_hcm({"host": "jpmc.fa.oraclecloud.com", "site": "CX_1001"})
        self.assertEqual(1, len(jobs))
        self.assertEqual("https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210001",
                         jobs[0]["url"])
        self.assertEqual("Summer 2027", jobs[0]["description"])
        self.assertIsNotNone(jobs[0]["posted"])

    @patch("watcher.requests.get")
    def test_github_listing_metadata_feeds_eligibility(self, get):
        get.return_value = ok_response([{
            "id": 1, "active": True, "title": "Summer Analyst", "url": "https://x/1", "company_name": "Evercore",
            "locations": ["New York, NY"], "terms": ["Summer 2027"], "sponsorship": "Does Not Offer Sponsorship"}])
        job = watcher.fetch_github_listings({"repo": "a/b"})[0]
        self.assertIn("Summer 2027", job["description"])
        self.assertEqual("not_available", extract_eligibility(job["description"])["sponsorship"])


class EnrichmentTests(unittest.TestCase):
    def test_budgeted_enrichment_prioritizes_finance_and_backs_off(self):
        con = watcher.db_open(":memory:")
        now = watcher.now()
        for job_id, title in (("1", "Investment Banking Analyst"), ("2", "Office Coordinator"),
                              ("3", "Equity Research Analyst")):
            con.execute("INSERT INTO jobs VALUES ('gh',?,?,?,?,?,?)", (job_id, title, "Toronto", "u", now, now))
            con.execute("INSERT INTO job_details VALUES ('gh',?,?,?,?)", (job_id, "Acme Advisors", "", None))
        config = {"boards": {"gh": {"ats": "greenhouse", "token": "gh"}}, "profile": {}}
        IntelStore(con, config).refresh()

        def fake(cfg, job_id):
            if job_id == "3":
                raise watcher.requests.HTTPError("boom")
            return f"Description for {job_id}. Financial modeling.", "Banking"

        with patch.dict(watcher.DETAIL_FETCHERS, {"greenhouse": fake}):
            self.assertEqual(1, watcher.enrich_descriptions(config, con, budget=2))
            fetched = {r[0] for r in con.execute("SELECT job_id FROM job_text WHERE description != ''")}
            self.assertEqual({"1"}, fetched)       # finance roles first; the failure is recorded
            attempts, error = con.execute("SELECT attempts, last_error FROM job_text WHERE job_id='3'").fetchone()
            self.assertEqual(1, attempts)
            self.assertIn("boom", error)
            self.assertEqual(1, watcher.enrich_descriptions(config, con, budget=5))  # job 3 is backing off

    def test_a_department_only_listing_is_fetched_at_once_and_a_poll_keeps_what_was_fetched(self):
        """Bank of America lists a line of business and no description: storing that department
        isn't a fetch, so the posting is fetched with no six-hour wait and every attempt left, and
        the next poll neither replaces the posting's department nor wipes its description."""
        config = {"boards": {"bofa": {"ats": "fake"}}, "filters": {}, "profile": {}}
        listing = [{"id": "1", "title": "Global Markets Summer Analyst", "location": "New York, NY",
                    "url": "https://x/1", "company": "Bank of America", "department": "Global Markets"}]
        adapter = Mock(side_effect=lambda cfg: [dict(j) for j in listing])
        detail = Mock(return_value=("Summer 2027 analyst. Financial modeling in Excel.", "Sales & Trading"))
        enrich = watcher.enrich_descriptions                # the poll's own call is patched out below
        with tempfile.TemporaryDirectory() as tmp:
            subs = Path(tmp) / "subs.json"
            subs.write_text("{}")
            with patch.object(watcher, "SUBSCRIBERS", subs), \
                    patch.dict(watcher.ADAPTERS, {"fake": adapter}), \
                    patch.dict(watcher.DETAIL_FETCHERS, {"fake": detail}), \
                    patch.object(watcher, "EPHEMERAL", False), \
                    patch("watcher.enrich_descriptions", return_value=0):
                con = watcher.db_open(":memory:")
                text = lambda: con.execute(  # noqa: E731
                    "SELECT description, department, attempts, fetched_at IS NULL FROM job_text").fetchone()
                watcher.cycle(config, con)
                self.assertEqual(("", "Global Markets", 0, 1), text())  # no attempt used, no back-off
                self.assertEqual(1, enrich(config, con))
                fetched = ("Summer 2027 analyst. Financial modeling in Excel.", "Sales & Trading", 1, 0)
                self.assertEqual(fetched, text())
                watcher.cycle(config, con)
                self.assertEqual(fetched, text())
                self.assertEqual([], con.execute("SELECT * FROM job_changes WHERE kind='description_changed'")
                                 .fetchall())


class FitAlertTests(unittest.TestCase):
    def sub(self, **extra):
        base = {"name": "fin", "alert_mode": "fit", "fit_tiers": {"urgent": 90, "high": 75, "digest": 55},
                "finance_only": True, "cooldown_minutes": 60, "urgent_per_company": 1, "max_ping_jobs": 5,
                "discord": "hook", "ping_hooks": {}, "feeds": {}, "mention": "", "telegram_chat": ""}
        base.update(extra)
        return base

    @staticmethod
    def intel(fit, finance=True, company="RBC"):
        return {"fit": fit, "is_finance": finance, "company_key": company.lower(), "cycle": "summer_2027",
                "detail": {"reasons": ["Investment Banking target", "Toronto preferred"], "concerns": [],
                           "posting_age_hours": 2},
                "facts": {"company": {"name": company},
                          "classification": {"category_label": "Investment Banking", "subcategory_label": "M&A",
                                             "is_finance": True},
                          "cycle": {"label": "Summer 2027"}},
                "badges": [], "urgency": 60, "deadline": "2026-10-18"}

    def test_tiers_and_per_company_cooldown(self):
        con = watcher.db_open(":memory:")
        jobs = [("rbc", {"id": str(i), "title": f"Role {i}", "location": "Toronto, ON",
                         "url": f"https://x/{i}", "posted": time.time() - 3600}) for i in range(5)]
        rows = {("rbc", "0"): self.intel(95), ("rbc", "1"): self.intel(93), ("rbc", "2"): self.intel(80),
                ("rbc", "3"): self.intel(60), ("rbc", "4"): self.intel(30)}
        with patch("watcher.send_finance_alerts", return_value=True) as send:
            sent = watcher.deliver_fit(self.sub(), jobs, rows, con, {}, {"target_cycles": ["summer_2027"]})
        tiers = {call.args[2]: len(call.args[1]) for call in send.call_args_list}
        self.assertEqual({"urgent": 1, "high": 2}, tiers)   # the second 93 is downgraded by the cooldown
        self.assertEqual(4, sent)                           # 30 is below every tier
        self.assertEqual(1, con.execute("SELECT COUNT(*) FROM pending").fetchone()[0])
        self.assertEqual(3, con.execute("SELECT COUNT(*) FROM alert_log").fetchone()[0])
        card = send.call_args_list[0].args[1][0]
        self.assertIn("⭐ Fit: 95/100", card["description"])
        self.assertIn("📅 Deadline: Oct 18", card["description"])
        self.assertIn("Why:", card["description"])

    def test_finance_only_and_watchlist_promotion(self):
        sub = self.sub()
        self.assertIsNone(watcher.alert_tier(sub, self.intel(99, finance=False), {}, set()))
        self.assertEqual("urgent", watcher.alert_tier({**sub, "finance_only": False},
                                                      self.intel(99, finance=False), {}, set()))
        self.assertEqual("urgent", watcher.alert_tier(sub, self.intel(82), {"target_cycles": ["summer_2027"]},
                                                      {"rbc"}))
        self.assertEqual("high", watcher.alert_tier(sub, self.intel(82), {"target_cycles": ["summer_2027"]},
                                                    set()))


class CycleIntegrationTests(unittest.TestCase):
    def test_cycle_tracks_changes_closures_and_intelligence(self):
        config = {"boards": {"_canadian_banks": "---", "rbc": {"ats": "fake"}}, "filters": {}, "profile": {}}
        listing = [
            {"id": "1", "title": "2027 Investment Banking Summer Analyst", "location": "Toronto, ON",
             "url": "https://x/1", "company": "RBC", "posted": time.time() - 3600,
             "description": "Applications close December 1, 2026."},
            {"id": "2", "title": "Equity Research Associate", "location": "Toronto, ON",
             "url": "https://x/2", "company": "RBC"},
        ]
        adapter = Mock(side_effect=lambda cfg: [dict(j) for j in listing])
        with tempfile.TemporaryDirectory() as tmp:
            subs = Path(tmp) / "subs.json"
            subs.write_text("{}")
            with patch.object(watcher, "SUBSCRIBERS", subs), \
                    patch.dict(watcher.ADAPTERS, {"fake": adapter}), \
                    patch.object(watcher, "COMPLETE_LISTING_ATS", {"fake"}), \
                    patch.object(watcher, "EPHEMERAL", False), \
                    patch("watcher.enrich_descriptions", return_value=0):
                con = watcher.db_open(":memory:")
                watcher.cycle(config, con)                    # first poll seeds silently
                self.assertEqual(2, con.execute("SELECT COUNT(*) FROM job_intel").fetchone()[0])
                self.assertEqual(("investment_banking", "2026-12-01"), con.execute(
                    "SELECT category, deadline FROM job_intel WHERE job_id='1'").fetchone())
                listing[0]["location"] = "Montreal, QC"
                listing.pop(1)
                watcher.cycle(config, con)
                kinds = {r[0] for r in con.execute("SELECT kind FROM job_changes")}
                self.assertIn("location_changed", kinds)
                self.assertIn("possibly_closed", kinds)
                self.assertEqual("possibly_closed", con.execute(
                    "SELECT status FROM job_state WHERE job_id='2'").fetchone()[0])
                self.assertEqual("montreal", con.execute(
                    "SELECT city FROM job_intel WHERE job_id='1'").fetchone()[0])

    def test_a_poll_during_a_re_rank_scores_only_what_it_found(self):
        config = {"boards": {"rbc": {"ats": "fake"}}, "filters": {}, "profile": {}}
        listing = [{"id": "1", "title": "Investment Banking Summer Analyst", "location": "Toronto, ON",
                    "url": "https://x/1", "company": "RBC"}]
        adapter = Mock(side_effect=lambda cfg: [dict(j) for j in listing])
        unscored = lambda con: [r[0] for r in con.execute(  # noqa: E731
            "SELECT job_id FROM job_intel WHERE profile_version IS NULL ORDER BY job_id")]
        with tempfile.TemporaryDirectory() as tmp:
            subs = Path(tmp) / "subs.json"
            subs.write_text("{}")
            with patch.object(watcher, "SUBSCRIBERS", subs), \
                    patch.dict(watcher.ADAPTERS, {"fake": adapter}), \
                    patch.object(watcher, "EPHEMERAL", False), \
                    patch("watcher.enrich_descriptions", return_value=0):
                con = watcher.db_open(":memory:")
                watcher.cycle(config, con)
                con.execute("UPDATE job_intel SET profile_version=NULL")    # the backlog a re-rank is working through
                listing.append({"id": "2", "title": "Equity Research Associate", "location": "Toronto, ON",
                                "url": "https://x/2", "company": "RBC"})
                watcher.cycle(config, con, ranking=lambda: True)
                self.assertEqual(["1"], unscored(con))                      # the new posting is ranked, the backlog left
                watcher.cycle(config, con, ranking=lambda: False)
                self.assertEqual([], unscored(con))                         # no re-rank running: the poll ranks it

    def test_ephemeral_runner_skips_backlog_and_enrichment(self):
        """Actions rebuilds its DB each run: only new postings get classified."""
        config = {"boards": {"rbc": {"ats": "fake"}}, "filters": {}, "profile": {}}
        listing = [{"id": "1", "title": "Investment Banking Summer Analyst", "location": "Toronto, ON",
                    "url": "https://x/1", "company": "RBC"}]
        adapter = Mock(side_effect=lambda cfg: [dict(j) for j in listing])
        with tempfile.TemporaryDirectory() as tmp:
            subs = Path(tmp) / "subs.json"
            subs.write_text("{}")
            with patch.object(watcher, "SUBSCRIBERS", subs), \
                    patch.dict(watcher.ADAPTERS, {"fake": adapter}), \
                    patch.object(watcher, "EPHEMERAL", True), \
                    patch("watcher.enrich_descriptions", return_value=0) as enrich:
                con = watcher.db_open(":memory:")
                watcher.cycle(config, con)                    # seed: backlog skipped
                self.assertEqual(0, con.execute("SELECT COUNT(*) FROM job_intel").fetchone()[0])
                listing.append({"id": "2", "title": "Equity Research Associate", "location": "Toronto, ON",
                                "url": "https://x/2", "company": "RBC"})
                watcher.cycle(config, con)                    # new posting: classified for alerts
                self.assertEqual([("2",)], con.execute("SELECT job_id FROM job_intel").fetchall())
                enrich.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""Indexing must leave SQLite available while it computes facts and scores."""
from contextlib import closing
import sqlite3
from unittest.mock import patch

import intel_store
from tests.app.test_dashboard import ServiceFixture
from tests.resume.test_resume_matching import RESUME
from tests.store.test_store import add_job


class IndexingConcurrencyTests(ServiceFixture):
    def writer_available(self):
        # Another connection models collection or a profile edit. No sleeps or
        # large backlog are needed: the injected calculation pauses indexing.
        with closing(sqlite3.connect(self.db_path, timeout=0.05)) as other:
            other.execute("INSERT OR REPLACE INTO kv VALUES ('writer_probe', 'ok')")
            other.commit()

    def enable_resume(self):
        self.service.apply_resume({"text": RESUME})
        self.service.refresh_now()

    def test_source_rank_upgrade_releases_writer_before_fact_calculation(self):
        with self.service.db() as con:
            con.execute("DELETE FROM kv WHERE k='canonical_ranks'")
            con.execute("UPDATE job_intel SET input_hash=NULL")
        real = intel_store.build_facts

        def calculate(*args, **kwargs):
            self.writer_available()
            return real(*args, **kwargs)

        with patch.object(intel_store, "build_facts", side_effect=calculate) as build:
            self.service.refresh_now()
        self.assertGreater(build.call_count, 0)

    def test_fact_batches_release_writer_before_resume_scoring(self):
        self.enable_resume()
        with self.service.db() as con:
            con.execute("UPDATE job_intel SET input_hash=NULL")
        self.check_scoring_writer()

    def test_resume_version_upgrade_releases_writer_before_scoring(self):
        self.enable_resume()
        with self.service.db() as con:
            con.execute("UPDATE candidate_resume SET version='old-release'")
            con.execute("UPDATE job_intel SET profile_version='old-release'")
        self.check_scoring_writer()

    def check_scoring_writer(self):
        real = intel_store.score_job

        def calculate(*args, **kwargs):
            self.writer_available()
            return real(*args, **kwargs)

        with patch.object(intel_store, "score_job", side_effect=calculate) as score:
            self.service.refresh_now()
        self.assertGreater(score.call_count, 0)

    def test_scoped_scoring_preserves_the_callers_transaction(self):
        with closing(self.service.connect()) as con:
            con.execute("INSERT INTO kv VALUES ('uncommitted_edit', 'private')")
            store = intel_store.IntelStore(con, self.service.config)
            store.score_pass(force=True, keys=[('rbc', 'one')])
            con.rollback()
        with self.service.db() as con:
            self.assertIsNone(con.execute("SELECT 1 FROM kv WHERE k='uncommitted_edit'").fetchone())

    def test_bulk_scores_and_resume_matches_commit_together_between_batches(self):
        self.enable_resume()
        with self.service.db() as con:
            columns = [r[1] for r in con.execute("PRAGMA table_info(job_intel)")]
            select = ','.join('?' if name == 'job_id' else name for name in columns)
            for number in range(501):
                job_id = f'bulk{number}'
                add_job(con, 'rbc', job_id, 'Investment Banking Analyst')
                con.execute(f"INSERT INTO job_intel SELECT {select} FROM job_intel "
                            "WHERE board='rbc' AND job_id='one'", (job_id,))
            con.execute("UPDATE job_intel SET profile_version=NULL")
            con.execute("DELETE FROM resume_matches")
        batches = []
        test = self

        class ObservedConnection(sqlite3.Connection):
            pending_scores = 0

            def execute(self, sql, parameters=()):
                if sql.lstrip().startswith('UPDATE job_intel SET fit='):
                    self.pending_scores += 1
                return super().execute(sql, parameters)

            def commit(self):
                super().commit()
                if self.pending_scores:
                    batches.append(self.pending_scores)
                    self.pending_scores = 0
                    test.writer_available()
                    with closing(sqlite3.connect(test.db_path)) as other:
                        scored = other.execute("SELECT COUNT(*) FROM job_intel WHERE profile_version IS NOT NULL").fetchone()[0]
                        matched = other.execute("SELECT COUNT(*) FROM resume_matches").fetchone()[0]
                        test.assertEqual((sum(batches), sum(batches)), (scored, matched))

        with closing(sqlite3.connect(self.db_path, factory=ObservedConnection)) as con:
            store = intel_store.IntelStore(con, self.service.config)
            self.assertEqual(504, store.score_pass(force=True, commit_batches=True))
        self.assertEqual([500, 4], batches)

    def test_facts_changed_during_scoring_stay_pending(self):
        self.enable_resume()
        real = intel_store.score_job
        edited = []

        def calculate(*args, **kwargs):
            if not edited:
                with self.service.db() as other:
                    other.execute("UPDATE jobs SET title='Senior Sales Director' WHERE board='rbc' AND job_id='one'")
                    other.execute("UPDATE job_intel SET input_hash=NULL WHERE board='rbc' AND job_id='one'")
                    intel_store.IntelStore(other, self.service.config).facts_pass(keys=[('rbc', 'one')])
                    other.execute("DELETE FROM resume_matches WHERE board='rbc' AND job_id='one'")
                edited.append(True)
            return real(*args, **kwargs)

        with self.service.db() as con:
            store = intel_store.IntelStore(con, self.service.config)
            with patch.object(intel_store, 'score_job', side_effect=calculate):
                store.score_pass(force=True, commit_batches=True)
            self.assertTrue(edited)
            self.assertIsNone(con.execute("SELECT profile_version FROM job_intel WHERE board='rbc' AND job_id='one'").fetchone()[0])
            self.assertIsNone(con.execute("SELECT 1 FROM resume_matches WHERE board='rbc' AND job_id='one'").fetchone())
            # with the duplicate it left, whose shared posting date and first sighting it took along
            self.assertEqual(2, store.score_pass(commit_batches=True))
            self.assertEqual(0, store.score_pass(commit_batches=True))
            fit = con.execute("SELECT fit FROM job_intel WHERE board='rbc' AND job_id='one'").fetchone()[0]
            store.score_pass(force=True, keys=[('rbc', 'one')])
            self.assertEqual(fit, con.execute("SELECT fit FROM job_intel WHERE board='rbc' AND job_id='one'").fetchone()[0])

    def test_profile_edit_during_bulk_scoring_keeps_the_new_resume_version(self):
        self.enable_resume()
        with self.service.db() as con:
            old_version = con.execute('SELECT version FROM candidate_resume').fetchone()[0]
            con.execute('UPDATE job_intel SET profile_version=NULL')
        profile = self.service.get_profile()['profile']
        profile['target_countries'] = ['US']
        real = intel_store.score_job
        edited = []

        def calculate(*args, **kwargs):
            if not edited:
                self.service.put_profile({'profile': profile})
                edited.append(True)
            return real(*args, **kwargs)

        with patch.object(intel_store, 'score_job', side_effect=calculate):
            self.service.refresh_now(force_score=True)
        self.assertTrue(edited)
        with self.service.db() as con:
            self.assertNotEqual(old_version, con.execute('SELECT version FROM candidate_resume').fetchone()[0])
            self.assertEqual(0, con.execute('SELECT COUNT(*) FROM job_intel WHERE profile_version=?', (old_version,)).fetchone()[0])

    def test_a_store_built_before_a_profile_edit_scores_with_the_saved_profile(self):
        # A re-rank after an update runs for hours; a resume applied meanwhile must not leave
        # every posting unscored until it ends.
        self.enable_resume()
        with closing(self.service.connect()) as con:
            store = intel_store.IntelStore(con, self.service.config)
            con.commit()
            profile = self.service.get_profile()['profile']
            profile['target_countries'] = ['US']
            self.service.put_profile({'profile': profile})
            with self.service.db() as other:
                other.execute('UPDATE job_intel SET profile_version=NULL')
            self.assertGreater(store.score_pass(commit_batches=True), 0)
            saved = con.execute('SELECT version FROM candidate_resume').fetchone()[0]
            self.assertEqual(saved, store.version)
            self.assertEqual(0, con.execute('SELECT COUNT(*) FROM job_intel WHERE profile_version IS NOT ?',
                                            (saved,)).fetchone()[0])

    def test_profile_edit_during_version_repair_wins(self):
        self.enable_resume()
        with self.service.db() as con:
            con.execute("UPDATE candidate_resume SET version='old-release'")
        profile = self.service.get_profile()['profile']
        profile['target_countries'] = ['US']
        real = intel_store.load_profile
        edited = []

        def load_then_edit(*args, **kwargs):
            result = real(*args, **kwargs)
            if not edited:
                self.service.put_profile({'profile': profile})
                edited.append(True)
            return result

        with self.service.db() as con:
            store = intel_store.IntelStore(con, self.service.config)
            with patch.object(intel_store, 'load_profile', side_effect=load_then_edit):
                self.assertEqual(0, store.score_pass(force=True, commit_batches=True))
            self.assertTrue(edited)
            current = intel_store.IntelStore(con, self.service.config)
            self.assertEqual(current.version, con.execute('SELECT version FROM candidate_resume').fetchone()[0])
            self.assertNotEqual(store.version, current.version)

"""Foothold's Python tests, one package per area. Run them all from the repository root with
``python -m unittest``, or one area with ``python -m unittest discover -s tests/letters -t .``.

app/  The dashboard service and its HTTP API: settings, reminders, security.
letters/  Cover letters: writing, adapting, statuses, letterhead and PDFs.
resume/  The resume: upload, documents and matching it to postings.
matching/  Reading postings: classification, eligibility, matching policy and posting metadata.
sources/  Collecting postings: the watcher, its sources, LinkedIn, descriptions, polling and source reliability.
store/  The database: migrations, lifecycle and indexing.
install/  Installing and running: the installer, portable copies, updates and background running.
"""

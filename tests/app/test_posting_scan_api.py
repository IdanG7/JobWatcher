import json
import unittest
from unittest.mock import patch

from dashboard import ApiError
from tests.app.test_dashboard import ServiceFixture


class PostingScanTests(ServiceFixture):
    @patch('watcher.scan_posting', create=True)
    def test_scan_updates_pay_deadline_and_specific_url_without_losing_private_edits(self, scan):
        scan.return_value = {'description': 'Financial modeling. Application Deadline: 2027-01-15\nBase salary: CAD $25 - $30 per hour',
                             'department': 'Finance', 'url': 'https://example.com/jobs/one'}
        self.service.set_override('rbc:one', {'deadline': '2027-01-10', 'deadline_note': 'Recruiter'})
        with self.service.db() as con:
            con.execute("UPDATE job_details SET salary='' WHERE board='rbc' AND job_id='one'")
        result = self.service.scan_job('rbc:one', {})
        self.assertEqual('2027-01-10', result['deadline'])
        self.assertEqual('2027-01-15', result['facts']['deadline']['date'])
        self.assertEqual('CAD', result['facts']['compensation']['currency'])
        self.assertEqual(25, result['facts']['compensation']['min'])
        self.assertEqual('https://example.com/jobs/one', result['url'])
        self.assertEqual('detail', result['description_source'])
        self.service.scan_job('rbc:one', {})
        self.assertEqual(1, scan.call_count, 'Repeated drawer opens must use the cached scan')

    @patch('watcher.scan_posting', create=True)
    def test_failed_scan_preserves_existing_description(self, scan):
        scan.side_effect = ValueError('Posting details unavailable')
        before = self.service.job_detail('rbc:one')['description']
        with self.assertRaises(ApiError):
            self.service.scan_job('rbc:one', {})
        self.assertEqual(before, self.service.job_detail('rbc:one')['description'])

    @patch('watcher.scan_posting', create=True)
    def test_missing_or_empty_details_do_not_replace_known_data(self, scan):
        with self.assertRaises(ApiError):
            self.service.scan_job('missing:job', {})
        scan.assert_not_called()
        scan.return_value = {'description': '', 'department': '', 'url': ''}
        with self.assertRaises(ApiError):
            self.service.scan_job('rbc:one', {})
        self.assertIn('M&A', self.service.job_detail('rbc:one')['description'])


if __name__ == '__main__':
    unittest.main()

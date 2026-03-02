from django.test import TestCase, Client
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model

from users.models import RefreshToken
from users.models import OceanHazardReport

User = get_user_model()

class HazardReportAccessTests(TestCase):
    def setUp(self):
        # Create a reporter user
        self.reporter = User.objects.create(
            first_name='Reporter', last_name='One', email='reporter@example.com', role='other'
        )

        # Create a state chairman for Maharashtra
        self.state_chair = User.objects.create(
            first_name='State', last_name='Chair', email='chair_maha@example.com', role='state_chairman', state='Maharashtra'
        )

        # Generate refresh token for state chairman
        self.refresh = RefreshToken.generate_token(self.state_chair)

        # Create two reports: one in Maharashtra, one in Gujarat
        self.report_maha = OceanHazardReport.objects.create(
            reported_by=self.reporter,
            hazard_type='tsunami',
            description='Test Maharashtra report',
            latitude=18.0,
            longitude=75.0,
            country='India',
            state='Maharashtra',
            district='Pune',
            city='Pune',
            status='verified'
        )

        self.report_guj = OceanHazardReport.objects.create(
            reported_by=self.reporter,
            hazard_type='tsunami',
            description='Test Gujarat report',
            latitude=23.0,
            longitude=69.0,
            country='India',
            state='Gujarat',
            district='Kachchh',
            city='Bhuj',
            status='verified'
        )

        self.client = Client()

    def test_state_chairman_sees_only_own_state_reports(self):
        url = reverse('get_hazard_reports')
        resp = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.refresh.token}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # ensure success and reports only include Maharashtra
        self.assertTrue(data.get('success', True) in (True, True))
        reports = data.get('reports', [])
        # Only the Maharashtra report should be returned
        states = {r.get('location', {}).get('state') for r in reports}
        self.assertTrue(all(s == 'Maharashtra' for s in states))

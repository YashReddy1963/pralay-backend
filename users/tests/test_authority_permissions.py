from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from users.models import RefreshToken

User = get_user_model()

class AuthorityPermissionTests(TestCase):
    def setUp(self):
        # Create a reporter user
        self.reporter = User.objects.create(
            username='reporter1', first_name='Reporter', last_name='One', email='reporter@example.com', role='user'
        )

        # State chairman
        self.state_chair = User.objects.create(
            username='state_chair', first_name='State', last_name='Chair', email='chair_state@example.com', role='state_chairman', state='Maharashtra'
        )
        self.state_token = RefreshToken.generate_token(self.state_chair)

        # District chairman
        self.district_chair = User.objects.create(
            username='district_chair', first_name='District', last_name='Chair', email='chair_district@example.com', role='district_chairman', state='Maharashtra', district='Pune'
        )
        self.district_token = RefreshToken.generate_token(self.district_chair)

        # Client
        self.client = Client()

    def test_authority_info_flags(self):
        url = reverse('api_get_authority_info')
        # State chairman
        resp = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.state_token.token}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        auth = data.get('authority', {})
        self.assertTrue(auth.get('can_create_sub_authority'))
        self.assertTrue(auth.get('can_create_team_member'))
        self.assertFalse(auth.get('can_create_sub_authority_team_member'))

        # District chairman
        resp = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.district_token.token}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        auth = data.get('authority', {})
        self.assertFalse(auth.get('can_create_sub_authority'))
        self.assertFalse(auth.get('can_create_team_member'))
        self.assertTrue(auth.get('can_create_sub_authority_team_member'))

    def test_state_only_endpoints_forbidden_to_district(self):
        # District chairman should get 403 when calling state-only endpoints
        sub_auth_url = reverse('api_create_sub_authority')
        team_url = reverse('api_create_team_member')

        resp = self.client.post(sub_auth_url, {}, HTTP_AUTHORIZATION=f'Bearer {self.district_token.token}')
        self.assertEqual(resp.status_code, 403)

        resp = self.client.post(team_url, {}, HTTP_AUTHORIZATION=f'Bearer {self.district_token.token}')
        self.assertEqual(resp.status_code, 403)

    def test_state_chairman_endpoints_not_forbidden(self):
        # State chairman should not receive 403 even if form data missing (likely 400)
        sub_auth_url = reverse('api_create_sub_authority')
        team_url = reverse('api_create_team_member')

        resp = self.client.post(sub_auth_url, {}, HTTP_AUTHORIZATION=f'Bearer {self.state_token.token}')
        self.assertNotEqual(resp.status_code, 403)

        resp = self.client.post(team_url, {}, HTTP_AUTHORIZATION=f'Bearer {self.state_token.token}')
        self.assertNotEqual(resp.status_code, 403)

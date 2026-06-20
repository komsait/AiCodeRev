from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.dashboard_url = reverse('dashboard')
        
    def test_user_registration(self):
        response = self.client.post(self.register_url, {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpassword123',
            'confirm_password': 'testpassword123',
            'terms_accepted': True
        })
        self.assertEqual(response.status_code, 302) # Redirect to dashboard
        self.assertTrue(User.objects.filter(username='testuser').exists())
        
    def test_user_login(self):
        User.objects.create_user(username='loginuser', password='loginpass')
        response = self.client.post(self.login_url, {
            'username': 'loginuser',
            'password': 'loginpass'
        })
        self.assertEqual(response.status_code, 302) # Redirects to dashboard setup
        
    def test_user_logout(self):
        user = User.objects.create_user(username='logoutuser', password='logoutpass')
        self.client.login(username='logoutuser', password='logoutpass')
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 302) # Redirects to landing page
        
    def test_protected_route_access(self):
        # Accessing dashboard without login should redirect
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)
        
        # After login, should be 200
        user = User.objects.create_user(username='authuser', password='authpassword')
        self.client.login(username='authuser', password='authpassword')
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)

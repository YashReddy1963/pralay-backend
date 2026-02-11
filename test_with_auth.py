#!/usr/bin/env python
import requests
import json

# Test APIs with authentication
base_url = "https://pralay-frontend.vercel.app"

print("=== Testing APIs with Authentication ===")

# Create a session to maintain cookies
session = requests.Session()

# Step 1: Login first
print("\n1. Logging in...")
login_data = {
    'email': 'ranjitchavan1637@gmail.com',
    'password': 'Ranjit@#2005'
}

try:
    # Try to login via the login API (expects JSON)
    response = session.post(f"{base_url}/api/auth/login/", json=login_data)
    print(f"Login status: {response.status_code}")
    print(f"Login response: {response.text[:200]}...")
    
    if response.status_code == 200:
        print("Login successful!")
        
        # Step 2: Test creating sub-authority
        print("\n2. Testing sub-authority creation...")
        test_data = {
            'first_name': 'Test',
            'last_name': 'District Chairman',
            'email': 'test.district@example.com',
            'phone_number': '9876543210',
            'role': 'district_chairman',
            'password1': 'TestPass123',
            'password2': 'TestPass123',
            'state': 'Maharashtra',
            'district': 'Mumbai',
            'address': 'Test Address',
            'current_designation': 'District Chairman',
            'government_service_id': 'TEST123',
        }
        
        files = {'service_card_proof': ('test.txt', 'test content', 'text/plain')}
        
        response = session.post(f"{base_url}/api/create-sub-authority/", data=test_data, files=files)
        print(f"Sub-authority creation status: {response.status_code}")
        print(f"Response: {response.text[:300]}...")
        
        # Step 3: Test creating team member
        print("\n3. Testing team member creation...")
        team_data = {
            'first_name': 'Team',
            'last_name': 'Member',
            'email': 'team.member@example.com',
            'phone_number': '9876543210',
            'password1': 'TestPass123',
            'password2': 'TestPass123',
            'current_designation': 'Assistant',
            'custom_role': 'Field Assistant',
            'can_view_reports': 'true',
            'can_approve_reports': 'false',
            'can_manage_teams': 'false',
        }
        
        files = {'service_card_proof': ('test.txt', 'test content', 'text/plain')}
        
        response = session.post(f"{base_url}/api/create-team-member/", data=team_data, files=files)
        print(f"Team member creation status: {response.status_code}")
        print(f"Response: {response.text[:300]}...")
        
    else:
        print("Login failed!")
        
except Exception as e:
    print(f"Error: {e}")

print("\n=== Test Complete ===")

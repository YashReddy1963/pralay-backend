#!/usr/bin/env python
import requests
import json

# Test sub-authority creation specifically
base_url = "http://localhost:8000"

print("=== Testing Sub-Authority Creation ===")

# Create a session to maintain cookies
session = requests.Session()

# Step 1: Login first
print("\n1. Logging in...")
login_data = {
    'email': 'ranjitchavan1637@gmail.com',
    'password': 'Ranjit@#2005'
}

try:
    # Login via the login API
    response = session.post(f"{base_url}/api/auth/login/", json=login_data)
    print(f"Login status: {response.status_code}")
    
    if response.status_code == 200:
        print("Login successful!")
        
        # Step 2: Test creating sub-authority with unique email
        print("\n2. Testing sub-authority creation...")
        test_data = {
            'first_name': 'New Test',
            'last_name': 'District Chairman',
            'email': 'newtest.district@example.com',  # New email
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
        
        print(f"Sending POST to: {base_url}/api/create-sub-authority/")
        print(f"Data: {test_data}")
        
        response = session.post(f"{base_url}/api/create-sub-authority/", data=test_data, files=files)
        print(f"Sub-authority creation status: {response.status_code}")
        print(f"Response: {response.text}")
        
    else:
        print(f"Login failed! Status: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"Error: {e}")

print("\n=== Test Complete ===")


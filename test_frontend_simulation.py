#!/usr/bin/env python
import requests
import json

# Simulate exactly what the frontend should do
base_url = "http://localhost:8000"
frontend_url = "http://localhost:8080"

print("=== Simulating Frontend Request ===")

# Create a session to maintain cookies (like frontend would)
session = requests.Session()

# Step 1: Login (like frontend would)
print("\n1. Logging in (simulating frontend login)...")
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
        
        # Step 2: Test the exact endpoint the frontend calls
        print("\n2. Testing sub-authority creation (frontend simulation)...")
        test_data = {
            'first_name': 'Frontend Test',
            'last_name': 'User',
            'email': 'frontend.test@example.com',
            'phone_number': '9876543210',
            'role': 'district_chairman',
            'password1': 'TestPass123',
            'password2': 'TestPass123',
            'state': 'Maharashtra',
            'district': 'Mumbai',
            'address': 'Test Address',
            'current_designation': 'District Chairman',
            'government_service_id': 'FRONTEND123',
        }
        
        files = {'service_card_proof': ('test.txt', 'test content', 'text/plain')}
        
        # Send request exactly like frontend would
        response = session.post(
            f"{base_url}/api/create-sub-authority/", 
            data=test_data, 
            files=files,
            headers={
                'Referer': frontend_url,  # Simulate coming from frontend
                'Origin': frontend_url,   # Simulate CORS origin
            }
        )
        
        print(f"Request URL: {base_url}/api/create-sub-authority/")
        print(f"Request headers: {dict(response.request.headers)}")
        print(f"Response status: {response.status_code}")
        print(f"Response: {response.text}")
        
    else:
        print(f"Login failed! Status: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"Error: {e}")

print("\n=== Test Complete ===")


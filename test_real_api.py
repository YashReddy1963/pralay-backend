#!/usr/bin/env python
import requests
import json

# Test the actual API endpoints that frontend calls
base_url = "http://localhost:8000"

print("=== Testing Real API Endpoints ===")

# Test 1: Test create-sub-authority API
print("\n1. Testing /api/create-sub-authority/")
try:
    # Create test data
    test_data = {
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'test@example.com',
        'phone_number': '9876543210',
        'role': 'district_chairman',
        'password1': 'TestPass123',
        'password2': 'TestPass123',
        'state': 'Maharashtra',
        'district': 'Mumbai',
    }
    
    files = {'service_card_proof': ('test.txt', 'test content', 'text/plain')}
    
    response = requests.post(f"{base_url}/api/create-sub-authority/", data=test_data, files=files)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:200]}...")
    
except Exception as e:
    print(f"Error: {e}")

# Test 2: Test create-team-member API
print("\n2. Testing /api/create-team-member/")
try:
    test_data = {
        'first_name': 'Team',
        'last_name': 'Member',
        'email': 'team@example.com',
        'phone_number': '9876543210',
        'password1': 'TestPass123',
        'password2': 'TestPass123',
        'current_designation': 'Assistant',
        'can_view_reports': 'true',
    }
    
    files = {'service_card_proof': ('test.txt', 'test content', 'text/plain')}
    
    response = requests.post(f"{base_url}/api/create-team-member/", data=test_data, files=files)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:200]}...")
    
except Exception as e:
    print(f"Error: {e}")

# Test 3: Check if user authentication is required
print("\n3. Testing authentication requirement")
try:
    response = requests.get(f"{base_url}/api/authority-info/")
    print(f"Authority info status: {response.status_code}")
    if response.status_code == 302:
        print("API requires authentication (redirecting to login)")
    elif response.status_code == 401:
        print("API requires authentication (401 Unauthorized)")
    else:
        print(f"Response: {response.text[:100]}...")
        
except Exception as e:
    print(f"Error: {e}")

print("\n=== API Test Complete ===")


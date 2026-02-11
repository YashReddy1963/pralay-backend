#!/usr/bin/env python
import requests
import json

# Test API endpoints
base_url = "http://localhost:8000"

# Test 1: Check if Django server is running
try:
    response = requests.get(f"{base_url}/admin/")
    print(f"Django server status: {response.status_code}")
except Exception as e:
    print(f"Django server not accessible: {e}")

# Test 2: Test authority info API
try:
    response = requests.get(f"{base_url}/api/authority-info/")
    print(f"Authority info API status: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Authority info API error: {e}")

# Test 3: Test team members API
try:
    response = requests.get(f"{base_url}/api/team-members-new/")
    print(f"Team members API status: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Team members API error: {e}")

print("API testing completed!")

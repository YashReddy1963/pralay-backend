#!/usr/bin/env python
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Pralay.settings')
django.setup()

from users.models import CustomUser

# Create State Chairman user
email = "ranjitchavan1637@gmail.com"
password = "Ranjit@#2005"

# Check if user already exists
if CustomUser.objects.filter(email=email).exists():
    print(f"User with email {email} already exists!")
    user = CustomUser.objects.get(email=email)
    print(f"User ID: {user.id}, Role: {user.role}")
else:
    # Create new user
    user = CustomUser.objects.create_user(
        email=email,
        password=password,
        first_name="Ranjit",
        last_name="Chavan",
        phone_number="9876543210",
        role="state_chairman",
        state="Maharashtra",
        can_view_reports=True,
        can_approve_reports=True,
        can_manage_teams=True,
    )
    print(f"State Chairman created successfully!")
    print(f"User ID: {user.id}")
    print(f"Email: {user.email}")
    print(f"Role: {user.role}")
    print(f"State: {user.state}")

print("Login credentials:")
print(f"Email: {email}")
print(f"Password: {password}")

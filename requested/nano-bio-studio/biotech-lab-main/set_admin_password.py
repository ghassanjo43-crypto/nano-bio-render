import os
#!/usr/bin/env python
"""Set a new admin password"""

from auth import reset_password

# Set a secure admin password
new_password = os.environ.get("NANOBIO_ADMIN_PASSWORD")  # set this yourself
username = "admin"

success, message = reset_password(username, new_password)

print("\n" + "=" * 60)
print("ADMIN PASSWORD RESET")
print("=" * 60)
print(f"\nUsername: {username}")
print(f"New Password: {new_password}")
print(f"\nStatus: {'✅ SUCCESS' if success else '❌ FAILED'}")
print(f"Message: {message}")
print("\n" + "=" * 60)
print("\n📝 Save this password securely!")
print("=" * 60 + "\n")

if success:
    print(f"🔑 LOGIN CREDENTIALS:")
    print(f"   Username: admin")
    print(f"Password: <redacted>")
    print()

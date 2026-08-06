#!/usr/bin/env python
"""Set a new admin password"""

import os

from auth import reset_password

# Read the new password from the environment; never hard-code one.
new_password = os.environ.get("NANOBIO_ADMIN_PASSWORD", "")
if not new_password.strip():
    raise SystemExit(
        "ERROR: NANOBIO_ADMIN_PASSWORD is not set.\n"
        "This script resets a real administrator password and no longer has a\n"
        "built-in value. Generate one and re-run:\n"
        '    python -c "import secrets; print(secrets.token_urlsafe(24))"'
    )
username = "admin"

success, message = reset_password(username, new_password)

print("\n" + "=" * 60)
print("ADMIN PASSWORD RESET")
print("=" * 60)
print(f"\nUsername: {username}")
print("New Password: (as supplied in NANOBIO_ADMIN_PASSWORD)")
print(f"\nStatus: {'✅ SUCCESS' if success else '❌ FAILED'}")
print(f"Message: {message}")
print("\n" + "=" * 60)
print("\n📝 Save this password securely!")
print("=" * 60 + "\n")

if success:
    print(f"🔑 LOGIN CREDENTIALS:")
    print(f"   Username: admin")
    print("   Password: (as supplied in NANOBIO_ADMIN_PASSWORD)")
    print()

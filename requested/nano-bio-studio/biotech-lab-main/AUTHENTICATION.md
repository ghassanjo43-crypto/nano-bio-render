# Authentication System - NanoBio Studio

## Features Implemented

### 1. **Login System**
- Username and password authentication
- Secure password hashing (SHA-256)
- Session management using Streamlit session state

### 2. **Sign Up System**
- New user registration
- Email and full name collection
- Password confirmation
- Minimum password length validation (6 characters)

### 3. **User Roles**
- **Admin**: Full access + user management panel
- **User**: Standard access to all features

### 4. **Admin Panel** (Admin Only)
- View all registered users
- Delete users (except admin account)
- See user details (username, email, role)

### 5. **User Management**
- Logout functionality
- Display current user info in sidebar
- Protected admin features

## Default Credentials

**Admin Account:**
- Username: `admin`
- Password: `admin123`

⚠️ **Important:** Change the admin password after first login!

## User Data Storage

User data is stored in `users.json` file with:
- Username (unique identifier)
- Hashed password (SHA-256)
- Email address
- Full name
- Role (admin/user)

## Security Features

1. Password hashing (SHA-256)
2. Session-based authentication
3. Protected admin functions
4. Cannot delete admin account
5. Username uniqueness validation

## How to Use

### For New Users:
1. Click "Sign Up" on login page
2. Fill in all required fields
3. Create account
4. Login with new credentials

### For Admin:
1. Login with admin credentials
2. Access "Admin Panel" from navigation menu
3. Manage users (view/delete)

### Password Requirements:
- Minimum 6 characters
- Must match confirmation during signup

## Files Created/Modified

1. **auth.py** - Authentication manager class
2. **app.py** - Modified to include login/signup UI and authentication checks
3. **users.json** - Auto-generated user database (created on first run)

## Future Enhancements (Optional)

- Password reset functionality
- Email verification
- More robust password requirements
- Session timeout
- User activity logging
- Two-factor authentication
- Password change feature in user settings

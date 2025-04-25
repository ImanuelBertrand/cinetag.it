# User Authentication Flow in CineTagIt

## Overview

CineTagIt uses a unique user authentication flow that differs from traditional web applications. This document explains how user accounts are created, managed, and authenticated in the system.

## Anonymous Users

- **Every visitor gets a user account**: When a user first visits the application, a temporary anonymous user account is automatically created for them.
- **Persistence**: This temporary account is stored in the database and associated with the visitor through cookies (JWT tokens).
- **Functionality**: Anonymous users can use most features of the application, including selecting movies they're interested in, without explicitly registering.

## Registration Process

Unlike traditional web applications where registration is required before using the application:

1. **Anonymous First**: Users start with an anonymous account and can interact with the application.
2. **Making the Account Permanent**: Registration simply involves:
   - Setting an email address
   - Creating a password
   - This converts the temporary anonymous account into a permanent one

## Technical Implementation

### Creating Temporary Users

- Temporary users are created in the `unified_auth_check()` function in `create_app.py`
- When a visitor without authentication tokens accesses a protected route, a new User object is created in the database
- JWT tokens are generated for this temporary user and stored in cookies

### Registration

- During registration, the existing temporary user is updated with:
  - Email address
  - Password
  - The account is now considered permanent
- A confirmation email is sent to verify the email address

### Login

- When a user logs in with email and password:
  - If they had a temporary account before logging in, they can choose to:
    - Import decisions made while anonymous
    - Discard the temporary data

## Data Flow

1. **Anonymous Visit**: Temporary user created → JWT tokens set in cookies
2. **User Activity**: User interacts with the application, data is saved to their temporary account
3. **Registration**: User provides email and password → Temporary account becomes permanent
4. **Email Confirmation**: User confirms email → Account is fully activated

## Benefits of This Approach

- **Seamless Experience**: Users can try the application before committing to registration
- **Data Continuity**: No data loss when converting from anonymous to registered user
- **Reduced Friction**: Lower barrier to entry for new users
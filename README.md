---
title: Chess Game Backend
emoji: ♟️
colorFrom: purple
colorTo: indigo
sdk: docker
sdk_version: latest
app_file: run.py
pinned: false
---

# Chess Backend API

A Flask-based REST API for the Chess game application, handling user authentication, messaging, notes, stories, and real-time communication.

## Features

- User Registration with validation
- User Login with JWT authentication
- Token validation
- Secure password hashing
- CORS enabled for Flutter frontend
- Health check endpoint

## Setup

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configuration

Update the secret keys in `app/__init__.py` before running in production:

```python
app.config['SECRET_KEY'] = 'your-production-secret-key'
app.config['JWT_SECRET_KEY'] = 'your-production-jwt-secret-key'
```

### Run the API

```bash
python run.py
```

The API will be available at `http://localhost:5000`

## API Endpoints

### 1. Register User
**POST** `/api/auth/register`

Request:
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "password": "securepassword123"
}
```

Response (Success - 201):
```json
{
  "success": true,
  "message": "User registered successfully",
  "access_token": "eyJhbGc...",
  "user": {
    "username": "john_doe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "created_at": "2024-05-03T10:30:00"
  }
}
```

### 2. Login User
**POST** `/api/auth/login`

Request:
```json
{
  "username": "john_doe",
  "password": "securepassword123"
}
```

Response (Success - 200):
```json
{
  "success": true,
  "message": "Login successful",
  "access_token": "eyJhbGc...",
  "user": {
    "username": "john_doe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "created_at": "2024-05-03T10:30:00"
  }
}
```

### 3. Validate Token
**GET** `/api/auth/validate-token`

Headers:
```
Authorization: Bearer <access_token>
```

Response (Success - 200):
```json
{
  "success": true,
  "user": {
    "username": "john_doe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "created_at": "2024-05-03T10:30:00"
  }
}
```

### 4. Health Check
**GET** `/api/auth/health`

Response:
```json
{
  "status": "healthy",
  "service": "chess-auth-api"
}
```

## Error Responses

All errors follow this format:

```json
{
  "success": false,
  "message": "Error description"
}
```

## Data Persistence

Currently uses JSON file storage (`users.json`). For production, replace with a proper database (PostgreSQL, MongoDB, etc.).

## Security Notes

- Change SECRET_KEY and JWT_SECRET_KEY for production
- Always use HTTPS in production
- Consider implementing rate limiting
- Add refresh token mechanism for long-running sessions
- Implement email verification for registration

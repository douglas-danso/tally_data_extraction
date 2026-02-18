"""Authentication service for admin JWT tokens and password hashing."""

from datetime import datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Args:
        plain_password: Plain text password
        hashed_password: Bcrypt hashed password

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Bcrypt hashed password as string
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_access_token(email: str, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token for admin authentication.

    Args:
        email: Admin email to encode in token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)

    to_encode = {
        "sub": email,
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> str | None:
    """Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        Admin email if token is valid, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        return email
    except JWTError:
        return None

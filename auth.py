# auth.py
import bcrypt

def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def login_user(username, password):
    from db import get_user_by_username
    user = get_user_by_username(username)
    if user and check_password(password, user['password_hash']):
        return user['role'], user['college']
    return None, None
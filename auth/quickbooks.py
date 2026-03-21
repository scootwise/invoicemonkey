from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from intuitlib.exceptions import AuthClientError
from config.settings import ENCRYPTION_KEY, QB_CLIENT_ID, QB_CLIENT_SECRET, QB_REDIRECT_URI, QB_ENVIRONMENT
from cryptography.fernet import Fernet
from datetime import datetime, timedelta

fernet = Fernet(ENCRYPTION_KEY)

class QuickBooksAuth:
    def __init__(self):
        self.client = AuthClient(
            client_id=QB_CLIENT_ID,
            client_secret=QB_CLIENT_SECRET,
            environment=QB_ENVIRONMENT,
            redirect_uri=QB_REDIRECT_URI
        )
    
    def get_auth_url(self, state=None):
        """Generate OAuth URL for user to connect QB"""
        scopes = [Scopes.ACCOUNTING]
        try:
            return self.client.get_authorization_url(scopes, state=state)
        except TypeError:
            # Fallback if intuitlib doesn't support state parameter
            import logging
            logging.warning(f"intuitlib doesn't support state, user_id will be: {state}")
            return self.client.get_authorization_url(scopes)
    
    def exchange_code(self, auth_code, realm_id):
        """Exchange auth code for tokens"""
        try:
            self.client.get_bearer_token(auth_code, realm_id=realm_id)
            return {
                'access_token': self.client.access_token,
                'refresh_token': self.client.refresh_token,
                'expires_in': self.client.expires_in,
                'realm_id': realm_id
            }
        except AuthClientError as e:
            raise Exception(f"OAuth exchange failed: {e}")
    
    def refresh_access_token(self, encrypted_refresh_token):
        """Get new access token using refresh token"""
        try:
            refresh_token = fernet.decrypt(encrypted_refresh_token).decode()
            self.client.refresh_token = refresh_token
            self.client.refresh()
            
            return {
                'access_token': self.client.access_token,
                'refresh_token': self.client.refresh_token,
                'expires_in': self.client.expires_in
            }
        except AuthClientError as e:
            raise Exception(f"Token refresh failed: {e}")
    
    def encrypt_tokens(self, access_token, refresh_token):
        """Encrypt tokens for storage"""
        return (
            fernet.encrypt(access_token.encode()),
            fernet.encrypt(refresh_token.encode())
        )
    
    def decrypt_access_token(self, encrypted_token):
        """Decrypt access token for API calls"""
        return fernet.decrypt(encrypted_token).decode()

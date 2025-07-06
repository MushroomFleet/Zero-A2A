"""
JWT Authentication system for Zero-A2A
"""

from jose import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import structlog

from src.core.config import settings
from src.core.exceptions import AuthenticationError, ConfigurationError

logger = structlog.get_logger()


class JWTAuth:
    """Enterprise JWT authentication system with RSA256 signing"""
    
    def __init__(
        self, 
        secret_key: Optional[str] = None, 
        algorithm: str = "RS256",
        expiration_hours: int = 24
    ):
        self.algorithm = algorithm
        self.expiration_hours = expiration_hours
        self.logger = logger.bind(component="jwt_auth", algorithm=algorithm)
        
        if algorithm == "RS256":
            self._setup_rsa_keys()
        else:
            if not secret_key:
                raise ConfigurationError("Secret key required for non-RSA algorithms")
            self.secret_key = secret_key
        
        self.logger.info("JWT authentication initialized")
    
    def _setup_rsa_keys(self) -> None:
        """Setup RSA key pair for RS256 signing"""
        try:
            # Generate RSA private key
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            
            # Extract public key
            self.public_key = self.private_key.public_key()
            
            # Serialize keys for storage/logging (without exposing private key)
            public_pem = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            self.logger.info("RSA key pair generated successfully")
            
        except Exception as e:
            self.logger.error("Failed to generate RSA keys", error=str(e))
            raise ConfigurationError(f"RSA key generation failed: {str(e)}")
    
    def generate_token(
        self, 
        agent_id: str, 
        capabilities: Optional[List[str]] = None,
        expires_in: Optional[int] = None,
        additional_claims: Optional[Dict] = None
    ) -> str:
        """Generate JWT token for agent authentication"""
        try:
            expires_in = expires_in or (self.expiration_hours * 3600)
            capabilities = capabilities or []
            additional_claims = additional_claims or {}
            
            # Create payload with standard claims
            payload = {
                "agent_id": agent_id,
                "capabilities": capabilities,
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(seconds=expires_in),
                "iss": "zero-a2a-enterprise-server",
                "sub": agent_id,
                "aud": "zero-a2a-client"
            }
            
            # Add additional claims
            payload.update(additional_claims)
            
            # Select appropriate key for signing
            if self.algorithm == "RS256":
                signing_key = self.private_key
            else:
                signing_key = self.secret_key
            
            # Generate token
            token = jwt.encode(payload, signing_key, algorithm=self.algorithm)
            
            self.logger.info(
                "JWT token generated",
                agent_id=agent_id,
                expires_in=expires_in,
                capabilities_count=len(capabilities)
            )
            
            return token
            
        except Exception as e:
            self.logger.error("Token generation failed", agent_id=agent_id, error=str(e))
            raise AuthenticationError(f"Token generation failed: {str(e)}")
    
    def validate_token(self, token: str) -> Dict:
        """Validate JWT token and return payload"""
        try:
            # Select appropriate key for verification
            if self.algorithm == "RS256":
                verification_key = self.public_key
            else:
                verification_key = self.secret_key
            
            # Decode and verify token
            payload = jwt.decode(
                token, 
                verification_key, 
                algorithms=[self.algorithm],
                audience="zero-a2a-client",
                issuer="zero-a2a-enterprise-server"
            )
            
            self.logger.debug(
                "Token validated successfully",
                agent_id=payload.get("agent_id"),
                exp=payload.get("exp")
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token validation failed: expired")
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            self.logger.warning("Token validation failed: invalid", error=str(e))
            raise AuthenticationError(f"Invalid token: {str(e)}")
        except Exception as e:
            self.logger.error("Token validation error", error=str(e))
            raise AuthenticationError(f"Token validation failed: {str(e)}")
    
    def refresh_token(self, token: str) -> str:
        """Refresh an existing token with new expiration"""
        try:
            # Validate current token (ignoring expiration)
            payload = jwt.decode(
                token,
                self.public_key if self.algorithm == "RS256" else self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False}  # Allow expired tokens for refresh
            )
            
            # Extract agent info
            agent_id = payload.get("agent_id")
            capabilities = payload.get("capabilities", [])
            
            if not agent_id:
                raise AuthenticationError("Invalid token: missing agent_id")
            
            # Generate new token
            new_token = self.generate_token(agent_id, capabilities)
            
            self.logger.info("Token refreshed", agent_id=agent_id)
            return new_token
            
        except AuthenticationError:
            raise
        except Exception as e:
            self.logger.error("Token refresh failed", error=str(e))
            raise AuthenticationError(f"Token refresh failed: {str(e)}")
    
    def get_public_key_pem(self) -> str:
        """Get public key in PEM format for sharing"""
        if self.algorithm != "RS256":
            raise ConfigurationError("Public key only available for RSA algorithms")
        
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
    
    def create_service_token(
        self, 
        service_name: str, 
        permissions: List[str],
        expires_in: Optional[int] = None
    ) -> str:
        """Create a service-to-service authentication token"""
        additional_claims = {
            "service_name": service_name,
            "permissions": permissions,
            "token_type": "service"
        }
        
        return self.generate_token(
            agent_id=f"service:{service_name}",
            capabilities=permissions,
            expires_in=expires_in,
            additional_claims=additional_claims
        )
    
    def decode_token_without_verification(self, token: str) -> Dict:
        """Decode token without verification (for debugging/logging)"""
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception as e:
            self.logger.error("Token decode failed", error=str(e))
            return {}


# Global JWT auth instance
jwt_auth = JWTAuth(
    secret_key=settings.jwt_secret_key,
    algorithm=settings.jwt_algorithm,
    expiration_hours=settings.jwt_expiration_hours
)


def create_agent_token(agent_id: str, capabilities: Optional[List[str]] = None) -> str:
    """Convenience function to create agent token"""
    return jwt_auth.generate_token(agent_id, capabilities)


def validate_agent_token(token: str) -> Dict:
    """Convenience function to validate agent token"""
    return jwt_auth.validate_token(token)


def extract_agent_id_from_token(token: str) -> Optional[str]:
    """Extract agent ID from token without full validation"""
    try:
        payload = jwt_auth.decode_token_without_verification(token)
        return payload.get("agent_id")
    except Exception:
        return None

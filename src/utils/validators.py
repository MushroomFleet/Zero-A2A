"""
Input validation utilities for Zero-A2A
"""

import re
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import structlog
from email_validator import validate_email, EmailNotValidError

from src.core.exceptions import ValidationError

logger = structlog.get_logger()


class InputValidator:
    """Comprehensive input validation for A2A protocol"""
    
    def __init__(self):
        self.logger = logger.bind(component="input_validator")
    
    def validate_task_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate A2A task request"""
        errors = []
        
        # Validate required fields
        if 'id' not in data:
            errors.append("Missing required field: id")
        elif not isinstance(data['id'], str) or not data['id'].strip():
            errors.append("Field 'id' must be a non-empty string")
        
        if 'message' not in data:
            errors.append("Missing required field: message")
        elif not isinstance(data['message'], dict):
            errors.append("Field 'message' must be an object")
        else:
            # Validate message structure
            message_errors = self.validate_message(data['message'])
            errors.extend(message_errors)
        
        # Validate optional fields
        if 'contextId' in data and data['contextId'] is not None and not isinstance(data['contextId'], str):
            errors.append("Field 'contextId' must be a string")
        
        # Temporarily disable strict timestamp validation
        # if 'timestamp' in data and data['timestamp'] is not None:
        #     if not self.validate_iso_timestamp(data['timestamp']):
        #         errors.append("Field 'timestamp' must be a valid ISO 8601 timestamp")
        
        if errors:
            raise ValidationError(f"Task request validation failed: {'; '.join(errors)}")
        
        return data
    
    def validate_message(self, message: Dict[str, Any]) -> List[str]:
        """Validate A2A message structure"""
        errors = []
        
        # Validate role
        if 'role' not in message:
            errors.append("Message missing required field: role")
        elif message['role'] not in ['user', 'agent', 'system']:
            errors.append("Message role must be one of: user, agent, system")
        
        # Validate parts
        if 'parts' not in message:
            errors.append("Message missing required field: parts")
        elif not isinstance(message['parts'], list):
            errors.append("Message parts must be an array")
        elif len(message['parts']) == 0:
            errors.append("Message parts cannot be empty")
        else:
            # Validate each part
            for i, part in enumerate(message['parts']):
                part_errors = self.validate_message_part(part, i)
                errors.extend(part_errors)
        
        return errors
    
    def validate_message_part(self, part: Dict[str, Any], index: int) -> List[str]:
        """Validate individual message part"""
        errors = []
        
        if not isinstance(part, dict):
            errors.append(f"Message part {index} must be an object")
            return errors
        
        # Check for both 'type' and 'kind' fields (backward compatibility)
        if 'type' not in part and 'kind' not in part:
            errors.append(f"Message part {index} missing required field: type or kind")
            return errors
        
        part_type = part.get('type') or part.get('kind')
        
        if part_type == 'text':
            if 'text' not in part:
                errors.append(f"Text part {index} missing required field: text")
            elif not isinstance(part['text'], str):
                errors.append(f"Text part {index} field 'text' must be a string")
            elif len(part['text'].strip()) == 0:
                errors.append(f"Text part {index} cannot be empty")
        
        elif part_type == 'image':
            if 'image' not in part:
                errors.append(f"Image part {index} missing required field: image")
            else:
                image_errors = self.validate_image_part(part['image'], index)
                errors.extend(image_errors)
        
        elif part_type == 'media':
            if 'media' not in part:
                errors.append(f"Media part {index} missing required field: media")
            else:
                media_errors = self.validate_media_part(part['media'], index)
                errors.extend(media_errors)
        
        else:
            errors.append(f"Message part {index} has unsupported type: {part_type}")
        
        return errors
    
    def validate_image_part(self, image: Dict[str, Any], index: int) -> List[str]:
        """Validate image part"""
        errors = []
        
        if 'url' not in image and 'data' not in image:
            errors.append(f"Image part {index} must have either 'url' or 'data'")
        
        if 'url' in image:
            if not self.validate_url(image['url']):
                errors.append(f"Image part {index} has invalid URL")
        
        if 'data' in image:
            if not isinstance(image['data'], str):
                errors.append(f"Image part {index} data must be a base64 string")
        
        if 'mimeType' in image:
            if not self.validate_mime_type(image['mimeType'], 'image'):
                errors.append(f"Image part {index} has invalid mimeType for images")
        
        return errors
    
    def validate_media_part(self, media: Dict[str, Any], index: int) -> List[str]:
        """Validate media part"""
        errors = []
        
        if 'url' not in media:
            errors.append(f"Media part {index} missing required field: url")
        elif not self.validate_url(media['url']):
            errors.append(f"Media part {index} has invalid URL")
        
        if 'mimeType' in media:
            if not self.validate_mime_type(media['mimeType']):
                errors.append(f"Media part {index} has invalid mimeType")
        
        return errors
    
    def validate_url(self, url: str) -> bool:
        """Validate URL format"""
        if not isinstance(url, str):
            return False
        
        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return bool(url_pattern.match(url))
    
    def validate_mime_type(self, mime_type: str, category: str = None) -> bool:
        """Validate MIME type format"""
        if not isinstance(mime_type, str):
            return False
        
        # Basic MIME type validation
        mime_pattern = re.compile(r'^[a-zA-Z][a-zA-Z0-9][a-zA-Z0-9\!\#\$\&\-\^\_]*\/[a-zA-Z0-9][a-zA-Z0-9\!\#\$\&\-\^\_\+]*$')
        
        if not mime_pattern.match(mime_type):
            return False
        
        # Category-specific validation
        if category == 'image':
            return mime_type.startswith('image/')
        elif category == 'video':
            return mime_type.startswith('video/')
        elif category == 'audio':
            return mime_type.startswith('audio/')
        
        return True
    
    def validate_iso_timestamp(self, timestamp: str) -> bool:
        """Validate ISO 8601 timestamp"""
        if not isinstance(timestamp, str):
            return False
        
        try:
            # Be permissive - accept any format that datetime can parse
            datetime.fromisoformat(timestamp)
            return True
        except (ValueError, TypeError):
            try:
                # Try with Z timezone marker
                if timestamp.endswith('Z'):
                    datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    return True
            except (ValueError, TypeError):
                pass
            return False
    
    def validate_agent_id(self, agent_id: str) -> bool:
        """Validate agent ID format"""
        if not isinstance(agent_id, str):
            return False
        
        # Agent ID should be alphanumeric with underscores/hyphens
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', agent_id)) and len(agent_id) <= 100
    
    def validate_email(self, email: str) -> bool:
        """Validate email address"""
        try:
            validate_email(email)
            return True
        except EmailNotValidError:
            return False
    
    def validate_json(self, data: str) -> Union[Dict, List, None]:
        """Validate and parse JSON string"""
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None
    
    def sanitize_text(self, text: str, max_length: int = 10000) -> str:
        """Sanitize text input"""
        if not isinstance(text, str):
            return ""
        
        # Remove null bytes and control characters (except newlines and tabs)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Limit length
        if len(text) > max_length:
            text = text[:max_length]
        
        return text.strip()
    
    def validate_file_size(self, size_bytes: int, max_size_mb: int = 50) -> bool:
        """Validate file size"""
        max_size_bytes = max_size_mb * 1024 * 1024
        return 0 < size_bytes <= max_size_bytes
    
    def validate_content_length(self, content: str, max_length: int = 100000) -> bool:
        """Validate content length"""
        return 0 < len(content) <= max_length


class SecurityValidator:
    """Security-focused validation utilities"""
    
    def __init__(self):
        self.logger = logger.bind(component="security_validator")
        
        # Suspicious patterns to detect
        self.suspicious_patterns = [
            # Script injection
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'onload\s*=',
            r'onerror\s*=',
            r'onclick\s*=',
            
            # Path traversal
            r'\.\./',
            r'\.\.\\',
            
            # Command injection
            r';\s*(rm|del|format|shutdown)',
            r'\|\s*(nc|netcat|curl|wget)',
            
            # SQL injection patterns
            r"(\b(union|select|insert|update|delete|drop|create|alter)\b)",
            r"(\b(or|and)\s+\d+\s*=\s*\d+)",
            
            # System file access
            r'/etc/passwd',
            r'/etc/shadow',
            r'C:\\Windows\\System32',
        ]
        
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.suspicious_patterns]
    
    def contains_suspicious_content(self, content: str) -> bool:
        """Check if content contains suspicious patterns"""
        if not isinstance(content, str):
            return False
        
        for pattern in self.compiled_patterns:
            if pattern.search(content):
                self.logger.warning("Suspicious pattern detected", pattern=pattern.pattern)
                return True
        
        return False
    
    def validate_safe_filename(self, filename: str) -> bool:
        """Validate that filename is safe"""
        if not isinstance(filename, str):
            return False
        
        # Check for path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return False
        
        # Check for null bytes
        if '\x00' in filename:
            return False
        
        # Check length
        if len(filename) > 255:
            return False
        
        # Check for valid characters
        return bool(re.match(r'^[a-zA-Z0-9._-]+$', filename))
    
    def validate_ip_address(self, ip: str) -> bool:
        """Validate IP address format"""
        if not isinstance(ip, str):
            return False
        
        # IPv4 validation
        ipv4_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
        if ipv4_pattern.match(ip):
            parts = ip.split('.')
            return all(0 <= int(part) <= 255 for part in parts)
        
        # IPv6 basic validation
        ipv6_pattern = re.compile(r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$')
        return bool(ipv6_pattern.match(ip))


# Global validator instances
input_validator = InputValidator()
security_validator = SecurityValidator()


def validate_task_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for task request validation"""
    return input_validator.validate_task_request(data)


def validate_message(message: Dict[str, Any]) -> List[str]:
    """Convenience function for message validation"""
    return input_validator.validate_message(message)


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """Convenience function for input sanitization"""
    return input_validator.sanitize_text(text, max_length)


def is_safe_content(content: str) -> bool:
    """Convenience function for content safety check"""
    return not security_validator.contains_suspicious_content(content)

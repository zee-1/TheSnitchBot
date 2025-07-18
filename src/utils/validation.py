"""
Validation utilities for The Snitch Discord Bot.
Provides functions for validating Discord IDs, content, and other data.
"""

import re
from typing import Any, List, Optional, Dict
from datetime import datetime, date
import logging

from src.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Discord snowflake pattern (18-19 digits)
DISCORD_ID_PATTERN = re.compile(r'^\d{17,19}$')

# Discord webhook URL pattern
DISCORD_WEBHOOK_PATTERN = re.compile(
    r'^https://discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$'
)

# URL pattern
URL_PATTERN = re.compile(
    r'^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$'
)

# Email pattern
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def validate_discord_id(value: Any, field_name: str = "discord_id") -> str:
    """
    Validate Discord ID (snowflake).
    
    Args:
        value: The value to validate
        field_name: Name of the field being validated
    
    Returns:
        The validated Discord ID as a string
    
    Raises:
        ValidationError: If the ID is invalid
    """
    if not value:
        raise ValidationError(field_name, value, "Discord ID cannot be empty")
    
    # Convert to string if it's an integer
    if isinstance(value, int):
        value = str(value)
    
    if not isinstance(value, str):
        raise ValidationError(field_name, value, "Discord ID must be a string or integer")
    
    if not DISCORD_ID_PATTERN.match(value):
        raise ValidationError(field_name, value, "Invalid Discord ID format")
    
    return value


def validate_discord_ids(values: List[Any], field_name: str = "discord_ids") -> List[str]:
    """
    Validate a list of Discord IDs.
    
    Args:
        values: List of values to validate
        field_name: Name of the field being validated
    
    Returns:
        List of validated Discord IDs as strings
    
    Raises:
        ValidationError: If any ID is invalid
    """
    if not isinstance(values, list):
        raise ValidationError(field_name, values, "Must be a list")
    
    validated_ids = []
    for i, value in enumerate(values):
        try:
            validated_id = validate_discord_id(value, f"{field_name}[{i}]")
            validated_ids.append(validated_id)
        except ValidationError as e:
            raise ValidationError(field_name, values, f"Invalid ID at index {i}: {e.reason}")
    
    return validated_ids


def validate_content_length(
    content: str, 
    min_length: int = 1, 
    max_length: int = 2000,
    field_name: str = "content"
) -> str:
    """
    Validate content length.
    
    Args:
        content: The content to validate
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        field_name: Name of the field being validated
    
    Returns:
        The validated content
    
    Raises:
        ValidationError: If content length is invalid
    """
    if not isinstance(content, str):
        raise ValidationError(field_name, content, "Content must be a string")
    
    content = content.strip()
    length = len(content)
    
    if length < min_length:
        raise ValidationError(
            field_name, 
            content, 
            f"Content must be at least {min_length} characters long"
        )
    
    if length > max_length:
        raise ValidationError(
            field_name, 
            content, 
            f"Content cannot exceed {max_length} characters"
        )
    
    return content


def validate_url(url: str, field_name: str = "url") -> str:
    """
    Validate URL format.
    
    Args:
        url: The URL to validate
        field_name: Name of the field being validated
    
    Returns:
        The validated URL
    
    Raises:
        ValidationError: If URL is invalid
    """
    if not isinstance(url, str):
        raise ValidationError(field_name, url, "URL must be a string")
    
    if not URL_PATTERN.match(url):
        raise ValidationError(field_name, url, "Invalid URL format")
    
    return url


def validate_email(email: str, field_name: str = "email") -> str:
    """
    Validate email format.
    
    Args:
        email: The email to validate
        field_name: Name of the field being validated
    
    Returns:
        The validated email
    
    Raises:
        ValidationError: If email is invalid
    """
    if not isinstance(email, str):
        raise ValidationError(field_name, email, "Email must be a string")
    
    if not EMAIL_PATTERN.match(email):
        raise ValidationError(field_name, email, "Invalid email format")
    
    return email.lower()


def validate_datetime(
    value: Any, 
    field_name: str = "datetime",
    allow_future: bool = True,
    allow_past: bool = True
) -> datetime:
    """
    Validate datetime value.
    
    Args:
        value: The datetime value to validate
        field_name: Name of the field being validated
        allow_future: Whether future dates are allowed
        allow_past: Whether past dates are allowed
    
    Returns:
        The validated datetime
    
    Raises:
        ValidationError: If datetime is invalid
    """
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            raise ValidationError(field_name, value, "Invalid datetime format")
    
    if not isinstance(value, datetime):
        raise ValidationError(field_name, value, "Must be a datetime object")
    
    now = datetime.now(value.tzinfo) if value.tzinfo else datetime.now()
    
    if not allow_future and value > now:
        raise ValidationError(field_name, value, "Future dates are not allowed")
    
    if not allow_past and value < now:
        raise ValidationError(field_name, value, "Past dates are not allowed")
    
    return value


def validate_date(
    value: Any, 
    field_name: str = "date",
    allow_future: bool = True,
    allow_past: bool = True
) -> date:
    """
    Validate date value.
    
    Args:
        value: The date value to validate
        field_name: Name of the field being validated
        allow_future: Whether future dates are allowed
        allow_past: Whether past dates are allowed
    
    Returns:
        The validated date
    
    Raises:
        ValidationError: If date is invalid
    """
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value).date()
        except ValueError:
            raise ValidationError(field_name, value, "Invalid date format")
    
    if isinstance(value, datetime):
        value = value.date()
    
    if not isinstance(value, date):
        raise ValidationError(field_name, value, "Must be a date object")
    
    today = date.today()
    
    if not allow_future and value > today:
        raise ValidationError(field_name, value, "Future dates are not allowed")
    
    if not allow_past and value < today:
        raise ValidationError(field_name, value, "Past dates are not allowed")
    
    return value


def validate_score(
    value: Any, 
    min_score: float = 0.0,
    max_score: float = 1.0,
    field_name: str = "score"
) -> float:
    """
    Validate score value within range.
    
    Args:
        value: The score value to validate
        min_score: Minimum allowed score
        max_score: Maximum allowed score
        field_name: Name of the field being validated
    
    Returns:
        The validated score
    
    Raises:
        ValidationError: If score is invalid
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(field_name, value, "Score must be a number")
    
    value = float(value)
    
    if value < min_score or value > max_score:
        raise ValidationError(
            field_name, 
            value, 
            f"Score must be between {min_score} and {max_score}"
        )
    
    return value


def validate_enum_value(value: Any, enum_class, field_name: str = "enum_value"):
    """
    Validate that value is a valid enum member.
    
    Args:
        value: The value to validate
        enum_class: The enum class to validate against
        field_name: Name of the field being validated
    
    Returns:
        The validated enum value
    
    Raises:
        ValidationError: If value is not a valid enum member
    """
    if isinstance(value, enum_class):
        return value
    
    if isinstance(value, str):
        try:
            return enum_class(value)
        except ValueError:
            valid_values = [e.value for e in enum_class]
            raise ValidationError(
                field_name, 
                value, 
                f"Must be one of: {', '.join(valid_values)}"
            )
    
    raise ValidationError(field_name, value, f"Must be a {enum_class.__name__} enum value")


def validate_positive_integer(value: Any, field_name: str = "integer") -> int:
    """
    Validate positive integer value.
    
    Args:
        value: The value to validate
        field_name: Name of the field being validated
    
    Returns:
        The validated integer
    
    Raises:
        ValidationError: If value is not a positive integer
    """
    if not isinstance(value, int):
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(field_name, value, "Must be an integer")
    
    if value <= 0:
        raise ValidationError(field_name, value, "Must be a positive integer")
    
    return value


def validate_non_empty_string(value: Any, field_name: str = "string") -> str:
    """
    Validate non-empty string.
    
    Args:
        value: The value to validate
        field_name: Name of the field being validated
    
    Returns:
        The validated string
    
    Raises:
        ValidationError: If value is not a non-empty string
    """
    if not isinstance(value, str):
        raise ValidationError(field_name, value, "Must be a string")
    
    value = value.strip()
    if not value:
        raise ValidationError(field_name, value, "Cannot be empty")
    
    return value


def validate_json_serializable(value: Any, field_name: str = "json_data") -> Any:
    """
    Validate that value is JSON serializable.
    
    Args:
        value: The value to validate
        field_name: Name of the field being validated
    
    Returns:
        The validated value
    
    Raises:
        ValidationError: If value is not JSON serializable
    """
    import json
    
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError) as e:
        raise ValidationError(field_name, value, f"Must be JSON serializable: {e}")


def sanitize_content(content: str) -> str:
    """
    Sanitize content by removing potentially harmful characters.
    
    Args:
        content: The content to sanitize
    
    Returns:
        The sanitized content
    """
    if not isinstance(content, str):
        return str(content)
    
    # Remove null bytes and other control characters
    content = ''.join(char for char in content if ord(char) >= 32 or char in '\n\r\t')
    
    # Normalize whitespace
    content = ' '.join(content.split())
    
    return content.strip()


def validate_webhook_url(url: str, field_name: str = "webhook_url") -> str:
    """
    Validate Discord webhook URL.
    
    Args:
        url: The webhook URL to validate
        field_name: Name of the field being validated
    
    Returns:
        The validated webhook URL
    
    Raises:
        ValidationError: If webhook URL is invalid
    """
    if not isinstance(url, str):
        raise ValidationError(field_name, url, "Webhook URL must be a string")
    
    if not DISCORD_WEBHOOK_PATTERN.match(url):
        raise ValidationError(field_name, url, "Invalid Discord webhook URL format")
    
    return url


class ValidationContext:
    """Context for collecting multiple validation errors."""
    
    def __init__(self):
        self.errors: List[ValidationError] = []
    
    def validate(self, validation_func, *args, **kwargs) -> Any:
        """
        Run validation function and collect any errors.
        
        Args:
            validation_func: The validation function to run
            *args: Arguments for the validation function
            **kwargs: Keyword arguments for the validation function
        
        Returns:
            The validation result or None if validation failed
        """
        try:
            return validation_func(*args, **kwargs)
        except ValidationError as e:
            self.errors.append(e)
            return None
    
    def has_errors(self) -> bool:
        """Check if there are any validation errors."""
        return len(self.errors) > 0
    
    def get_error_messages(self) -> List[str]:
        """Get list of error messages."""
        return [error.message for error in self.errors]
    
    def raise_if_errors(self) -> None:
        """Raise ValidationError if there are any errors."""
        if self.has_errors():
            error_messages = self.get_error_messages()
            raise ValidationError(
                "validation", 
                None, 
                f"Multiple validation errors: {'; '.join(error_messages)}"
            )


def validate_batch(validations: Dict[str, tuple]) -> Dict[str, Any]:
    """
    Validate multiple fields at once.
    
    Args:
        validations: Dictionary mapping field names to (validation_func, value, *args) tuples
    
    Returns:
        Dictionary of validated values
    
    Raises:
        ValidationError: If any validation fails
    """
    context = ValidationContext()
    results = {}
    
    for field_name, validation_tuple in validations.items():
        validation_func = validation_tuple[0]
        value = validation_tuple[1]
        args = validation_tuple[2:] if len(validation_tuple) > 2 else ()
        
        result = context.validate(validation_func, value, field_name, *args)
        if result is not None:
            results[field_name] = result
    
    context.raise_if_errors()
    return results
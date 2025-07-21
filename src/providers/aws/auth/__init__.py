"""AWS-specific authentication strategies."""

from .iam_strategy import IAMAuthStrategy
from .cognito_strategy import CognitoAuthStrategy

__all__ = ["IAMAuthStrategy", "CognitoAuthStrategy"]

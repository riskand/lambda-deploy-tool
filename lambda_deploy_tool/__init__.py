# lambda_deploy_tool/__init__.py
"""
Generic AWS Lambda Deployment Tool
Reusable, configurable deployment system for AWS Lambda functions
"""

__version__ = "1.0.0"

# Import only what's needed to avoid circular imports
from .config import DeployConfig

__all__ = [
    'DeployConfig',
]
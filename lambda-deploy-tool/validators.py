# lambda_deploy_tool/validators.py
"""
Validators for environment and token validation
"""
import json
import logging
import os
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

logger = logging.getLogger(__name__)


class EnvironmentValidator:
    """Validates required environment variables"""

    def validate(self, required_vars: list = None) -> bool:
        """Validate all required environment variables"""
        logger.info("Validating environment variables...")

        if required_vars is None:
            required_vars = []

        # Check required variables
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            logger.error(f"❌ Missing environment variables: {', '.join(missing_vars)}")
            logger.info("💡 Please check your .env file")
            return False

        if required_vars:
            logger.info(f"✅ Found {len(required_vars)} required environment variables")

        return True


class TokenValidator:
    """Validates Google OAuth token"""

    def validate(self) -> bool:
        """Validate Google token"""
        logger.info("Validating Google OAuth token...")

        token_data_str = os.getenv('GOOGLE_TOKEN_DATA')
        if not token_data_str:
            logger.error("❌ GOOGLE_TOKEN_DATA not found in environment")
            return False

        # Validate JSON format
        try:
            token_data = json.loads(token_data_str)
        except json.JSONDecodeError as e:
            logger.error(f"❌ GOOGLE_TOKEN_DATA is not valid JSON: {e}")
            return False

        logger.info("✅ Token format is valid JSON")

        # Check required fields
        required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes']
        missing_fields = [field for field in required_fields if field not in token_data]

        if missing_fields:
            logger.error(f"❌ Token missing required fields: {', '.join(missing_fields)}")
            return False

        logger.info("✅ Token contains all required fields")
        return True


class AWSValidator:
    """Validates AWS credentials and access"""

    def __init__(self, region: str):
        self.region = region

    def validate(self) -> Optional[str]:
        """
        Validate AWS credentials and return account ID
        Returns account ID on success, None on failure
        """
        logger.info("Validating AWS credentials...")

        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError

            sts = boto3.client('sts', region_name=self.region)
            identity = sts.get_caller_identity()
            account_id = identity['Account']

            logger.info(f"✅ AWS credentials valid")
            logger.info(f"  Account: {account_id}")
            logger.info(f"  Region: {self.region}")

            return account_id

        except NoCredentialsError:
            logger.error("❌ AWS credentials not configured")
            logger.info("💡 Please configure AWS CLI using: aws configure")
            return None
        except ClientError as e:
            logger.error(f"❌ AWS credentials invalid: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error validating AWS credentials: {e}")
            return None


class LambdaPackageValidator:
    """Validates Lambda package locally"""

    def __init__(self, package_path: Path):
        self.package_path = package_path

    def validate(self) -> bool:
        """Test Lambda package locally"""
        logger.info("Testing Lambda package locally...")

        if not self.package_path.exists():
            logger.error(f"❌ Package not found: {self.package_path}")
            return False

        # Basic package structure validation
        try:
            with zipfile.ZipFile(self.package_path, 'r') as zipf:
                file_list = zipf.namelist()
                if len(file_list) == 0:
                    logger.error("❌ Package is empty")
                    return False

                logger.info(f"✅ Package contains {len(file_list)} files")
                return True

        except Exception as e:
            logger.error(f"❌ Package validation failed: {e}")
            return False
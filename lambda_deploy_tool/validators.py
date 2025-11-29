# deploy/validators.py
"""
Validators for environment and token validation
Single Responsibility: Each validator checks one thing
"""
import asyncio
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
    """Validates required environment variables (SRP)"""

    REQUIRED_VARS = [
        'GOOGLE_OAUTH_CLIENT_ID',
        'GOOGLE_OAUTH_CLIENT_SECRET',
    ]

    def validate(self) -> bool:
        """Validate all required environment variables"""
        logger.info("Validating environment variables...")

        # Check OAuth credentials
        missing_vars = []
        for var in self.REQUIRED_VARS:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            logger.error(f"❌ Missing environment variables: {', '.join(missing_vars)}")
            logger.info("💡 Please check your .env file")
            return False

        logger.info("✅ OAuth credentials found")

        # Check worksheet configuration
        worksheet_vars = [var for var in os.environ.keys() if var.startswith('PNPG_WORKSHEET_')]
        if not worksheet_vars:
            logger.error("❌ No PNPG_WORKSHEET_* environment variables found")
            logger.info("💡 Example: PNPG_WORKSHEET_KEDOYA=your_sheet_id_here")
            return False

        logger.info(f"✅ Found {len(worksheet_vars)} worksheet(s)")

        # Check mapping configuration
        mapping_vars = [var for var in os.environ.keys() if var.startswith('PNPG_MAPPING_')]
        if not mapping_vars:
            logger.error("❌ No PNPG_MAPPING_* environment variables found")
            logger.info("💡 Example: PNPG_MAPPING_KEDOYA=Pick n Go Jakarta Barat")
            return False

        logger.info(f"✅ Found {len(mapping_vars)} mapping(s)")

        return True


class TokenValidator:
    """Validates Google OAuth token (SRP)"""

    def validate(self) -> bool:
        """Validate Google token (matches validate_token.py logic)"""
        logger.info("Validating Google OAuth token...")

        token_data_str = os.getenv('GOOGLE_TOKEN_DATA')
        if not token_data_str:
            logger.error("❌ GOOGLE_TOKEN_DATA not found in environment")
            logger.info("💡 Please run local_runner.py first to authenticate:")
            logger.info("   python -m pnpgwatch.local_runner")
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

        # Test token with Gmail API (like validate_token.py does)
        if not self._test_token_with_api():
            logger.error("❌ Token validation failed with Gmail API")
            logger.info("💡 The token may be expired or invalid. Please re-authenticate:")
            logger.info("   python -m pnpgwatch.local_runner")
            return False

        logger.info("✅ Token validated successfully with Gmail API")
        return True

    def _test_token_with_api(self) -> bool:
        """Test token by making a Gmail API call"""
        try:
            return asyncio.run(self._async_test_token())
        except Exception as e:
            logger.error(f"Error testing token: {e}")
            return False

    async def _async_test_token(self) -> bool:
        """Async token test with Gmail API (matches validate_token.py)"""
        try:
            from google_services import GmailService, get_token_storage

            # Use the same token storage factory as local_runner
            token_storage = get_token_storage()
            gmail_service = GmailService(token_storage=token_storage)

            logger.debug("🔍 Testing token with Gmail API...")
            await gmail_service.ensure_authenticated()

            # Try a simple API call - use safe_api_call which handles async properly
            logger.debug("Testing API call...")
            profile = await gmail_service.safe_api_call(
                gmail_service.service.users().getProfile,
                userId='me'
            )

            email = profile.get('emailAddress')
            logger.debug(f"Connected as: {email}")
            return True

        except Exception as e:
            logger.debug(f"Token test failed: {e}")
            return False


class AWSValidator:
    """Validates AWS credentials and access (SRP)"""

    def __init__(self, region: str):
        self.region = region

    def validate(self) -> Optional[str]:
        """
        Validate AWS credentials and return account ID
        Returns account ID on success, None on failure
        Matches shell script logic: "aws sts get-caller-identity"
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
    """Validates Lambda package locally (SRP)"""

    def __init__(self, package_path: Path):
        self.package_path = package_path

    def validate(self) -> bool:
        """Test Lambda package locally"""
        logger.info("Testing Lambda package locally...")

        if not self.package_path.exists():
            logger.error(f"❌ Package not found: {self.package_path}")
            return False

        return self._test_lambda_handler()

    def _test_lambda_handler(self) -> bool:
        """Test Lambda handler with local execution"""
        try:
            with TemporaryDirectory() as temp_dir:
                # Extract package
                with zipfile.ZipFile(self.package_path, 'r') as zipf:
                    zipf.extractall(temp_dir)

                # Add to Python path
                sys.path.insert(0, temp_dir)

                try:
                    from pnpgwatch.lambda_function import lambda_handler

                    # Create test event and mock context
                    test_event = {
                        "test": "local_invocation",
                        "source": "local_test"
                    }

                    class MockContext:
                        def __init__(self):
                            self.function_name = "pnpg-watch-local-test"
                            self.memory_limit_in_mb = 512
                            self.remaining_time_in_millis = lambda: 300000
                            self.function_version = "$LATEST"
                            self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:pnpg-watch-local-test"
                            self.aws_request_id = "test-request-id"

                    # Invoke handler
                    logger.info("Invoking Lambda handler locally...")
                    result = lambda_handler(test_event, MockContext())

                    if result and result.get('statusCode') == 200:
                        logger.info("✅ Local Lambda test passed")
                        return True
                    else:
                        logger.error(f"❌ Local Lambda test failed: {result}")
                        return False

                finally:
                    # Cleanup
                    if temp_dir in sys.path:
                        sys.path.remove(temp_dir)

        except Exception as e:
            logger.error(f"❌ Local Lambda test failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
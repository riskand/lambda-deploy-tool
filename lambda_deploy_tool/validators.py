# lambda_deploy_tool/validators.py (GENERIC - No PNPGWatch specific code)
"""
Generic validators for AWS Lambda deployment
Single Responsibility: Each validator checks one thing
"""
import json
import logging
import os
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


class AWSValidator:
    """Validates AWS credentials and access (SRP)"""

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
    """Validates Lambda package locally (Generic - SRP)"""

    def __init__(self, package_path: Path, handler_module: str, handler_function: str):
        self.package_path = package_path
        self.handler_module = handler_module
        self.handler_function = handler_function

    def validate(self) -> bool:
        """Test Lambda package locally"""
        logger.info(f"Testing Lambda package locally...")

        if not self.package_path.exists():
            logger.error(f"❌ Package not found: {self.package_path}")
            return False

        return self._test_lambda_handler()

    def _test_lambda_handler(self) -> bool:
        """Test Lambda handler with local execution (Generic)"""
        try:
            with TemporaryDirectory() as temp_dir:
                # Extract package
                with zipfile.ZipFile(self.package_path, 'r') as zipf:
                    zipf.extractall(temp_dir)

                # Add to Python path
                sys.path.insert(0, temp_dir)

                try:
                    # Dynamically import the handler module
                    import importlib
                    module = importlib.import_module(self.handler_module)

                    # Get the handler function
                    handler = getattr(module, self.handler_function)

                    # Create test event and mock context
                    test_event = {
                        "test": "local_invocation",
                        "source": "local_test"
                    }

                    class MockContext:
                        def __init__(self):
                            self.function_name = "lambda-local-test"
                            self.memory_limit_in_mb = 512
                            self.remaining_time_in_millis = lambda: 300000
                            self.function_version = "$LATEST"
                            self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:lambda-local-test"
                            self.aws_request_id = "test-request-id"

                    # Invoke handler
                    logger.info(f"Invoking Lambda handler {self.handler_module}.{self.handler_function} locally...")
                    result = handler(test_event, MockContext())

                    if result:
                        logger.info(f"✅ Local Lambda test passed. Handler returned: {result}")
                        return True
                    else:
                        logger.error(f"❌ Local Lambda test failed: Handler returned None")
                        return False

                except ImportError as e:
                    logger.error(f"❌ Failed to import handler module '{self.handler_module}': {e}")
                    return False
                except AttributeError as e:
                    logger.error(f"❌ Handler function '{self.handler_function}' not found: {e}")
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


class EnvironmentVariableValidator:
    """Generic environment variable validator (SRP)"""

    def __init__(self, required_vars: list, optional_vars: list = None):
        self.required_vars = required_vars
        self.optional_vars = optional_vars or []

    def validate(self) -> bool:
        """Validate environment variables"""
        logger.info("Validating environment variables...")

        missing_vars = []
        for var in self.required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            logger.error(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
            return False

        logger.info(f"✅ Found {len(self.required_vars)} required environment variables")

        # Check optional variables (warn if missing)
        missing_optional = []
        for var in self.optional_vars:
            if not os.getenv(var):
                missing_optional.append(var)

        if missing_optional:
            logger.warning(f"⚠️  Missing optional environment variables: {', '.join(missing_optional)}")

        return True
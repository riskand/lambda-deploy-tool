# deploy/aws/lambda_manager.py
"""
Lambda Function Manager with explicit imports and enhanced error handling
"""
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Explicit import to avoid circular dependencies
from . import AWSServiceManager

logger = logging.getLogger(__name__)


class LambdaManager(AWSServiceManager):
    """Manages Lambda function deployment with enhanced error handling"""

    @property
    def service_name(self) -> str:
        return 'lambda'

    def deploy_function(
            self,
            function_name: str,
            role_arn: str,
            handler: str,
            runtime: str,
            timeout: int,
            memory_size: int,
            env_vars: dict,
            package_path: Path
    ) -> str:
        """
        Deploy Lambda function with comprehensive error handling
        Returns function ARN
        """
        logger.info(f"Deploying Lambda function: {function_name}")

        try:
            # Validate package exists and is readable
            if not package_path.exists():
                raise FileNotFoundError(f"Package not found: {package_path}")

            # Read package with error handling
            try:
                with open(package_path, 'rb') as f:
                    zip_content = f.read()
            except IOError as e:
                raise IOError(f"Failed to read package file: {e}")

            # Validate package size
            package_size_mb = len(zip_content) / (1024 * 1024)
            if package_size_mb > 250:  # AWS Lambda deployment package limit
                raise ValueError(f"Package size {package_size_mb:.2f}MB exceeds AWS limit of 250MB")

            function_exists = self.resource_exists('get_function', FunctionName=function_name)

            if function_exists:
                return self._update_function(
                    function_name, env_vars, timeout, memory_size, zip_content
                )
            else:
                return self._create_function(
                    function_name, role_arn, handler, runtime,
                    timeout, memory_size, env_vars, zip_content
                )

        except Exception as e:
            logger.error(f"❌ Lambda deployment failed for {function_name}: {e}")
            raise

    def _create_function(
            self,
            function_name: str,
            role_arn: str,
            handler: str,
            runtime: str,
            timeout: int,
            memory_size: int,
            env_vars: dict,
            zip_content: bytes
    ) -> str:
        """Create new Lambda function with validation"""
        logger.info("Creating new Lambda function...")

        # Validate parameters
        self._validate_lambda_parameters(timeout, memory_size)

        response = self.safe_call_with_retry(
            'create_function',
            FunctionName=function_name,
            Runtime=runtime,
            Role=role_arn,
            Handler=handler,
            Code={'ZipFile': zip_content},
            Timeout=timeout,
            MemorySize=memory_size,
            Environment={'Variables': env_vars},
            Tags={
                'Application': 'pnpgwatch',
                'ManagedBy': 'deploy-script',
                'BudgetEnforced': 'true'
            },
            max_attempts=3
        )

        if self.dry_run:
            return f"arn:aws:lambda:{self.region}:000000000000:function:{function_name}"

        # Wait for function to be active
        self._wait_for_function_active(function_name)

        logger.info(f"✅ Lambda function created: {function_name}")
        return response['FunctionArn']

    def _update_function(
            self,
            function_name: str,
            env_vars: dict,
            timeout: int,
            memory_size: int,
            zip_content: bytes
    ) -> str:
        """Update existing Lambda function with rollback capability"""
        logger.info("Updating existing Lambda function...")

        # Validate parameters
        self._validate_lambda_parameters(timeout, memory_size)

        try:
            # Update code
            code_response = self.safe_call_with_retry(
                'update_function_code',
                FunctionName=function_name,
                ZipFile=zip_content,
                max_attempts=3
            )

            if not self.dry_run:
                # Wait for code update to complete
                self._wait_for_function_updated(function_name)

            # Update configuration
            config_response = self.safe_call_with_retry(
                'update_function_configuration',
                FunctionName=function_name,
                Environment={'Variables': env_vars},
                Timeout=timeout,
                MemorySize=memory_size,
                max_attempts=3
            )

            if self.dry_run:
                return f"arn:aws:lambda:{self.region}:000000000000:function:{function_name}"

            logger.info(f"✅ Lambda function updated: {function_name}")
            return code_response['FunctionArn']

        except Exception as e:
            logger.error(f"❌ Failed to update Lambda function {function_name}: {e}")
            # TODO: Implement rollback to previous version
            raise

    def _validate_lambda_parameters(self, timeout: int, memory_size: int) -> None:
        """Validate Lambda configuration parameters"""
        if timeout < 1 or timeout > 900:
            raise ValueError(f"Timeout {timeout} must be between 1 and 900 seconds")

        if memory_size < 128 or memory_size > 10240:
            raise ValueError(f"Memory size {memory_size} must be between 128 and 10240 MB")

        # Check memory size increments
        if memory_size % 64 != 0:
            raise ValueError(f"Memory size {memory_size} must be a multiple of 64")

    def _wait_for_function_active(self, function_name: str, max_attempts: int = 20) -> None:
        """Wait for Lambda function to become active"""
        if self.dry_run:
            return

        logger.info(f"Waiting for function {function_name} to become active...")

        for attempt in range(max_attempts):
            try:
                response = self.safe_call('get_function', FunctionName=function_name)
                state = response['Configuration']['State']

                if state == 'Active':
                    logger.info("✅ Function is active")
                    return
                elif state == 'Failed':
                    raise ValueError(
                        f"Function creation failed: {response['Configuration'].get('StateReason', 'Unknown error')}")
                elif state == 'Pending':
                    if attempt < max_attempts - 1:
                        time.sleep(2)
                    else:
                        raise TimeoutError(f"Function did not become active within {max_attempts * 2} seconds")

            except Exception as e:
                if attempt == max_attempts - 1:
                    raise TimeoutError(f"Failed to check function state: {e}")
                time.sleep(2)

    def _wait_for_function_updated(self, function_name: str, max_attempts: int = 20) -> None:
        """Wait for Lambda function update to complete"""
        if self.dry_run:
            return

        logger.info(f"Waiting for function {function_name} update to complete...")

        for attempt in range(max_attempts):
            try:
                response = self.safe_call('get_function', FunctionName=function_name)
                last_update_status = response['Configuration']['LastUpdateStatus']

                if last_update_status == 'Successful':
                    logger.info("✅ Function update completed")
                    return
                elif last_update_status == 'Failed':
                    raise ValueError(
                        f"Function update failed: {response['Configuration'].get('LastUpdateStatusReason', 'Unknown error')}")
                elif last_update_status in ['InProgress', '']:
                    if attempt < max_attempts - 1:
                        time.sleep(2)
                    else:
                        raise TimeoutError(f"Function update did not complete within {max_attempts * 2} seconds")

            except Exception as e:
                if attempt == max_attempts - 1:
                    raise TimeoutError(f"Failed to check function update status: {e}")
                time.sleep(2)

    def test_function(self, function_name: str, payload: dict = None) -> bool:
        """Test Lambda function invocation with comprehensive error handling"""
        logger.info(f"Testing Lambda function: {function_name}")

        if payload is None:
            payload = {"test": "deployment_test", "source": "deployer"}

        try:
            import json

            response = self.safe_call_with_retry(
                'invoke',
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload).encode(),
                max_attempts=2
            )

            if self.dry_run:
                logger.info("[DRY-RUN] Would test Lambda function")
                return True

            status_code = response.get('StatusCode', 0)
            if status_code == 200:
                # Check function error
                if 'FunctionError' in response:
                    logger.error(f"❌ Lambda test failed with function error: {response.get('FunctionError')}")
                    return False

                logger.info("✅ Lambda test successful")
                return True
            else:
                logger.error(f"❌ Lambda test failed with status: {status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Lambda test failed: {e}")
            return False
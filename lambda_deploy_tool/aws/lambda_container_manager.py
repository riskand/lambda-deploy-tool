# lambda_deploy_tool/aws/lambda_container_manager.py
"""
Container Lambda Manager
"""
import logging
from typing import Dict, List

from .lambda_manager import LambdaManager

logger = logging.getLogger(__name__)


class ContainerLambdaManager(LambdaManager):
    """Manages container-based Lambda functions"""

    def deploy_container_function(
            self,
            function_name: str,
            role_arn: str,
            image_uri: str,
            timeout: int,
            memory_size: int,
            env_vars: Dict[str, str],
            architectures: List[str] = None
    ) -> str:
        """
        Deploy container-based Lambda function

        Returns:
            Function ARN
        """
        logger.info(f"🚢 Deploying container Lambda: {function_name}")
        logger.info(f"  Image: {image_uri}")
        logger.info(f"  Memory: {memory_size}MB")
        logger.info(f"  Timeout: {timeout}s")

        # Set default architectures
        if architectures is None:
            architectures = ['x86_64']

        function_exists = self.resource_exists('get_function', FunctionName=function_name)

        if function_exists:
            return self._update_container_function(
                function_name, image_uri, env_vars, timeout, memory_size
            )
        else:
            return self._create_container_function(
                function_name, role_arn, image_uri, env_vars,
                timeout, memory_size, architectures
            )

    def _create_container_function(
            self,
            function_name: str,
            role_arn: str,
            image_uri: str,
            env_vars: Dict[str, str],
            timeout: int,
            memory_size: int,
            architectures: List[str]
    ) -> str:
        """Create new container-based Lambda function"""
        logger.info("Creating new container Lambda function...")

        # Validate parameters
        self._validate_lambda_parameters(timeout, memory_size)

        response = self.safe_call_with_retry(
            'create_function',
            FunctionName=function_name,
            Role=role_arn,
            Code={'ImageUri': image_uri},
            PackageType='Image',
            Architectures=architectures,
            Timeout=timeout,
            MemorySize=memory_size,
            Environment={'Variables': env_vars},
            Tags={
                'DeploymentType': 'container',
                'ManagedBy': 'lambda-deploy-tool',
                'ImageUri': image_uri
            },
            max_attempts=3
        )

        if self.dry_run:
            return f"arn:aws:lambda:{self.region}:000000000000:function:{function_name}"

        # Wait for function to be active
        self._wait_for_function_active(function_name)

        logger.info(f"✅ Container Lambda created: {function_name}")
        return response['FunctionArn']

    def _update_container_function(
            self,
            function_name: str,
            image_uri: str,
            env_vars: Dict[str, str],
            timeout: int,
            memory_size: int
    ) -> str:
        """Update existing container-based Lambda function"""
        logger.info("Updating container Lambda function...")

        # Validate parameters
        self._validate_lambda_parameters(timeout, memory_size)

        try:
            # Update container image
            code_response = self.safe_call_with_retry(
                'update_function_code',
                FunctionName=function_name,
                ImageUri=image_uri,
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

            logger.info(f"✅ Container Lambda updated: {function_name}")
            return code_response['FunctionArn']

        except Exception as e:
            logger.error(f"❌ Failed to update container Lambda: {e}")
            raise
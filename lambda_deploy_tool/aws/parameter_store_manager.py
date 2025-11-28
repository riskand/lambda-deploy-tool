# lambda_deploy_tool/aws/parameter_store_manager.py
"""
Parameter Store Manager
"""
import logging

from .base import AWSServiceManager

logger = logging.getLogger(__name__)


class ParameterStoreManager(AWSServiceManager):
    """Manages AWS Systems Manager Parameter Store"""

    @property
    def service_name(self) -> str:
        return 'ssm'

    def store_google_token(self, parameter_name: str, token_data: str) -> None:
        """Store Google OAuth token in Parameter Store"""
        logger.info(f"Storing Google token in Parameter Store: {parameter_name}")

        self.safe_call(
            'put_parameter',
            Name=parameter_name,
            Value=token_data,
            Type='SecureString',
            Overwrite=True,
            Description='Google OAuth tokens for Lambda function'
        )

        logger.info("✅ Google token stored securely")

    def get_parameter(self, parameter_name: str) -> str:
        """Retrieve parameter value"""
        response = self.safe_call(
            'get_parameter',
            Name=parameter_name,
            WithDecryption=True
        )

        if self.dry_run:
            return "dry-run-value"

        return response['Parameter']['Value']

    def parameter_exists(self, parameter_name: str) -> bool:
        """Check if parameter exists"""
        return self.resource_exists('get_parameter', Name=parameter_name)
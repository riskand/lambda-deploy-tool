# lambda_deploy_tool/aws/ecr_manager.py
"""
ECR Repository Manager
"""
import logging
import base64
import json

from . import AWSServiceManager

logger = logging.getLogger(__name__)


class ECRManager(AWSServiceManager):
    """Manages ECR repositories for container Lambda"""

    @property
    def service_name(self) -> str:
        return 'ecr'

    def ensure_repository(self, repository_name: str) -> str:
        """
        Ensure ECR repository exists

        Returns:
            Repository URI (e.g., account.dkr.ecr.region.amazonaws.com/repo)
        """
        logger.info(f"📦 Setting up ECR repository: {repository_name}")

        if self.dry_run:
            # Return a mock repository URI for dry-run
            mock_uri = f"123456789012.dkr.ecr.{self.region}.amazonaws.com/{repository_name}"
            logger.info(f"[DRY-RUN] Would ensure ECR repository: {repository_name}")
            logger.info(f"[DRY-RUN] Mock repository URI: {mock_uri}")
            return mock_uri

        try:
            # Check if repository exists
            response = self.safe_call(
                'describe_repositories',
                repositoryNames=[repository_name]
            )
            repo_uri = response['repositories'][0]['repositoryUri']
            logger.info(f"✅ ECR repository exists: {repo_uri}")
            return repo_uri

        except self.client.exceptions.RepositoryNotFoundException:
            # Create repository if it doesn't exist
            logger.info(f"Creating ECR repository: {repository_name}")
            response = self.safe_call(
                'create_repository',
                repositoryName=repository_name,
                imageTagMutability='MUTABLE',
                imageScanningConfiguration={
                    'scanOnPush': True
                }
            )
            repo_uri = response['repository']['repositoryUri']
            logger.info(f"✅ Created ECR repository: {repo_uri}")
            return repo_uri

    def get_authorization_token(self) -> dict:
        """
        Get ECR authorization token for Docker login

        Returns:
            dict with username, password, and proxy endpoint
        """
        logger.debug("Getting ECR authorization token...")

        if self.dry_run:
            # Return mock auth for dry-run
            mock_auth = {
                'username': 'AWS',
                'password': 'dry-run-token',
                'registry': f'123456789012.dkr.ecr.{self.region}.amazonaws.com'
            }
            logger.info(f"[DRY-RUN] Would get ECR authorization token")
            return mock_auth

        response = self.safe_call('get_authorization_token')
        auth_data = response['authorizationData'][0]

        # Decode authorization token
        auth_token = base64.b64decode(auth_data['authorizationToken']).decode()
        username, password = auth_token.split(':')

        auth_info = {
            'username': username,
            'password': password,
            'registry': auth_data['proxyEndpoint'].replace('https://', '')
        }

        logger.debug(f"✅ Got ECR authorization for {auth_info['registry']}")
        return auth_info
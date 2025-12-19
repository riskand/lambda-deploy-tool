# lambda_deploy_tool/container_deployer.py
"""
Container Deployer
"""
import logging
from typing import List, Tuple, Callable

from .deployer import Deployer
from .config_container import ContainerDeployConfig
from .builder_container import ContainerBuilder
from .aws.ecr_manager import ECRManager
from .aws.lambda_container_manager import ContainerLambdaManager

logger = logging.getLogger(__name__)


class ContainerDeployer(Deployer):
    """Deployer for container-based Lambda functions"""

    def __init__(self, config: ContainerDeployConfig):
        # Initialize parent with config
        super().__init__(config)

        # Ensure config is ContainerDeployConfig
        if not isinstance(config, ContainerDeployConfig):
            raise TypeError("config must be ContainerDeployConfig")

        self.config = config

        # Initialize container-specific managers
        self.ecr_mgr = ECRManager(config.region, config.dry_run)
        self.container_builder = ContainerBuilder(config)

        # Initialize container Lambda manager
        self.container_lambda_mgr = ContainerLambdaManager(
            config.region,
            config.dry_run
        )

        # Set container-specific deployment steps
        self.deployment_steps = self.get_default_deployment_steps()

    def get_default_deployment_steps(self) -> List[Tuple[str, Callable]]:
        """Get container-specific deployment steps"""
        steps = []

        # ECR setup (container-specific)
        steps.append(("ECR Repository Setup", self._setup_ecr_repository))

        # Budget setup (inherited, but skip for local test)
        if self.config.enable_budget and not self.config.local_test_enabled:
            steps.append(("Budget Setup", self._setup_budget_if_needed))

        # Container build (container-specific)
        steps.append(("Container Build", self._build_container))

        # Local test (container-specific, if enabled)
        if self.config.local_test_enabled and not getattr(self.config, 'skip_container_test', False):
            steps.append(("Local Container Test", self._test_container_locally))

        # IAM setup (inherited, but skip for local test)
        if not self.config.local_test_enabled:
            steps.append(("IAM Setup", self._setup_iam_roles))
            steps.append(("Container Deployment", self._deploy_container))
            steps.append(("Schedule Setup", self._setup_schedule))

        return steps

    def _setup_ecr_repository(self) -> None:
        """Setup ECR repository"""
        logger.info("📦 Setting up ECR repository...")

        # Ensure ECR repository exists and get URI
        repo_uri = self.ecr_mgr.ensure_repository(self.config.ecr_repository_name)

        # Update config with repository URI
        self.config.ecr_repository_uri = repo_uri

        logger.info(f"✅ ECR repository ready: {repo_uri}")

    def _build_container(self) -> None:
        """Build and push Docker container"""
        logger.info("🔨 Building and pushing container...")

        # Get ECR authorization
        ecr_auth = self.ecr_mgr.get_authorization_token()

        # Build and push image
        success = self.container_builder.build_image(ecr_auth)

        if not success:
            raise RuntimeError("Container build failed")

        logger.info(f"✅ Container built and pushed: {self.config.full_image_uri}")

    def _test_container_locally(self) -> None:
        """Test container locally"""
        logger.info("🧪 Testing container locally...")

        success = self.container_builder.test_locally()

        if not success:
            raise RuntimeError("Local container test failed")

        logger.info("✅ Local container test passed")

    def _deploy_container(self) -> None:
        """Deploy container to Lambda"""
        logger.info("🚢 Deploying container to Lambda...")

        # Get environment variables
        env_vars = self.config.get_env_vars()

        # Deploy container Lambda
        function_arn = self.container_lambda_mgr.deploy_container_function(
            function_name=self.config.function_name,
            role_arn=self.config.role_arn,
            image_uri=self.config.full_image_uri,
            timeout=self.config.timeout,
            memory_size=self.config.memory_size,
            env_vars=env_vars,
            architectures=self.config.architectures
        )

        # Update config with Lambda ARN
        self.config.lambda_arn = function_arn

        logger.info(f"✅ Container deployed to Lambda: {function_arn}")

    def _setup_iam_roles(self) -> None:
        """Setup IAM roles for container Lambda"""
        logger.info("👤 Setting up IAM roles for container...")

        # Use parent's IAM setup (works for both zip and container)
        super()._setup_iam_roles()

        # Add ECR permissions for Lambda role
        if not self.config.local_test_enabled and not self.config.dry_run:
            self._add_ecr_permissions()

    def _add_ecr_permissions(self) -> None:
        """Add ECR permissions to Lambda role for container pull"""
        logger.info("➕ Adding ECR permissions to Lambda role...")

        policy_name = 'ecr-pull-policy'
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:BatchCheckLayerAvailability"
                ],
                "Resource": f"arn:aws:ecr:{self.config.region}:{self.config.account_id}:repository/{self.config.ecr_repository_name}"
            }, {
                "Effect": "Allow",
                "Action": "ecr:GetAuthorizationToken",
                "Resource": "*"
            }]
        }

        self.iam_mgr.attach_inline_policy(
            self.config.role_name,
            policy_name,
            policy_document
        )

        logger.info("✅ ECR permissions added to Lambda role")

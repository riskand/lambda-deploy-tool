# lambda_deploy_tool/config_container.py
"""
Container-specific configuration extending generic DeployConfig
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List

from .config import DeployConfig


@dataclass
class ContainerDeployConfig(DeployConfig):
    """Configuration for container-based Lambda deployment"""

    # Container registry configuration
    ecr_repository_name: str = 'lambda-container'
    ecr_repository_uri: Optional[str] = None
    dockerfile_path: Path = Path('Dockerfile')
    docker_context: Path = Path('.')

    # Container configuration
    image_tag: str = 'latest'
    container_port: int = 8080
    platform: str = 'linux/amd64'

    # Container-specific Lambda settings
    package_type: str = 'Image'
    architectures: List[str] = field(default_factory=lambda: ['x86_64'])

    # Container environment
    container_env_vars: Dict[str, str] = field(default_factory=dict)

    # Build options
    build_args: Dict[str, str] = field(default_factory=dict)
    cache_from: List[str] = field(default_factory=list)

    # Runtime options
    entrypoint: List[str] = field(default_factory=list)
    command: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize container-specific properties"""
        super().__post_init__()

        # Set package_type to Image for container deployment
        self.package_type = 'Image'

        # Initialize ECR repository URI if not provided
        if not self.ecr_repository_uri and self.account_id:
            self.ecr_repository_uri = f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/{self.ecr_repository_name}"

        # No zip package for container deployments
        self.package_path = None

        # Set default entrypoint if not specified
        if not self.entrypoint and not self.command:
            # Default to Lambda Runtime Interface Emulator (RIE) if no custom entrypoint
            pass

    @property
    def full_image_uri(self) -> str:
        """Get full ECR image URI"""
        if not self.ecr_repository_uri:
            raise ValueError("ECR repository URI not set")
        return f"{self.ecr_repository_uri}:{self.image_tag}"

    def get_build_args(self) -> Dict[str, str]:
        """Get build args with defaults"""
        build_args = self.build_args.copy()

        # Add common build args
        if self.account_id:
            build_args.setdefault('AWS_ACCOUNT_ID', self.account_id)
        build_args.setdefault('AWS_REGION', self.region)
        build_args.setdefault('LAMBDA_FUNCTION_NAME', self.function_name)

        return build_args
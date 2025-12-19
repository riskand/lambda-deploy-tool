# lambda_deploy_tool/__init__.py
"""
AWS Lambda Deployment System - Now with Container Support
KISS, DRY, SOLID principles applied
"""

__version__ = "2.0.0"

# Re-export existing components
from .deployer import Deployer
from .config import DeployConfig
from .args import DeploymentArgumentParser, parse_arguments
from .builder import LambdaBuilder
from .validators import (
    AWSValidator,
    LambdaPackageValidator,
    EnvironmentVariableValidator
)

# New container components
from .config_container import ContainerDeployConfig
from .container_deployer import ContainerDeployer
from .args_container import ContainerDeploymentArgumentParser
from .builder_container import ContainerBuilder

__all__ = [
    # Existing exports
    'Deployer',
    'DeployConfig',
    'DeploymentArgumentParser',
    'parse_arguments',
    'LambdaBuilder',
    'AWSValidator',
    'LambdaPackageValidator',
    'EnvironmentVariableValidator',

    # New container exports
    'ContainerDeployConfig',
    'ContainerDeployer',
    'ContainerDeploymentArgumentParser',
    'ContainerBuilder',
]
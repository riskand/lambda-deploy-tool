# lambda_deploy_tool/args_container.py
"""
Container-specific argument parsing
"""
from pathlib import Path

from .args import DeploymentArgumentParser


class ContainerDeploymentArgumentParser(DeploymentArgumentParser):
    """Argument parser for container Lambda deployment"""

    def __init__(self, script_name: str = None, description: str = None):
        super().__init__(script_name, description)
        self._add_container_arguments()

    def _add_container_arguments(self):
        """Add container-specific arguments"""
        container_group = self.add_argument_group('Container Options')

        container_group.add_argument(
            '--container',
            action='store_true',
            help='Deploy as container Lambda (instead of zip package)'
        )

        container_group.add_argument(
            '--ecr-repository',
            type=str,
            default=None,
            help='ECR repository name (default: {function-name}-container)'
        )

        container_group.add_argument(
            '--dockerfile',
            type=str,
            default='Dockerfile',
            help='Path to Dockerfile (default: Dockerfile)'
        )

        container_group.add_argument(
            '--docker-context',
            type=str,
            default='.',
            help='Docker build context (default: current directory)'
        )

        container_group.add_argument(
            '--image-tag',
            type=str,
            default='latest',
            help='Docker image tag (default: latest)'
        )

        container_group.add_argument(
            '--platform',
            type=str,
            default='linux/amd64',
            help='Docker build platform (default: linux/amd64)'
        )

        container_group.add_argument(
            '--no-push',
            action='store_true',
            help='Build Docker image without pushing to ECR'
        )

        container_group.add_argument(
            '--skip-container-test',
            action='store_true',
            help='Skip local container test'
        )
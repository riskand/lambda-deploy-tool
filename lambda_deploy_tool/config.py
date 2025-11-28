# lambda_deploy_tool/config.py
"""
Deployment configuration management for lambda_deploy_tool
"""
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List


@dataclass
class DeployConfig:
    """Deployment configuration - all settings come from environment or constructor"""

    # Required settings (no defaults - must be provided)
    function_name: str
    source_dir: Path

    # Optional settings with defaults
    output_dir: Path = Path('dist')
    package_name: str = 'lambda-package.zip'
    region: str = 'ap-southeast-1'
    role_name: Optional[str] = None
    schedule_name: Optional[str] = None

    # Lambda configuration
    runtime: str = 'python3.12'
    timeout: int = 300
    memory_size: int = 512
    handler: str = 'lambda_function.lambda_handler'

    # Schedule configuration
    schedule_expression: Optional[str] = None

    # Budget configuration
    enable_budget: bool = False
    budget_name: Optional[str] = None
    budget_limit: float = 1.00
    budget_email: Optional[str] = None

    # Execution options
    dry_run: bool = False
    local_test_enabled: bool = False

    # Environment variables to include in Lambda
    env_vars: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize derived properties"""
        self.package_path = self.output_dir / self.package_name

        # Set default role name if not provided
        if self.role_name is None:
            self.role_name = f"{self.function_name}-role"

        # Set default schedule name if not provided
        if self.schedule_name is None and self.schedule_expression:
            self.schedule_name = f"{self.function_name}-schedule"

    @property
    def lambda_arn(self) -> str:
        """Get Lambda function ARN"""
        if not hasattr(self, 'account_id') or not self.account_id:
            raise ValueError("Account ID not set")
        return f"arn:aws:lambda:{self.region}:{self.account_id}:function:{self.function_name}"

    @property
    def role_arn(self) -> str:
        """Get IAM role ARN"""
        if not hasattr(self, 'account_id') or not self.account_id:
            raise ValueError("Account ID not set")
        return f"arn:aws:iam::{self.account_id}:role/{self.role_name}"

    def discover_source_files(self, exclude_patterns: List[str] = None) -> List[Path]:
        """
        Discover source files automatically, excluding specified patterns
        """
        if exclude_patterns is None:
            exclude_patterns = ['__pycache__', '*.pyc', '.git', 'tests', 'test_*']

        source_files = []

        # First pass: exclude directories
        for pattern in exclude_patterns:
            if not pattern.startswith('*'):
                # Directory pattern
                for dir_path in self.source_dir.rglob(pattern):
                    if dir_path.is_dir():
                        shutil.rmtree(dir_path, ignore_errors=True)

        # Second pass: collect files and exclude file patterns
        for file_path in self.source_dir.rglob('*'):
            if file_path.is_file():
                should_exclude = False
                for pattern in exclude_patterns:
                    if pattern.startswith('*'):
                        # File pattern match
                        if file_path.match(pattern):
                            should_exclude = True
                            break

                if not should_exclude and not any(part.startswith('.') for part in file_path.parts):
                    relative_path = file_path.relative_to(self.source_dir)
                    source_files.append(relative_path)

        return source_files
# lambda_deploy_tool/config.py (GENERIC)
"""
Generic deployment configuration management
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Set

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


@dataclass
class DeployConfig:
    """Generic deployment configuration"""

    # Build configuration
    source_dir: Path = Path('.')
    output_dir: Path = Path('dist')
    package_name: str = 'lambda-package.zip'

    # AWS configuration
    region: str = 'us-east-1'
    function_name: str = 'lambda-function'
    role_name: str = 'lambda-execution-role'
    schedule_name: str = 'lambda-schedule'

    # Lambda configuration
    runtime: str = 'python3.12'
    timeout: int = 300
    memory_size: int = 512
    handler: str = 'lambda_function.lambda_handler'

    # Schedule configuration
    schedule_expression: str = 'rate(5 minutes)'

    # Budget configuration
    enable_budget: bool = True
    budget_name: str = 'Lambda Function Budget'
    budget_limit: float = 1.00
    budget_email: Optional[str] = None
    budget_topic_name: str = None  # ADDED: Configurable SNS topic name

    # Local testing configuration
    local_test_enabled: bool = False
    local_test_event: dict = field(default_factory=lambda: {
        "test": "local_invocation",
        "source": "local_test"
    })

    # Execution options
    dry_run: bool = False

    # Environment variable configuration
    required_env_vars: Set[str] = field(default_factory=set)
    allowed_env_prefixes: Set[str] = field(default_factory=set)
    env_file_path: Optional[Path] = None  # ADDED: Custom env file path

    # Derived properties
    account_id: Optional[str] = field(default=None, init=False)
    package_path: Path = field(init=False)

    def __post_init__(self):
        """Initialize derived properties"""
        self.package_path = self.output_dir / self.package_name

        # Set default budget topic name if not provided
        if not self.budget_topic_name and self.function_name:
            self.budget_topic_name = f"{self.function_name}-budget-alerts"

    @property
    def lambda_arn(self) -> str:
        """Get Lambda function ARN"""
        if not self.account_id:
            raise ValueError("Account ID not set")
        return f"arn:aws:lambda:{self.region}:{self.account_id}:function:{self.function_name}"

    @property
    def role_arn(self) -> str:
        """Get IAM role ARN"""
        if not self.account_id:
            raise ValueError("Account ID not set")
        return f"arn:aws:iam::{self.account_id}:role/{self.role_name}"

    def get_env_vars(self) -> Dict[str, str]:
        """
        Get filtered environment variables for Lambda
        Extend this in subclasses for specific filtering
        """
        env_vars = {}

        # Determine which .env file to load
        env_file = self._get_env_file_path()

        # Load .env file if available
        if load_dotenv and env_file.exists():
            load_dotenv(env_file, override=True)
            self._log_env_loaded(env_file)
        elif not self.local_test_enabled and not self.dry_run:
            # Only require .env for real deployments
            raise FileNotFoundError(f".env file not found at {env_file}")

        # Add required environment variables
        for var_name in self.required_env_vars:
            value = os.getenv(var_name)
            if value:
                env_vars[var_name] = value
            elif not self.local_test_enabled:
                # Only enforce required vars for real deployments
                raise ValueError(f"Required environment variable not found: {var_name}")

        # Add variables with allowed prefixes
        for env_var, value in os.environ.items():
            for prefix in self.allowed_env_prefixes:
                if env_var.startswith(prefix) and value.strip():
                    env_vars[env_var] = value.strip()
                    break

        # Log summary
        self._log_env_summary(env_vars)

        return env_vars

    def _get_env_file_path(self) -> Path:
        """Get the path to the .env file"""
        if self.env_file_path:
            return self.env_file_path
        return Path('.env')

    def _log_env_loaded(self, env_file: Path) -> None:
        """Log that environment file was loaded"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"✅ Loaded environment from {env_file}")

    def _log_env_summary(self, env_vars: Dict[str, str]) -> None:
        """Log environment variable summary"""
        import logging
        logger = logging.getLogger(__name__)

        total_size = sum(len(k) + len(v) for k, v in env_vars.items())
        logger.info(f"📋 Environment variables: {len(env_vars)} variables, ~{total_size} bytes")

        # Warn if approaching Lambda limit
        if total_size > 3500:
            logger.warning(f"⚠️  Environment variables size ({total_size} bytes) approaching Lambda 4KB limit")
        else:
            logger.info(f"✅ Environment variables within safe limits ({total_size}/4096 bytes)")

    def validate_env_vars_size(self, env_vars: Dict[str, str]) -> bool:
        """Validate that environment variables don't exceed Lambda limits"""
        total_size = 0
        for key, value in env_vars.items():
            total_size += len(key) + len(value)

        # Add overhead for JSON structure and AWS encoding
        estimated_size = total_size + (len(env_vars) * 10) + 100

        return estimated_size <= 4000  # Leave some buffer under 4KB
# lambda_deploy_tool/config.py
"""
Generic deployment configuration management
All settings loaded from environment variables - no hardcoded values
"""
import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Set, List

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


@dataclass
class DeployConfig:
    """Generic deployment configuration - fully configurable via environment"""

    # Build configuration
    source_dir: Path = None
    source_files: List[str] = None
    output_dir: Path = None
    package_name: str = None
    requirements_file: Path = None

    # AWS configuration
    region: str = None
    function_name: str = None
    role_name: str = None
    schedule_name: str = None

    # Lambda configuration
    runtime: str = None
    timeout: int = None
    memory_size: int = None
    handler: str = None

    # Schedule configuration
    schedule_expression: str = None

    # Budget configuration
    enable_budget: bool = True
    budget_name: str = None
    budget_limit: float = None
    budget_email: Optional[str] = None

    # Parameter Store configuration
    parameter_store_path: str = None
    token_env_var: str = None

    # Local testing configuration
    local_test_enabled: bool = False
    local_test_event: dict = field(default_factory=dict)

    # Execution options
    dry_run: bool = False

    # Derived properties
    account_id: Optional[str] = field(default=None, init=False)
    package_path: Path = field(init=False)

    # Environment variable configuration
    required_env_vars: Set[str] = field(default_factory=set)
    allowed_env_prefixes: Set[str] = field(default_factory=set)
    excluded_packages: Set[str] = field(default_factory=set)

    def __post_init__(self):
        """Initialize configuration from environment variables"""
        if load_dotenv:
            env_file = Path('.env')
            if env_file.exists():
                load_dotenv(env_file, override=True)

        self._load_from_environment()
        self.package_path = self.output_dir / self.package_name

        if self.enable_budget and not self.budget_email:
            raise ValueError("Budget enforcement requires LAMBDA_BUDGET_EMAIL")

    def _load_from_environment(self):
        """Load all configuration from environment variables"""
        self.source_dir = Path(os.getenv('LAMBDA_SOURCE_DIR', '.'))
        
        source_files_str = os.getenv('LAMBDA_SOURCE_FILES', '')
        self.source_files = [f.strip() for f in source_files_str.split(',') if f.strip()]
        
        self.output_dir = Path(os.getenv('LAMBDA_OUTPUT_DIR', 'dist'))
        self.package_name = os.getenv('LAMBDA_PACKAGE_NAME', 'lambda-function.zip')
        self.requirements_file = Path(os.getenv('LAMBDA_REQUIREMENTS_FILE', 'requirements.txt'))

        self.region = os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
        self.function_name = self._require_env('LAMBDA_FUNCTION_NAME')
        self.role_name = os.getenv('LAMBDA_ROLE_NAME', f'{self.function_name}-role')
        self.schedule_name = os.getenv('LAMBDA_SCHEDULE_NAME', f'{self.function_name}-schedule')

        self.runtime = os.getenv('LAMBDA_RUNTIME', 'python3.12')
        self.timeout = int(os.getenv('LAMBDA_TIMEOUT', '300'))
        self.memory_size = int(os.getenv('LAMBDA_MEMORY_SIZE', '512'))
        self.handler = self._require_env('LAMBDA_HANDLER')

        self.schedule_expression = os.getenv('LAMBDA_SCHEDULE_EXPRESSION', '')

        self.enable_budget = os.getenv('LAMBDA_ENABLE_BUDGET', 'true').lower() == 'true'
        self.budget_name = os.getenv('LAMBDA_BUDGET_NAME', 'Lambda Function Budget')
        self.budget_limit = float(os.getenv('LAMBDA_BUDGET_LIMIT', '1.00'))
        self.budget_email = os.getenv('LAMBDA_BUDGET_EMAIL')

        self.parameter_store_path = os.getenv('LAMBDA_PARAMETER_STORE_PATH', '')
        self.token_env_var = os.getenv('LAMBDA_TOKEN_ENV_VAR', '')

        required_vars_str = os.getenv('LAMBDA_REQUIRED_ENV_VARS', '')
        self.required_env_vars = {v.strip() for v in required_vars_str.split(',') if v.strip()}

        allowed_prefixes_str = os.getenv('LAMBDA_ALLOWED_ENV_PREFIXES', '')
        self.allowed_env_prefixes = {p.strip() for p in allowed_prefixes_str.split(',') if p.strip()}

        excluded_str = os.getenv('LAMBDA_EXCLUDED_PACKAGES', '')
        self.excluded_packages = {p.strip() for p in excluded_str.split(',') if p.strip()}

    def _require_env(self, var_name: str) -> str:
        """Require an environment variable to be set"""
        value = os.getenv(var_name)
        if not value:
            raise ValueError(f"Required environment variable not set: {var_name}")
        return value

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
        """Get filtered environment variables for Lambda"""
        env_vars = {}

        if load_dotenv:
            env_file = Path('.env')
            if env_file.exists():
                load_dotenv(env_file, override=True)

        for var_name in self.required_env_vars:
            value = os.getenv(var_name)
            if value:
                env_vars[var_name] = value
            else:
                raise ValueError(f"Required environment variable not found: {var_name}")

        for env_var, value in os.environ.items():
            for prefix in self.allowed_env_prefixes:
                if env_var.startswith(prefix) and value.strip():
                    env_vars[env_var] = value.strip()
                    break

        self._log_env_summary(env_vars)
        return env_vars

    def _log_env_summary(self, env_vars: Dict[str, str]) -> None:
        """Log environment variable summary"""
        import logging
        logger = logging.getLogger(__name__)

        total_size = sum(len(k) + len(v) for k, v in env_vars.items())
        logger.info(f"📋 Environment variables: {len(env_vars)} variables, ~{total_size} bytes")

        if total_size > 3500:
            logger.warning(f"⚠️  Environment variables size ({total_size} bytes) approaching Lambda 4KB limit")
        else:
            logger.info(f"✅ Environment variables within safe limits ({total_size}/4096 bytes)")

    def validate_env_vars_size(self, env_vars: Dict[str, str]) -> bool:
        """Validate that environment variables don't exceed Lambda limits"""
        total_size = sum(len(k) + len(v) for k, v in env_vars.items())
        estimated_size = total_size + (len(env_vars) * 10) + 100
        return estimated_size <= 4000

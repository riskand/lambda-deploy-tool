# deploy/deployer.py
"""
Main deployment orchestrator with fixed imports and error handling
"""
import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Import from the same package to avoid circular dependencies
from .builder import LambdaBuilder
from .config import DeployConfig
from .validators import AWSValidator, LambdaPackageValidator

logger = logging.getLogger(__name__)


class Deployer:
    """
    Main deployment orchestrator with comprehensive error handling
    """

    def __init__(self, config: DeployConfig):
        self.config = config
        self.account_id: Optional[str] = None
        self.package_path: Optional[Path] = None

        # Initialize with error handling
        self._initialize_aws_managers()

    def _initialize_aws_managers(self) -> None:
        """Initialize AWS service managers with error handling"""
        try:
            # Validate AWS and get account ID
            aws_validator = AWSValidator(self.config.region)
            self.account_id = aws_validator.validate()
            if not self.account_id:
                raise ValueError("AWS validation failed - cannot get account ID")

            self.config.account_id = self.account_id

            # Lazy import to avoid circular imports
            from .aws.lambda_manager import LambdaManager
            from .aws.iam_manager import IAMManager
            from .aws.parameter_store_manager import ParameterStoreManager
            from .aws.scheduler_manager import SchedulerManager
            from .aws.budget_manager import BudgetManager

            # Initialize AWS service managers
            self.lambda_mgr = LambdaManager(self.config.region, self.config.dry_run)
            self.iam_mgr = IAMManager(self.config.region, self.config.dry_run)
            self.param_store_mgr = ParameterStoreManager(self.config.region, self.config.dry_run)
            self.scheduler_mgr = SchedulerManager(self.config.region, self.config.dry_run)
            self.budget_mgr = BudgetManager(self.config.region, self.account_id, self.config.dry_run)

            # Initialize builder
            self.builder = LambdaBuilder(self.config)

        except Exception as e:
            logger.error(f"❌ Failed to initialize AWS managers: {e}")
            raise

    def deploy(self) -> None:
        """
        Execute complete deployment with comprehensive error handling
        """
        logger.info("🚀 Starting deployment...")

        try:
            deployment_steps = [
                ("Budget Setup", self._setup_budget_if_needed),
                ("Build Package", self._build_package),
                ("Local Test", self._run_local_test_if_enabled),
                ("IAM Setup", self._setup_iam_roles),
                ("Token Storage", self._store_google_token),
                ("Lambda Deployment", self._deploy_lambda),
                ("Schedule Setup", self._setup_schedule)
            ]

            for step_name, step_func in deployment_steps:
                if self._should_skip_step(step_name):
                    continue

                logger.info(f"\n📋 {step_name}")
                logger.info("-" * 60)

                if not self._execute_step_safely(step_name, step_func):
                    raise ValueError(f"Deployment failed at step: {step_name}")

            logger.info("✅ Deployment completed successfully!")

        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}")
            self._cleanup_on_failure()
            raise

    def _should_skip_step(self, step_name: str) -> bool:
        """Determine if a step should be skipped based on configuration"""
        if step_name == "Budget Setup" and (not self.config.enable_budget or self.config.local_test_enabled):
            return True
        if step_name == "Local Test" and not self.config.local_test_enabled:
            return True
        if step_name in ["IAM Setup", "Token Storage", "Lambda Deployment",
                         "Schedule Setup"] and self.config.local_test_enabled:
            return True
        return False

    def _execute_step_safely(self, step_name: str, step_func) -> bool:
        """Execute a deployment step with comprehensive error handling"""
        try:
            step_func()
            return True
        except Exception as e:
            logger.error(f"❌ {step_name} failed: {e}")
            raise

    def _setup_budget_if_needed(self) -> None:
        """Setup budget enforcement with error handling"""
        if not self.config.enable_budget or self.config.local_test_enabled:
            return

        logger.info("💰 Setting up Budget Enforcement")

        try:
            # Create budget action role first
            budget_role_arn = self.iam_mgr.ensure_budget_action_role(
                'pnpgwatch-budget-action-role',
                self.config.account_id
            )
            self.iam_mgr.attach_budget_action_policy('pnpgwatch-budget-action-role')
            logger.debug(f"Budget action role ARN: {budget_role_arn}")

            # Setup budget with enforcement
            self.budget_mgr.setup_budget_enforcement(
                budget_name=self.config.budget_name,
                budget_limit=self.config.budget_limit,
                email=self.config.budget_email,
                budget_action_role_arn=budget_role_arn
            )

        except Exception as e:
            logger.error(f"❌ Budget setup failed: {e}")
            raise

    def _build_package(self) -> None:
        """Build Lambda package with error handling"""
        logger.info("📦 Building Lambda Package")
        self.package_path = self.builder.build()

    def _run_local_test_if_enabled(self) -> None:
        """Run local Lambda test if enabled"""
        if not self.config.local_test_enabled:
            return

        logger.info("🧪 Testing Lambda Package Locally")
        validator = LambdaPackageValidator(self.package_path)
        if not validator.validate():
            raise ValueError("Local Lambda test failed")

    def _setup_iam_roles(self) -> None:
        """Setup IAM roles with error handling"""
        logger.info("👤 Setting up IAM Roles")

        try:
            # Lambda execution role
            role_arn = self.iam_mgr.ensure_lambda_role(
                self.config.role_name,
                self.config.account_id
            )
            logger.debug(f"Lambda role ARN: {role_arn}")

            # Attach Parameter Store policy
            self.iam_mgr.attach_parameter_store_policy(
                self.config.role_name,
                self.config.account_id
            )

            # Scheduler role
            scheduler_role_arn = self.iam_mgr.ensure_scheduler_role(
                'pnpgwatch-schedule-role',
                self.config.account_id,
                self.config.function_name
            )
            logger.debug(f"Scheduler role ARN: {scheduler_role_arn}")

        except Exception as e:
            logger.error(f"❌ IAM setup failed: {e}")
            raise

    def _store_google_token(self) -> None:
        """Store Google OAuth token with error handling"""
        logger.info("🔐 Storing Google Token")

        try:
            token_data = os.getenv('GOOGLE_TOKEN_DATA')
            if not token_data:
                raise ValueError(
                    "GOOGLE_TOKEN_DATA not found in environment.\n"
                    "Make sure it's in your .env file."
                )

            self.param_store_mgr.store_google_token(
                self.config.parameter_store_path,
                token_data
            )

        except Exception as e:
            logger.error(f"❌ Token storage failed: {e}")
            raise

    def _deploy_lambda(self) -> None:
        """Deploy Lambda function with environment variable validation"""
        logger.info("⚡ Deploying Lambda Function")

        try:
            env_vars = self.config.get_env_vars()

            # Validate environment variable size before deployment
            if not self.config.validate_env_vars_size(env_vars):
                env_size = sum(len(k) + len(v) for k, v in env_vars.items())
                raise ValueError(
                    f"Environment variables exceed Lambda 4KB limit (estimated: {env_size} bytes). "
                    f"Reduce the number of worksheets or mappings."
                )

            function_arn = self.lambda_mgr.deploy_function(
                function_name=self.config.function_name,
                role_arn=self.config.role_arn,
                handler=self.config.handler,
                runtime=self.config.runtime,
                timeout=self.config.timeout,
                memory_size=self.config.memory_size,
                env_vars=env_vars,
                package_path=self.package_path
            )

            logger.info(f"✅ Lambda function deployed: {function_arn}")

        except Exception as e:
            logger.error(f"❌ Lambda deployment failed: {e}")
            raise

    def _setup_schedule(self) -> None:
        """Setup EventBridge schedule with error handling"""
        logger.info("⏰ Setting up EventBridge Schedule")

        try:
            scheduler_role_arn = f"arn:aws:iam::{self.config.account_id}:role/pnpgwatch-schedule-role"

            self.scheduler_mgr.ensure_schedule(
                schedule_name=self.config.schedule_name,
                schedule_expression=self.config.schedule_expression,
                target_arn=self.config.lambda_arn,
                role_arn=scheduler_role_arn
            )

        except Exception as e:
            logger.error(f"❌ Schedule setup failed: {e}")
            raise

    def _cleanup_on_failure(self) -> None:
        """Cleanup resources on deployment failure"""
        if self.config.dry_run or self.config.local_test_enabled:
            return

        logger.info("🧹 Cleaning up resources after failure...")

        try:
            # Add cleanup logic here for failed deployments
            # This could include deleting partially created resources
            pass
        except Exception as cleanup_error:
            logger.error(f"⚠️ Cleanup failed: {cleanup_error}")

    def build(self) -> Path:
        """Build Lambda package (public method for build-only mode)"""
        logger.info("\n📦 Building Lambda Package")
        logger.info("-" * 60)

        package_path = self.builder.build()

        # Verify package
        if not self.builder.verify_package(package_path):
            raise ValueError("Package verification failed")

        return package_path
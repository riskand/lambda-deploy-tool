# lambda_deploy_tool/deployer.py
"""
Main deployment orchestrator for lambda-deploy-tool
"""
import logging
from pathlib import Path
from typing import List

from .aws.lambda_manager import LambdaManager
from .aws.iam_manager import IAMManager
from .aws.parameter_store_manager import ParameterStoreManager
from .aws.scheduler_manager import SchedulerManager
from .aws.budget_manager import BudgetManager
from .builder import LambdaBuilder
from .validators import AWSValidator, LambdaPackageValidator

logger = logging.getLogger(__name__)


class Deployer:
    """
    Main deployment orchestrator
    """

    def __init__(self, config):
        self.config = config
        self.account_id = None

        # Initialize AWS managers
        self._initialize_aws_managers()

    def _initialize_aws_managers(self) -> None:
        """Initialize AWS service managers"""
        # Validate AWS and get account ID
        aws_validator = AWSValidator(self.config.region)
        self.account_id = aws_validator.validate()
        if not self.account_id:
            raise ValueError("AWS validation failed - cannot get account ID")

        self.config.account_id = self.account_id

        # Initialize AWS service managers
        self.lambda_mgr = LambdaManager(self.config.region, self.config.dry_run)
        self.iam_mgr = IAMManager(self.config.region, self.config.dry_run)
        self.param_store_mgr = ParameterStoreManager(self.config.region, self.config.dry_run)
        self.scheduler_mgr = SchedulerManager(self.config.region, self.config.dry_run)

        if self.config.enable_budget:
            self.budget_mgr = BudgetManager(self.config.region, self.account_id, self.config.dry_run)

        # Initialize builder
        self.builder = LambdaBuilder(self.config)

    def deploy(self, exclude_patterns: List[str] = None, requirements_file: Path = None) -> None:
        """
        Execute complete deployment with automatic source discovery
        """
        logger.info("🚀 Starting deployment...")

        deployment_steps = [
            ("Budget Setup", self._setup_budget_if_needed),
            ("Build Package", lambda: self._build_package(exclude_patterns, requirements_file)),
            ("Local Test", self._run_local_test_if_enabled),
            ("IAM Setup", self._setup_iam_roles),
            ("Lambda Deployment", self._deploy_lambda),
            ("Schedule Setup", self._setup_schedule)
        ]

        for step_name, step_func in deployment_steps:
            logger.info(f"\n📋 {step_name}")
            if not self._execute_step_safely(step_name, step_func):
                raise ValueError(f"Deployment failed at step: {step_name}")

        logger.info("✅ Deployment completed successfully!")

    def _execute_step_safely(self, step_name: str, step_func) -> bool:
        """Execute a deployment step with error handling"""
        try:
            step_func()
            return True
        except Exception as e:
            logger.error(f"❌ {step_name} failed: {e}")
            raise

    def _setup_budget_if_needed(self) -> None:
        """Setup budget enforcement"""
        if not self.config.enable_budget:
            return

        logger.info("💰 Setting up Budget Enforcement")
        budget_role_arn = self.iam_mgr.ensure_budget_action_role(
            f"{self.config.function_name}-budget-action-role",
            self.config.account_id
        )
        self.iam_mgr.attach_budget_action_policy(f"{self.config.function_name}-budget-action-role")

        self.budget_mgr.setup_budget_enforcement(
            budget_name=self.config.budget_name or f"{self.config.function_name}-budget",
            budget_limit=self.config.budget_limit,
            email=self.config.budget_email,
            budget_action_role_arn=budget_role_arn
        )

    def _build_package(self, exclude_patterns: List[str] = None, requirements_file: Path = None) -> None:
        """Build Lambda package with automatic source discovery"""
        logger.info("📦 Building Lambda Package")
        self.package_path = self.builder.build(exclude_patterns, requirements_file)

    def _run_local_test_if_enabled(self) -> None:
        """Run local Lambda test if enabled"""
        if not self.config.local_test_enabled:
            return

        logger.info("🧪 Testing Lambda Package Locally")
        validator = LambdaPackageValidator(self.package_path)
        if not validator.validate():
            raise ValueError("Local Lambda test failed")

    def _setup_iam_roles(self) -> None:
        """Setup IAM roles"""
        logger.info("👤 Setting up IAM Roles")

        # Lambda execution role
        role_arn = self.iam_mgr.ensure_lambda_role(
            self.config.role_name,
            self.config.account_id
        )

        # Attach Parameter Store policy if needed
        if any('ssm' in key.lower() or 'parameter' in key.lower() for key in self.config.env_vars.keys()):
            self.iam_mgr.attach_parameter_store_policy(
                self.config.role_name,
                self.config.account_id
            )

        # Scheduler role
        if self.config.schedule_expression:
            scheduler_role_arn = self.iam_mgr.ensure_scheduler_role(
                f"{self.config.function_name}-schedule-role",
                self.config.account_id,
                self.config.function_name
            )

    def _deploy_lambda(self) -> None:
        """Deploy Lambda function"""
        logger.info("⚡ Deploying Lambda Function")

        function_arn = self.lambda_mgr.deploy_function(
            function_name=self.config.function_name,
            role_arn=self.config.role_arn,
            handler=self.config.handler,
            runtime=self.config.runtime,
            timeout=self.config.timeout,
            memory_size=self.config.memory_size,
            env_vars=self.config.env_vars,
            package_path=self.package_path
        )

        logger.info(f"✅ Lambda function deployed: {function_arn}")

    def _setup_schedule(self) -> None:
        """Setup EventBridge schedule"""
        if not self.config.schedule_expression:
            return

        logger.info("⏰ Setting up EventBridge Schedule")
        scheduler_role_arn = f"arn:aws:iam::{self.config.account_id}:role/{self.config.function_name}-schedule-role"

        self.scheduler_mgr.ensure_schedule(
            schedule_name=self.config.schedule_name,
            schedule_expression=self.config.schedule_expression,
            target_arn=self.config.lambda_arn,
            role_arn=scheduler_role_arn
        )
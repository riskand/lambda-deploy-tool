# lambda_deploy_tool/aws/iam_manager.py
"""
IAM Role and Policy Manager
"""
import json
import logging
import time

from .base import AWSServiceManager

logger = logging.getLogger(__name__)


class IAMManager(AWSServiceManager):
    """Manages IAM roles and policies for Lambda"""

    @property
    def service_name(self) -> str:
        return 'iam'

    def ensure_lambda_role(self, role_name: str, account_id: str) -> str:
        """
        Ensure Lambda execution role exists
        Returns role ARN
        """
        logger.info(f"Setting up IAM role: {role_name}")

        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

        if self.resource_exists('get_role', RoleName=role_name):
            logger.info(f"✅ IAM role already exists: {role_name}")
            return role_arn

        # Create role
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }

        self.safe_call(
            'create_role',
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Execution role for Lambda function'
        )
        logger.info(f"✅ Created IAM role: {role_name}")

        # Attach basic execution policy
        self.safe_call(
            'attach_role_policy',
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
        )
        logger.info("✅ Attached AWSLambdaBasicExecutionRole")

        # Wait for role to be available
        if not self.dry_run:
            time.sleep(10)

        return role_arn

    def attach_parameter_store_policy(self, role_name: str, account_id: str) -> None:
        """Attach Parameter Store access policy to role"""
        logger.info("Setting up Parameter Store permissions...")

        policy_name = f'{role_name}-ssm-policy'
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameter",
                    "ssm:PutParameter"
                ],
                "Resource": f"arn:aws:ssm:{self.region}:{account_id}:parameter/*"
            }]
        }

        self.safe_call(
            'put_role_policy',
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        logger.info("✅ Parameter Store policy attached")

    def ensure_budget_action_role(self, role_name: str, account_id: str) -> str:
        """
        Ensure budget action role exists
        Returns role ARN
        """
        logger.info(f"Setting up budget action role: {role_name}")

        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

        if self.resource_exists('get_role', RoleName=role_name):
            logger.info(f"✅ Budget action role already exists: {role_name}")
            return role_arn

        # Create role
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "budgets.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }

        self.safe_call(
            'create_role',
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Role for budget enforcement actions'
        )
        logger.info(f"✅ Created budget action role: {role_name}")

        return role_arn

    def attach_budget_action_policy(self, role_name: str) -> None:
        """Attach budget action policy to role"""
        logger.info("Setting up budget action policy...")

        policy_name = f'{role_name}-budget-actions'
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "lambda:UpdateFunctionConfiguration",
                    "scheduler:UpdateSchedule",
                    "sns:Publish"
                ],
                "Resource": "*"
            }]
        }

        self.safe_call(
            'put_role_policy',
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        logger.info("✅ Budget action policy attached")

        # Wait for policy to propagate
        if not self.dry_run:
            time.sleep(10)

    def ensure_scheduler_role(self, role_name: str, account_id: str, function_name: str) -> str:
        """
        Ensure EventBridge Scheduler role exists
        Returns role ARN
        """
        logger.info(f"Setting up scheduler role: {role_name}")

        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

        if self.resource_exists('get_role', RoleName=role_name):
            logger.info(f"✅ Scheduler role already exists: {role_name}")
            return role_arn

        # Create role
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "scheduler.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": account_id
                    }
                }
            }]
        }

        self.safe_call(
            'create_role',
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Role for EventBridge Scheduler to invoke Lambda'
        )
        logger.info(f"✅ Created scheduler role: {role_name}")

        # Attach policy
        policy_name = f'{role_name}-schedule-policy'
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "lambda:InvokeFunction",
                "Resource": f"arn:aws:lambda:{self.region}:{account_id}:function:{function_name}"
            }]
        }

        self.safe_call(
            'put_role_policy',
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        logger.info("✅ Scheduler policy attached")

        # Wait for role to be available
        if not self.dry_run:
            time.sleep(5)

        return role_arn
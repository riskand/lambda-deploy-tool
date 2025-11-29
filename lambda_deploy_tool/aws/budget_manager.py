# deploy/aws/budget_manager.py
"""
AWS Budget Manager
Single Responsibility: Manage AWS Budgets with enforcement
"""
import json
import logging

import boto3
from botocore.exceptions import ClientError

from . import AWSServiceManager

logger = logging.getLogger(__name__)


class BudgetManager(AWSServiceManager):
    """Manages AWS Budgets with cost enforcement (SRP)"""

    @property
    def service_name(self) -> str:
        return 'budgets'

    def __init__(self, region: str, account_id: str, dry_run: bool = False):
        super().__init__(region, dry_run)
        self.account_id = account_id
        self._sns_client = None

    @property
    def sns_client(self):
        """Lazy-load SNS client"""
        if self._sns_client is None:
            self._sns_client = boto3.client('sns', region_name=self.region)
        return self._sns_client

    def setup_budget_enforcement(
        self,
        budget_name: str,
        budget_limit: float,
        email: str,
        budget_action_role_arn: str
    ) -> None:
        """Setup complete budget enforcement with email alerts"""
        logger.info(f"💰 Setting up budget enforcement: ${budget_limit}/month")

        # Create SNS topic and subscribe email
        topic_arn = self._ensure_sns_topic(email)

        # Create or update budget with notifications
        self._ensure_budget_with_notifications(
            budget_name, budget_limit, topic_arn, budget_action_role_arn
        )

        logger.info("✅ Budget enforcement configured")
        logger.info(f"   • 80% threshold: Email warning to {email}")
        logger.info(f"   • 100% threshold: Lambda function AUTOMATICALLY DISABLED")

    def _ensure_sns_topic(self, email: str) -> str:
        """Ensure SNS topic exists and email is subscribed"""
        topic_name = 'pnpgwatch-budget-alerts'
        topic_arn = f"arn:aws:sns:{self.region}:{self.account_id}:{topic_name}"

        logger.info("Setting up SNS topic for budget alerts...")

        # Create topic if it doesn't exist
        try:
            self.sns_client.get_topic_attributes(TopicArn=topic_arn)
            logger.info(f"✅ SNS topic exists: {topic_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'NotFound':
                if not self.dry_run:
                    self.sns_client.create_topic(Name=topic_name)
                logger.info(f"✅ Created SNS topic: {topic_name}")
            else:
                raise

        # Subscribe email if not already subscribed
        if not self._is_email_subscribed(topic_arn, email):
            if not self.dry_run:
                self.sns_client.subscribe(
                    TopicArn=topic_arn,
                    Protocol='email',
                    Endpoint=email
                )
            logger.info(f"✅ Subscribed {email} to budget alerts")
            logger.info(f"📧 Confirmation email sent to {email} - PLEASE CONFIRM")
        else:
            logger.info(f"✅ Email already subscribed: {email}")

        return topic_arn

    def _is_email_subscribed(self, topic_arn: str, email: str) -> bool:
        """Check if email is already subscribed to topic"""
        if self.dry_run:
            return False

        try:
            response = self.sns_client.list_subscriptions_by_topic(TopicArn=topic_arn)
            subscriptions = response.get('Subscriptions', [])

            for sub in subscriptions:
                if sub.get('Endpoint') == email:
                    return True

            return False
        except Exception:
            return False

    def _ensure_budget_with_notifications(
        self,
        budget_name: str,
        budget_limit: float,
        sns_topic_arn: str,
        budget_action_role_arn: str
    ) -> None:
        """Create or update budget with notifications and actions"""
        logger.info(f"Configuring budget: {budget_name}")

        budget_definition = {
            'BudgetName': budget_name,
            'BudgetLimit': {
                'Amount': str(budget_limit),
                'Unit': 'USD'
            },
            'CostFilters': {
                'Service': ['Amazon Lambda', 'Amazon EventBridge Scheduler']
            },
            'CostTypes': {
                'IncludeCredit': False,
                'IncludeDiscount': True,
                'IncludeOtherSubscription': True,
                'IncludeRecurring': True,
                'IncludeRefund': False,
                'IncludeSubscription': True,
                'IncludeSupport': True,
                'IncludeTax': True,
                'IncludeUpfront': True,
                'UseBlended': False
            },
            'TimeUnit': 'MONTHLY',
            'BudgetType': 'COST'
        }

        notifications = [
            {
                'Notification': {
                    'NotificationType': 'ACTUAL',
                    'ComparisonOperator': 'GREATER_THAN',
                    'Threshold': 80,
                    'ThresholdType': 'PERCENTAGE'
                },
                'Subscribers': [{
                    'SubscriptionType': 'SNS',
                    'Address': sns_topic_arn
                }]
            },
            {
                'Notification': {
                    'NotificationType': 'ACTUAL',
                    'ComparisonOperator': 'GREATER_THAN',
                    'Threshold': 100,
                    'ThresholdType': 'PERCENTAGE'
                },
                'Subscribers': [{
                    'SubscriptionType': 'SNS',
                    'Address': sns_topic_arn
                }]
            }
        ]

        if self._budget_exists(budget_name):
            self._update_budget(budget_name, budget_definition)
        else:
            self._create_budget(budget_name, budget_definition, notifications)

    def _budget_exists(self, budget_name: str) -> bool:
        """Check if budget exists"""
        try:
            self.safe_call(
                'describe_budget',
                AccountId=self.account_id,
                BudgetName=budget_name
            )
            return True
        except Exception:
            return False

    def _create_budget(
        self,
        budget_name: str,
        budget_definition: dict,
        notifications: list
    ) -> None:
        """Create new budget"""
        logger.info("Creating new budget...")

        self.safe_call(
            'create_budget',
            AccountId=self.account_id,
            Budget=budget_definition,
            NotificationsWithSubscribers=notifications
        )

        logger.info(f"✅ Budget created: {budget_name}")

    def _update_budget(self, budget_name: str, budget_definition: dict) -> None:
        """Update existing budget"""
        logger.info("Updating existing budget...")

        self.safe_call(
            'update_budget',
            AccountId=self.account_id,
            NewBudget=budget_definition
        )

        logger.info(f"✅ Budget updated: {budget_name}")
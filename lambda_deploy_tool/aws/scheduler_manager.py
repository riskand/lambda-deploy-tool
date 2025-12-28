# lambda_deploy_tool/aws/scheduler_manager.py
"""
EventBridge Scheduler Manager
"""
import logging

from . import AWSServiceManager

logger = logging.getLogger(__name__)


class SchedulerManager(AWSServiceManager):
    """Manages EventBridge Scheduler (SRP)"""

    @property
    def service_name(self) -> str:
        return 'scheduler'

    def ensure_schedule(
            self,
            schedule_name: str,
            schedule_expression: str,
            target_arn: str,
            role_arn: str,
            schedule_timezone: str = None,
            description: str = None
    ) -> None:
        """
        Ensure EventBridge schedule exists

        Args:
            schedule_name: Name of the schedule
            schedule_expression: Cron or rate expression
            target_arn: Lambda function ARN to invoke
            role_arn: IAM role ARN for scheduler
            schedule_timezone: Timezone for cron expressions (e.g., 'Asia/Jakarta', 'America/New_York')
                              Only valid for cron expressions, ignored for rate expressions
            description: Optional description for the schedule
        """
        logger.info(f"Setting up EventBridge schedule: {schedule_name}")
        logger.info(f"  Expression: {schedule_expression}")
        if schedule_timezone:
            logger.info(f"  Timezone: {schedule_timezone}")

        schedule_exists = self._schedule_exists(schedule_name)

        target_config = {
            'Arn': target_arn,
            'RoleArn': role_arn
        }

        flexible_time_window = {
            'Mode': 'FLEXIBLE',
            'MaximumWindowInMinutes': 5
        }

        if schedule_exists:
            self._update_schedule(
                schedule_name, schedule_expression, target_config,
                flexible_time_window, schedule_timezone, description
            )
        else:
            self._create_schedule(
                schedule_name, schedule_expression, target_config,
                flexible_time_window, schedule_timezone, description
            )

    def _schedule_exists(self, schedule_name: str) -> bool:
        """Check if schedule exists"""
        try:
            self.safe_call('get_schedule', Name=schedule_name)
            return True
        except Exception:
            return False

    def _create_schedule(
            self,
            schedule_name: str,
            schedule_expression: str,
            target: dict,
            flexible_time_window: dict,
            schedule_timezone: str = None,
            description: str = None
    ) -> None:
        """Create new schedule"""
        logger.info("Creating new schedule...")

        # Build parameters
        params = {
            'Name': schedule_name,
            'ScheduleExpression': schedule_expression,
            'Target': target,
            'FlexibleTimeWindow': flexible_time_window
        }

        # Add description if provided
        if description:
            params['Description'] = description

        # Add timezone if provided and expression is cron
        if schedule_timezone and schedule_expression.startswith('cron('):
            params['ScheduleExpressionTimezone'] = schedule_timezone
            logger.info(f"  Using timezone: {schedule_timezone}")

        self.safe_call('create_schedule', **params)

        logger.info(f"✅ Schedule created: {schedule_name}")

    def _update_schedule(
            self,
            schedule_name: str,
            schedule_expression: str,
            target: dict,
            flexible_time_window: dict,
            schedule_timezone: str = None,
            description: str = None
    ) -> None:
        """Update existing schedule"""
        logger.info("Updating existing schedule...")

        # Build parameters
        params = {
            'Name': schedule_name,
            'ScheduleExpression': schedule_expression,
            'Target': target,
            'FlexibleTimeWindow': flexible_time_window
        }

        # Add description if provided
        if description:
            params['Description'] = description

        # Add timezone if provided and expression is cron
        if schedule_timezone and schedule_expression.startswith('cron('):
            params['ScheduleExpressionTimezone'] = schedule_timezone
            logger.info(f"  Using timezone: {schedule_timezone}")

        self.safe_call('update_schedule', **params)

        logger.info(f"✅ Schedule updated: {schedule_name}")
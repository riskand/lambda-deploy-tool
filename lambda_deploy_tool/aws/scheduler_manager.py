# lambda_deploy_tool/aws/scheduler_manager.py
"""
EventBridge Scheduler Manager
Single Responsibility: Manage EventBridge schedules for Lambda
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
        role_arn: str
    ) -> None:
        """Ensure EventBridge schedule exists"""
        logger.info(f"Setting up EventBridge schedule: {schedule_name}")
        logger.info(f"  Expression: {schedule_expression}")

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
                schedule_name, schedule_expression, target_config, flexible_time_window
            )
        else:
            self._create_schedule(
                schedule_name, schedule_expression, target_config, flexible_time_window
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
        flexible_time_window: dict
    ) -> None:
        """Create new schedule"""
        logger.info("Creating new schedule...")

        self.safe_call(
            'create_schedule',
            Name=schedule_name,
            ScheduleExpression=schedule_expression,
            Target=target,
            FlexibleTimeWindow=flexible_time_window,
            Description='PNPG Watch execution schedule (08:00-21:00 GMT+7, every 15 minutes)'
        )

        logger.info(f"✅ Schedule created: {schedule_name}")

    def _update_schedule(
        self,
        schedule_name: str,
        schedule_expression: str,
        target: dict,
        flexible_time_window: dict
    ) -> None:
        """Update existing schedule"""
        logger.info("Updating existing schedule...")

        self.safe_call(
            'update_schedule',
            Name=schedule_name,
            ScheduleExpression=schedule_expression,
            Target=target,
            FlexibleTimeWindow=flexible_time_window
        )

        logger.info(f"✅ Schedule updated: {schedule_name}")
# deploy/aws/__init__.py
"""
AWS service managers - Simplified to avoid circular imports
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class AWSServiceManager(ABC):
    """
    Base class for AWS service managers (Open/Closed Principle)
    Provides common functionality for all AWS services
    """

    def __init__(self, region: str, dry_run: bool = False):
        self.region = region
        self.dry_run = dry_run
        self._client = None

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return AWS service name (e.g., 'lambda', 'iam')"""
        pass

    @property
    def client(self):
        """Lazy-load boto3 client"""
        if self._client is None:
            self._client = boto3.client(self.service_name, region_name=self.region)
        return self._client

    def safe_call(self, operation: str, **kwargs) -> Any:
        """
        Safely call AWS API with error handling and retries
        """
        return self.safe_call_with_retry(operation, **kwargs)

    def safe_call_with_retry(self, operation: str, max_attempts: int = 3, base_delay: float = 1.0, **kwargs) -> Any:
        """
        Safely call AWS API with exponential backoff retry
        """
        import time
        last_exception = None

        for attempt in range(max_attempts):
            if self.dry_run:
                logger.info(f"[DRY-RUN] Would call {self.service_name}.{operation}")
                logger.debug(f"[DRY-RUN] Parameters: {kwargs}")
                return None

            try:
                method = getattr(self.client, operation)
                response = method(**kwargs)
                logger.debug(f"✅ {self.service_name}.{operation} succeeded (attempt {attempt + 1})")
                return response

            except ClientError as e:
                last_exception = e
                error_code = e.response['Error']['Code']

                # Don't retry on these errors
                if error_code in ['AccessDenied', 'ValidationError', 'InvalidParameter']:
                    logger.error(f"❌ {self.service_name}.{operation} failed: {error_code}")
                    raise

                # Retry on throttling and server errors
                if attempt < max_attempts - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"⚠️ {self.service_name}.{operation} failed with {error_code}, retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(
                        f"❌ {self.service_name}.{operation} failed after {max_attempts} attempts: {error_code}")
                    raise

            except Exception as e:
                last_exception = e
                logger.error(f"❌ {self.service_name}.{operation} failed: {e}")
                if attempt == max_attempts - 1:
                    raise

        raise last_exception

    def resource_exists(self, check_operation: str, **kwargs) -> bool:
        """
        Check if AWS resource exists with proper error handling
        """
        try:
            self.safe_call(check_operation, **kwargs)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] in ['NoSuchEntity', 'ResourceNotFoundException', 'NotFoundException']:
                return False
            raise

    def wait_for_resource(self, waiter_name: str, max_attempts: int = 40, **kwargs) -> bool:
        """
        Wait for AWS resource to be ready with timeout handling
        """
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would wait for {waiter_name}")
            return True

        try:
            waiter = self.client.get_waiter(waiter_name)
            waiter.wait(
                WaiterConfig={'MaxAttempts': max_attempts},
                **kwargs
            )
            return True
        except Exception as e:
            logger.error(f"❌ Waiting for {waiter_name} failed: {e}")
            return False


# Remove the problematic imports - let each file import managers explicitly
__all__ = ['AWSServiceManager']
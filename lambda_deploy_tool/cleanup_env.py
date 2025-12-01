# lambda_deploy_tool/cleanup_env.py
"""
Utility to clean up Lambda environment variables
"""
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def cleanup_lambda_environment(function_name: str, region: str = 'ap-southeast-1'):
    """
    Clean up Lambda function environment variables by setting only required ones
    """
    lambda_client = boto3.client('lambda', region_name=region)

    try:
        # Get current function configuration
        response = lambda_client.get_function_configuration(FunctionName=function_name)
        current_env_vars = response.get('Environment', {}).get('Variables', {})

        logger.info(f"Current environment variables: {len(current_env_vars)}")

        # Create minimal environment
        minimal_env = {
            'PNPG_LOOKBACK_DAYS': '7',
            'PNPG_LOG_DIR': '/tmp/pnpgwatch',
            'GOOGLE_TOKEN_PARAMETER_NAME': '/pnpgwatch/google-tokens'
        }

        # Update function with minimal environment
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Environment={'Variables': minimal_env}
        )

        logger.info("✅ Lambda environment cleaned up")

    except ClientError as e:
        logger.error(f"❌ Failed to clean up Lambda environment: {e}")
        raise


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Clean up Lambda environment variables')
    parser.add_argument('--function-name', required=True, help='Lambda function name')
    parser.add_argument('--region', default='ap-southeast-1', help='AWS region')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    cleanup_lambda_environment(args.function_name, args.region)
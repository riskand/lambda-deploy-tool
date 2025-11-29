#!/usr/bin/env python3
# lambda_deploy_tool/cli.py
"""
Generic CLI interface for lambda-deploy-tool
"""
import argparse
import logging
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(env_path, override=True)
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

from .config import DeployConfig
from .deployer import Deployer


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Generic AWS Lambda deployment tool')
    parser.add_argument('--build-only', action='store_true', help='Build package only')
    parser.add_argument('--local-lambda', action='store_true', help='Build and test locally')
    parser.add_argument('--dry-run', action='store_true', help='Show what would happen')
    parser.add_argument('--skip-validation', action='store_true', help='Skip validation')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    return parser.parse_args()


def main() -> int:
    """Main deployment function"""
    args = parse_arguments()
    
    try:
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        logger.info("🚀 Lambda Deployment Tool")
        
        config = DeployConfig(dry_run=args.dry_run, local_test_enabled=args.local_lambda)
        deployer = Deployer(config)
        
        if args.build_only:
            package_path = deployer.build()
            logger.info(f"✅ Package built: {package_path}")
        else:
            deployer.deploy()
            logger.info("✅ Deployment completed!")
        
        return 0
    
    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

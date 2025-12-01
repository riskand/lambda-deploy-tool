# deploy/args.py
"""
Command line argument parsing for deployment - Class-based for extensibility
"""
import argparse
import os
from pathlib import Path


class DeploymentArgumentParser:
    """Class-based argument parser for deployment with extensibility"""

    def __init__(self, script_name: str = None, description: str = None):
        self.script_name = script_name or os.path.basename(__file__)
        self.description = description or 'Deploy application to AWS Lambda'
        self.parser = None
        self._initialize_parser()

    def _initialize_parser(self):
        """Initialize the argument parser with base arguments"""
        self.parser = argparse.ArgumentParser(
            description=self.description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self._get_epilog_text()
        )

        self._add_build_arguments()
        self._add_aws_arguments()
        self._add_budget_arguments()
        self._add_testing_arguments()
        self._add_other_arguments()

    def _add_build_arguments(self):
        """Add build-related arguments"""
        build_group = self.parser.add_argument_group('Build Options')
        build_group.add_argument(
            '--build-only',
            action='store_true',
            help='Build Lambda package without deploying'
        )
        build_group.add_argument(
            '--source-dir',
            type=Path,
            default=Path('.'),
            help='Source directory containing application code (default: current directory)'
        )
        build_group.add_argument(
            '--output-dir',
            type=Path,
            default=Path('dist'),
            help='Output directory for build artifacts (default: dist/)'
        )

    def _add_aws_arguments(self):
        """Add AWS-related arguments"""
        aws_group = self.parser.add_argument_group('AWS Deployment Options')
        aws_group.add_argument(
            '--region',
            default='ap-southeast-1',
            help='AWS region (default: ap-southeast-1)'
        )
        aws_group.add_argument(
            '--function-name',
            default='lambda-function',
            help='Lambda function name (default: lambda-function)'
        )

    def _add_budget_arguments(self):
        """Add budget-related arguments"""
        budget_group = self.parser.add_argument_group('Budget Enforcement Options')
        budget_group.add_argument(
            '--budget-limit',
            type=float,
            default=1.00,
            help='Monthly budget limit in USD (default: 1.00)'
        )
        budget_group.add_argument(
            '--budget-email',
            help='Email for budget alerts (required for budget enforcement)'
        )
        budget_group.add_argument(
            '--budget-name',
            help='Budget name (default: "Lambda Function Budget")'
        )
        budget_group.add_argument(
            '--no-budget',
            action='store_true',
            help='Skip budget enforcement (NOT RECOMMENDED)'
        )

    def _add_testing_arguments(self):
        """Add testing-related arguments"""
        testing_group = self.parser.add_argument_group('Testing Options')
        testing_group.add_argument(
            '--local-lambda',
            action='store_true',
            help='Build and test Lambda package locally without deploying to AWS'
        )

    def _add_other_arguments(self):
        """Add other miscellaneous arguments"""
        other_group = self.parser.add_argument_group('Other Options')
        other_group.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deployed without making changes'
        )
        other_group.add_argument(
            '--skip-validation',
            action='store_true',
            help='Skip token and environment validation (dangerous)'
        )
        other_group.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Enable verbose logging'
        )

    def add_argument(self, *args, **kwargs):
        """Add custom argument - extensibility point"""
        self.parser.add_argument(*args, **kwargs)

    def add_argument_group(self, title: str, description: str = None):
        """Add a custom argument group"""
        return self.parser.add_argument_group(title, description)

    def parse_args(self):
        """Parse and return arguments"""
        return self.parser.parse_args()

    def _get_epilog_text(self) -> str:
        """Generate dynamic epilog text based on script name"""
        return f"""
Examples:
  {self.script_name}                                    # Build and deploy
  {self.script_name} --build-only                       # Build package only
  {self.script_name} --local-lambda                     # Build and test locally
  {self.script_name} --budget-limit 2.00 \\
                     --budget-email you@example.com     # Custom budget
  {self.script_name} --no-budget                        # Skip budget enforcement
  {self.script_name} --dry-run                          # Show what would happen
"""


# Convenience function for backward compatibility
def parse_arguments(script_name: str = None) -> argparse.Namespace:
    """Convenience function for simple use cases"""
    parser = DeploymentArgumentParser(script_name)
    return parser.parse_args()
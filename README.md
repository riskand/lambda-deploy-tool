# Lambda Deploy Tool

Generic AWS Lambda deployment tool with budget enforcement, scheduling, and comprehensive error handling.

## Features

- ✅ **Generic and Reusable** - Configure everything via environment variables
- ✅ **Budget Enforcement** - Automatic Lambda shutdown when budget exceeded
- ✅ **EventBridge Scheduling** - Schedule Lambda executions with cron expressions
- ✅ **Parameter Store Integration** - Secure token storage
- ✅ **Local Testing** - Test Lambda packages before deployment
- ✅ **Dry Run Mode** - Preview changes without deploying
- ✅ **Package Exclusions** - Exclude dev dependencies from Lambda package

## Installation

```bash
pip install git+https://gitlab.com/luona-common-libraries/lambda-deploy-tool.git
```

## Quick Start

### 1. Create `.env` file

```bash
# Required
LAMBDA_FUNCTION_NAME=my-function
LAMBDA_HANDLER=my_module.lambda_function.handler
LAMBDA_SOURCE_FILES=my_module/__init__.py,my_module/lambda_function.py

# Optional (with defaults)
AWS_REGION=us-east-1
LAMBDA_RUNTIME=python3.12
LAMBDA_BUDGET_EMAIL=your-email@example.com
```

### 2. Deploy

```bash
lambda-deploy
```

## Documentation

See full documentation at: https://gitlab.com/luona-common-libraries/lambda-deploy-tool/wiki

## Extracted From

This tool was extracted from the PNPG Watch project to make it reusable across multiple Lambda projects.

Original source: ~/dev/pnpgwatch/deploy/

## License

MIT License

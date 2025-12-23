# lambda_deploy_tool/builder_container.py
"""
Container Builder for Lambda
"""
import logging
import subprocess
import tempfile
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ContainerBuilder:
    """Builds Docker images for Lambda container deployment"""

    def __init__(self, config):
        self.config = config

    def build_image(self, ecr_auth: dict) -> bool:
        """
        Build Docker image and push to ECR

        Returns:
            bool: True if successful
        """
        try:
            # Step 1: Docker login to ECR (skip in dry-run)
            if not self.config.dry_run:
                if not self._docker_login(ecr_auth):
                    return False

            # Step 2: Build Docker image
            build_success = self._docker_build()
            if not build_success:
                return False

            # Step 3: Push to ECR (unless disabled or dry-run)
            if not self.config.dry_run and not getattr(self.config, 'no_push', False):
                push_success = self._docker_push()
                return push_success

            return True

        except Exception as e:
            logger.error(f"❌ Container build failed: {e}")
            return False

    def _docker_login(self, ecr_auth: dict) -> bool:
        """Login to ECR with Docker"""
        logger.info("🔐 Logging into ECR...")

        if self.config.dry_run:
            logger.info("[DRY-RUN] Would login to ECR")
            return True

        cmd = [
            'docker', 'login',
            '--username', ecr_auth['username'],
            '--password-stdin',
            ecr_auth['registry']
        ]

        try:
            result = subprocess.run(
                cmd,
                input=ecr_auth['password'],
                text=True,
                capture_output=True,
                check=True
            )
            logger.info("✅ Docker login successful")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Docker login failed: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("❌ Docker not found. Install Docker first.")
            return False

    def _docker_build(self) -> bool:
        """Build Docker image"""
        logger.info("🔨 Building Docker image...")

        if self.config.dry_run:
            logger.info("[DRY-RUN] Would build Docker image")
            logger.info(f"[DRY-RUN]   Image: {self.config.ecr_repository_uri}")
            logger.info(f"[DRY-RUN]   Dockerfile: {self.config.dockerfile_path}")
            logger.info(f"[DRY-RUN]   Context: {self.config.docker_context}")
            logger.info(f"[DRY-RUN]   Platform: {self.config.platform}")
            return True

        # Build command
        cmd = [
            'docker', 'build',
            '--no-cache', 
            '-t', self.config.ecr_repository_uri,
            '-f', str(self.config.dockerfile_path),
            str(self.config.docker_context)
        ]

        # Add build args
        for key, value in self.config.get_build_args().items():
            cmd.extend(['--build-arg', f'{key}={value}'])

        # Add platform if specified
        if self.config.platform:
            cmd.extend(['--platform', self.config.platform])

        # Add cache from
        for cache in self.config.cache_from:
            cmd.extend(['--cache-from', cache])

        try:
            # Run build with real-time output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Stream output
            for line in process.stdout:
                line = line.strip()
                if line and not line.startswith('#'):
                    logger.info(f"  {line}")

            process.wait()

            if process.returncode == 0:
                logger.info(f"✅ Docker image built: {self.config.ecr_repository_uri}")
                return True
            else:
                logger.error(f"❌ Docker build failed with code {process.returncode}")
                return False

        except Exception as e:
            logger.error(f"❌ Docker build failed: {e}")
            return False

    def _docker_push(self) -> bool:
        """Push Docker image to ECR"""
        logger.info(f"📤 Pushing image to ECR: {self.config.ecr_repository_uri}")

        if self.config.dry_run:
            logger.info("[DRY-RUN] Would push image to ECR")
            return True

        cmd = ['docker', 'push', self.config.ecr_repository_uri]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Stream output
            for line in process.stdout:
                line = line.strip()
                if line:
                    logger.info(f"  {line}")

            process.wait()

            if process.returncode == 0:
                logger.info(f"✅ Docker image pushed to ECR")
                return True
            else:
                logger.error(f"❌ Docker push failed with code {process.returncode}")
                return False

        except Exception as e:
            logger.error(f"❌ Docker push failed: {e}")
            return False

    def test_locally(self, event: dict = None) -> bool:
        """Test container locally"""
        if not getattr(self.config, 'local_test_enabled', False):
            return True

        logger.info("🧪 Testing container locally...")

        # IMPORTANT: Skip if dry-run (image doesn't actually exist)
        if self.config.dry_run:
            logger.info("[DRY-RUN] Would test container locally")
            return True

        if event is None:
            event = getattr(self.config, 'local_test_event', {"test": "local"})

        # Create temporary event file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(event, f)
            event_file = f.name

        try:
            # Run container locally
            cmd = [
                'docker', 'run',
                '--rm',
                '-v', f'{event_file}:/var/task/event.json',
                '-e', 'AWS_LAMBDA_FUNCTION_NAME=local-test',
                '-e', 'AWS_LAMBDA_FUNCTION_MEMORY_SIZE=512',
                '-e', 'AWS_LAMBDA_FUNCTION_VERSION=$LATEST',
                '--entrypoint', '',
                self.config.ecr_repository_uri,
                '/lambda-entrypoint.sh',
                'sync_product.lambda_function.lambda_handler',
                '/var/task/event.json'
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info("✅ Local container test passed")
                logger.debug(f"Output: {result.stdout}")
                return True
            else:
                logger.error(f"❌ Local container test failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ Local container test timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Local container test failed: {e}")
            return False
        finally:
            # Clean up temp file
            Path(event_file).unlink(missing_ok=True)
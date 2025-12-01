# lambda_deploy_tool/builder.py
"""
Lambda package builder
Single Responsibility: Build Lambda deployment packages
"""
import logging
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Set, Optional

from .config import DeployConfig

logger = logging.getLogger(__name__)


class LambdaBuilder:
    """Builds Lambda deployment packages (SRP)"""

    def __init__(self, config: DeployConfig):
        self.config = config
        self.build_dir = config.output_dir / 'build'
        self.package_dir = self.build_dir / 'package'

    def build(self) -> Path:
        """Build Lambda package and return path to zip file"""
        logger.info("🔨 Building Lambda package...")

        self._check_gitlab_token()
        self._clean_build_dirs()
        self._install_dependencies()
        self._copy_source_code()
        package_path = self._create_zip_package()

        size_mb = package_path.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Package built: {package_path} ({size_mb:.2f} MB)")

        # Simple AWS limit check
        if size_mb > 68:
            logger.warning(f"⚠️  Package size ({size_mb:.2f} MB) is close to AWS 70MB limit")

        return package_path

    def _check_gitlab_token(self) -> None:
        """Check for GITLAB_TOKEN environment variable"""
        if not os.getenv('GITLAB_TOKEN'):
            logger.warning("⚠️  GITLAB_TOKEN not set")
            logger.warning("   This may fail when installing google-services from GitLab")
        else:
            logger.debug("✅ GITLAB_TOKEN found")

    def _clean_build_dirs(self) -> None:
        """Clean previous build directories"""
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.package_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created build directory: {self.package_dir}")

    def _install_dependencies(self) -> None:
        """Install Python dependencies using pip"""
        logger.info("📦 Installing dependencies...")

        requirements_file = Path('requirements.txt')
        if not requirements_file.exists():
            raise FileNotFoundError("requirements.txt not found")

        cmd = [
            sys.executable, '-m', 'pip', 'install',
            '-r', str(requirements_file),
            '--target', str(self.package_dir),
            '--no-cache-dir',
            '--quiet'
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("✅ Dependencies installed")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to install dependencies")
            logger.error(f"   stdout: {e.stdout}")
            logger.error(f"   stderr: {e.stderr}")
            if not os.getenv('GITLAB_TOKEN'):
                logger.error("💡 This might be due to missing GITLAB_TOKEN")
            raise

    def _copy_source_code(self) -> None:
        """Copy source code from current directory"""
        logger.info(f"📋 Copying source code from: {self.config.source_dir}")

        if not self.config.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {self.config.source_dir}")

        copied_count = 0
        for item in self.config.source_dir.iterdir():
            # Skip unnecessary files/patterns
            if self._should_skip(item):
                logger.debug(f"  Skipping: {item.name}")
                continue

            dest_path = self.package_dir / item.name

            if item.is_file():
                shutil.copy2(item, dest_path)
                copied_count += 1
                logger.debug(f"  Copied file: {item.name}")
            elif item.is_dir():
                # For directories, copy only .py files
                py_files = list(item.rglob("*.py"))
                if py_files:
                    dest_path.mkdir(exist_ok=True)
                    for py_file in py_files:
                        rel_path = py_file.relative_to(item)
                        full_dest = dest_path / rel_path
                        full_dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(py_file, full_dest)
                        copied_count += 1
                    logger.debug(f"  Copied {len(py_files)} .py files from: {item.name}")

        if copied_count == 0:
            raise FileNotFoundError(f"No source files found in {self.config.source_dir}")

        logger.info(f"✅ Copied {copied_count} source files")

    def _should_skip(self, item: Path) -> bool:
        """Check if item should be skipped"""
        skip_patterns = {
            # Build artifacts
            'dist', 'build', '__pycache__', '.pyc', '.pyo', '.pyd',
            # Version control
            '.git', '.gitignore',
            # Environment
            '.env', '.env.local', '.env.deploy', 'venv',
            # Deployment
            'deploy',  # Skip the deploy directory itself!
            # Tests
            'tests', 'test',
            # Other
            '.DS_Store', 'node_modules', '.pytest_cache', 'coverage'
        }

        name = item.name
        return any(
            name.startswith(pattern) or
            name.endswith(pattern) or
            name == pattern
            for pattern in skip_patterns
        )

    def _create_zip_package(self) -> Path:
        """Create ZIP package for Lambda"""
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self.config.package_path

        logger.info(f"📦 Creating ZIP package: {zip_path}")

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            file_count = 0
            for root, dirs, files in os.walk(self.package_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(self.package_dir)
                    zipf.write(file_path, arcname)
                    file_count += 1

        logger.debug(f"  Added {file_count} files to package")
        return zip_path
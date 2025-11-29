# deploy/builder.py
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
from typing import List



logger = logging.getLogger(__name__)


class LambdaBuilder:
    """Builds Lambda deployment packages (SRP)"""

    SOURCE_FILES = [
        'config.py',
        'email_processor.py',
        '__init__.py',
        'lambda_function.py',
        'local_runner.py',
        'pnpg_service.py',
        'sheets_manager.py'
    ]

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
        """Copy PNPG Watch source code to package"""
        logger.info(f"📋 Copying source code from: {self.config.source_dir}")

        if not self.config.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {self.config.source_dir}")

        dest_dir = self.package_dir / 'pnpgwatch'
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        copied_count = 0
        for source_file in self.SOURCE_FILES:
            src_path = self.config.source_dir / source_file
            if src_path.exists():
                dest_path = dest_dir / source_file
                shutil.copy2(src_path, dest_path)
                copied_count += 1
                logger.debug(f"  Copied {source_file}")
            else:
                logger.warning(f"  Source file not found: {src_path}")

        if copied_count == 0:
            raise FileNotFoundError(f"No source files found in {self.config.source_dir}")

        logger.info(f"✅ Copied {copied_count}/{len(self.SOURCE_FILES)} source files")

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

    def verify_package(self, package_path: Path) -> bool:
        """Verify package contents"""
        logger.info(f"🔍 Verifying package: {package_path}")

        required_dirs = [
            'pnpgwatch',
            'google_services',
            'google_auth_oauthlib',
            'googleapiclient',
            'bs4',
            'boto3'
        ]

        required_files = [
            'pnpgwatch/lambda_function.py',
            'pnpgwatch/pnpg_service.py',
            'pnpgwatch/config.py',
        ]

        try:
            with zipfile.ZipFile(package_path, 'r') as zipf:
                contents = zipf.namelist()

                # Check directories
                missing_dirs = []
                for dir_name in required_dirs:
                    if not any(item.startswith(dir_name + '/') for item in contents):
                        missing_dirs.append(dir_name)

                if missing_dirs:
                    logger.error(f"❌ Missing directories: {', '.join(missing_dirs)}")
                    return False

                # Check files
                missing_files = []
                for file_name in required_files:
                    if file_name not in contents:
                        missing_files.append(file_name)

                if missing_files:
                    logger.error(f"❌ Missing files: {', '.join(missing_files)}")
                    return False

                logger.info(f"✅ Package verification passed ({len(contents)} files)")
                return True

        except Exception as e:
            logger.error(f"❌ Error verifying package: {e}")
            return False
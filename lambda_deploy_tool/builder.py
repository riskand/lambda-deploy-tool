# lambda_deploy_tool/builder.py
"""
Lambda package builder - Independent of specific application
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

    def __init__(self, config):
        self.config = config
        self.build_dir = config.output_dir / 'build'
        self.package_dir = self.build_dir / 'package'

    def build(self, exclude_patterns: List[str] = None, requirements_file: Path = None) -> Path:
        """Build Lambda package and return path to zip file"""
        logger.info("🔨 Building Lambda package...")

        self._clean_build_dirs()
        self._install_dependencies(requirements_file)

        # Auto-discover source files
        source_files = self.config.discover_source_files(exclude_patterns)
        self._copy_source_code(source_files)

        package_path = self._create_zip_package()

        size_mb = package_path.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Package built: {package_path} ({size_mb:.2f} MB)")
        logger.info(f"📁 Included {len(source_files)} source files")

        return package_path

    def _clean_build_dirs(self) -> None:
        """Clean previous build directories"""
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.package_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created build directory: {self.package_dir}")

    def _install_dependencies(self, requirements_file: Path = None) -> None:
        """Install Python dependencies using pip"""
        logger.info("📦 Installing dependencies...")

        if not requirements_file:
            requirements_file = Path('requirements.txt')

        if not requirements_file.exists():
            logger.warning(f"Requirements file not found: {requirements_file}")
            return

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
            logger.error(f"❌ Failed to install dependencies: {e.stderr}")
            raise

    def _copy_source_code(self, source_files: List[Path]) -> None:
        """Copy source code to package"""
        logger.info(f"📋 Copying source code from: {self.config.source_dir}")

        if not self.config.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {self.config.source_dir}")

        copied_count = 0
        for source_file in source_files:
            src_path = self.config.source_dir / source_file
            if src_path.exists():
                dest_path = self.package_dir / source_file
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest_path)
                copied_count += 1
                logger.debug(f"  Copied {source_file}")
            else:
                logger.warning(f"  Source file not found: {src_path}")

        if copied_count == 0:
            raise FileNotFoundError(f"No source files found in {self.config.source_dir}")

        logger.info(f"✅ Copied {copied_count} files")

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
"""
Adapter for the unrpa library to support Ren'Py archive extraction on Linux/macOS.

Uses subprocess to invoke the unrpa command-line tool for maximum compatibility.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional, List


def _is_unrpa_installed() -> bool:
    """Check if unrpa command is available via subprocess."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "unrpa", "--help"],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


class UnrpaAdapter:
    """Wraps the unrpa library to provide extraction capabilities programmatically."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def is_available() -> bool:
        """Check if unrpa library is installed and available."""
        return _is_unrpa_installed()

    def extract_rpa(self, rpa_path: Path, output_dir: Path) -> bool:
        """
        Extract a single RPA file to the output directory.
        
        Args:
            rpa_path: Path to the .rpa file
            output_dir: Directory where files should be extracted
            
        Returns:
            bool: True if extraction was successful, False otherwise.
        """
        if not self.is_available():
            self.logger.error("unrpa library is not installed. Please install it using 'pip install unrpa'.")
            return False

        try:
            self.logger.info(f"Extracting {rpa_path} to {output_dir}")
            
            # Use unrpa as a command-line tool via python -m unrpa
            # This is more reliable than trying to use the internal API
            result = subprocess.run(
                [
                    sys.executable, "-m", "unrpa",
                    "--path", str(output_dir),
                    str(rpa_path)
                ],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per archive
            )
            
            if result.returncode == 0:
                self.logger.info(f"Successfully extracted {rpa_path.name}")
                if result.stdout:
                    self.logger.debug(f"unrpa output: {result.stdout}")
                return True
            else:
                self.logger.error(f"unrpa failed for {rpa_path.name}: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.logger.error(f"Extraction timed out for {rpa_path}")
            return False
        except Exception as e:
            self.logger.error(f"Error extracting RPA {rpa_path}: {e}")
            return False

    def extract_game(self, game_dir: Path) -> bool:
        """
        Finds all .rpa files in the game directory and extracts them.
        
        Args:
            game_dir: The 'game' directory of the Ren'Py project.
            
        Returns:
            bool: True if at least one RPA was extracted or none found (success state), False on critical error.
        """
        if not game_dir.exists():
            self.logger.error(f"Game directory not found: {game_dir}")
            return False

        rpa_files = list(game_dir.glob("**/*.rpa"))
        if not rpa_files:
            self.logger.info("No .rpa files found to extract.")
            return True

        success_count = 0
        for rpa_file in rpa_files:
            # Extract to the same directory as the rpa file (standard behavior)
            if self.extract_rpa(rpa_file, rpa_file.parent):
                success_count += 1
                
                # Rename the rpa file to .rpa.bak to prevent game from loading it + extracted files
                try:
                    bak_path = rpa_file.with_suffix(".rpa.bak")
                    if bak_path.exists():
                        bak_path.unlink()
                    rpa_file.rename(bak_path)
                    self.logger.info(f"Renamed {rpa_file.name} to .rpa.bak")
                except OSError as e:
                    self.logger.warning(f"Could not rename extracted RPA {rpa_file}: {e}")

        return success_count > 0

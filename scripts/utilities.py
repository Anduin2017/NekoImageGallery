from pathlib import Path

from loguru import logger


def gather_valid_files(root: Path, glob_pattern='**/*.*'):
    for item in root.glob(glob_pattern):
        if item.suffix in ['.jpg', '.png', '.jpeg', '.jfif', '.webp']:
            yield item
        else:
            logger.warning("Unsupported file type: {}. Skip...", item.suffix)

import uuid
from pathlib import Path

from PIL import Image
from loguru import logger

from app.Services import db_context
from app.config import config
from .utilities import gather_valid_files


def gen_thumbnail(item: Path, static_thumb_path: Path, id: uuid.UUID):
    try:
        img = Image.open(item)
    except Exception as e:
        logger.error("Error when opening image {}: {}", item, e)
        return False

    # generate thumbnail max size 256*256
    img.thumbnail((256, 256))
    img.save(static_thumb_path / f'{str(id)}.webp', 'WebP')
    img.close()
    logger.success("Thumbnail for {} generated!", id)
    return True


async def main():
    static_path = Path(config.static_file.path)
    static_thumb_path = static_path / 'thumbnails'
    if not static_thumb_path.exists():
        static_thumb_path.mkdir()
    count = 0
    for item in gather_valid_files(static_path, '*.*'):
        count += 1
        logger.info("[{}] Processing {}", str(count), item.relative_to(static_path).__str__())
        size = item.stat().st_size
        if size < 1024 * 500:
            logger.warning("File size too small: {}. Skip...", size)
            continue
        try:
            if (static_thumb_path / f'{item.stem}.webp').exists():
                logger.warning("Thumbnail for {} already exists. Skip...", item.stem)
                continue
            id = uuid.UUID(item.stem)
        except ValueError:
            logger.warning("Invalid file name: {}. Skip...", item.stem)
            continue
        try:
            imgdata = await db_context.retrieve_by_id(str(id))
        except Exception as e:
            logger.error("Error when retrieving image {}: {}", id, e)
            continue

        if gen_thumbnail(item, static_thumb_path, id):
            # update payload
            imgdata.thumbnail_url = f'/static/thumbnails/{str(id)}.webp'
            await db_context.updatePayload(imgdata)
            logger.success("Payload for {} updated!", id)

    logger.success("OK. Updated {} items.", count)

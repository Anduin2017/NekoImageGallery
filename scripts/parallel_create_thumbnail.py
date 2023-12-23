import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from loguru import logger

from app.Services import db_context
from app.config import config
from .local_create_thumbnail import gen_thumbnail
from .utilities import gather_valid_files


async def main(args):
    static_path = Path(config.static_file.path)
    static_thumb_path = static_path / 'thumbnails'
    if not static_thumb_path.exists():
        static_thumb_path.mkdir()
    count = 0

    loop = asyncio.get_running_loop()

    def thumb_generator(item: Path, idx: int):
        logger.info("[{}] Processing {}", str(idx), item.relative_to(static_path).__str__())
        size = item.stat().st_size
        if size < 1024 * 500:
            logger.warning("File size too small: {}. Skip...", size)
            return
        try:
            if (static_thumb_path / f'{item.stem}.webp').exists():
                logger.warning("Thumbnail for {} already exists. Skip...", item.stem)
                return
            id = uuid.UUID(item.stem)
        except ValueError:
            logger.warning("Invalid file name: {}. Skip...", item.stem)
            return
        try:
            imgdata = asyncio.run_coroutine_threadsafe(db_context.retrieve_by_id(str(id)), loop).result()
        except Exception as e:
            logger.error("Error when retrieving image {}: {}", id, e)
            return

        if gen_thumbnail(item, static_thumb_path / f'{str(id)}.webp'):
            # update payload
            imgdata.thumbnail_url = f'/static/thumbnails/{str(id)}.webp'
            asyncio.run_coroutine_threadsafe(db_context.updatePayload(imgdata), loop).result()
            logger.success("Payload for {} updated!", id)

    tasks = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for item in gather_valid_files(static_path, '*.*'):
            count += 1
            j = executor.submit(thumb_generator, item, count)
            j.add_done_callback(lambda t: tasks.remove(t))
            tasks.append(j)

        while len(tasks) > 0:
            await asyncio.sleep(1)

    logger.success("OK. Updated {} items.", count)

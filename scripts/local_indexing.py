if __name__ == '__main__':
    import sys

    sys.path.insert(1, './')

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from pathlib import Path
from shutil import copy2
from uuid import uuid4

from PIL import Image
from loguru import logger

from app.Models.img_data import ImageData
from app.Services import transformers_service, db_context, ocr_service
from app.config import config


def parse_args():
    parser = argparse.ArgumentParser(description='Create Qdrant collection')
    parser.add_argument('--copy-from', dest="local_index_target_dir", type=str, required=True,
                        help="Copy from this directory")
    return parser.parse_args()


def copy_and_index(filePath: Path) -> ImageData | None:
    try:
        img = Image.open(filePath)
    except Exception as e:
        logger.error("Error when opening image {}: {}", filePath, e)
        return None
    id = uuid4()
    img_ext = filePath.suffix
    image_ocr_result = None
    text_contain_vector = None
    [width, height] = img.size
    try:
        image_vector = transformers_service.get_image_vector(img)
        if config.ocr_search.enable:
            image_ocr_result = ocr_service.ocr_interface(img)  # This will modify img if you use preprocess!
            if image_ocr_result != "":
                text_contain_vector = transformers_service.get_bert_vector(image_ocr_result)
            else:
                image_ocr_result = None
    except Exception as e:
        logger.error("Error when processing image {}: {}", filePath, e)
        return None
    imgdata = ImageData(id=id,
                        url=f'/static/{id}{img_ext}',
                        image_vector=image_vector,
                        text_contain_vector=text_contain_vector,
                        index_date=datetime.now(),
                        width=width,
                        height=height,
                        aspect_ratio=float(width) / height,
                        ocr_text=image_ocr_result)

    # copy to static
    copy2(filePath, Path(config.static_file.path) / f'{id}{img_ext}')
    return imgdata


@logger.catch()
async def main(args):
    root = Path(args.local_index_target_dir)
    static_path = Path(config.static_file.path)
    if not static_path.exists():
        static_path.mkdir()
    buffer = []
    counter = 0

    tasks = []
    db_tasks: list[asyncio.Task] = []

    event_loop = asyncio.get_event_loop()

    def post_exec(f: Future):
        nonlocal buffer
        tasks.remove(f)
        result = f.result()
        if result is None:
            return
        buffer.append(result)
        if len(buffer) >= 20:
            l_buffer = buffer
            buffer = []
            logger.info("Upload {} element to database", len(l_buffer))
            db_tasks.append(asyncio.ensure_future(db_context.insertItems(l_buffer), loop=event_loop))

    with ThreadPoolExecutor(max_workers=8) as executor:
        for item in root.glob('**/*.*'):

            counter += 1
            logger.info("[{}] Indexing {}", str(counter), item.relative_to(root).__str__())

            if item.suffix not in ['.jpg', '.png', '.jpeg', '.jfif', '.webp']:
                logger.warning("Unsupported file type: {}. Skip...", item.suffix)
                continue

            proc_task = executor.submit(copy_and_index, item)
            proc_task.add_done_callback(post_exec)
            tasks.append(proc_task)

        # executor.shutdown(wait=True) # This will aggressively block the main thread

        while len(tasks) > 0:
            for task in db_tasks:  # Attempt to Complete all db_action tasks
                if not task.done():
                    await task
                db_tasks.remove(task)
            await asyncio.sleep(1)

        for task in db_tasks:
            await task
    if len(buffer) > 0:
        logger.info("Upload {} element to database", len(buffer))
        await db_context.insertItems(buffer)
        logger.success("Indexing completed! {} images indexed", counter)


if __name__ == '__main__':
    args = parse_args()
    asyncio.run(main(args))

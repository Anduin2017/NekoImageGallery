import asyncio
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path

from loguru import logger

from app.Services import db_context
from app.config import config
from .local_indexing import copy_and_index, gather_valid_files


@logger.catch()
async def main(args):
    root = Path(args.local_index_target_dir)
    static_path = Path(config.static_file.path)
    workers_count = args.workers
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

    with ThreadPoolExecutor(max_workers=workers_count) as executor:
        for item in gather_valid_files(root):
            counter += 1
            logger.info("[{}] Indexing {}", str(counter), item.relative_to(root).__str__())

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

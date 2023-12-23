import argparse
import asyncio
import collections

import uvicorn


def parse_args():
    parser = argparse.ArgumentParser(prog="NekoImageGallery Server",
                                     description='Ciallo~ Welcome to NekoImageGallery Server.',
                                     epilog="Build with ♥ By EdgeNeko. Github: "
                                            "https://github.com/hv0905/NekoImageGallery")
    db_actions = parser.add_argument_group('Database actions',
                                           description='When the following flags is set, '
                                                       'will not start the server.')
    db_actions.add_argument('--init-database', action='store_true',
                            help="Initialize qdrant database using connection settings in config.py.")

    local_indexing_actions = parser.add_argument_group('Local indexing actions',
                                                       description='When the following flags is set, '
                                                                   'will not start the server.')

    local_indexing_actions.add_argument('--local-index', dest="local_index_target_dir", type=str,
                                        help="Index all the images in this directory and copy them to "
                                             "static folder set in configuration.")
    local_indexing_actions.add_argument('--local-create-thumbnail', action='store_true',
                                        help='Create thumbnail for all local images in static folder set in config.py.')
    local_indexing_actions.add_argument('--parallel', '-j', dest="workers", type=int, default=1,
                                        help="Number of parallel threads when performing local index. "
                                             "Try this if your device isn't fully utilized. "
                                             "Use 1 to disable parallel.\n"
                                             "WARN: Parallelism is in an alpha state and may cause unexpected behavior."
                                             "It is intended for developers and early adopters who are comfortable "
                                             "debugging issues or providing detailed bug reports.\n"
                                             "Default is 1 (disabled).")

    server_options = parser.add_argument_group('Server options')

    server_options.add_argument('--port', type=int, default=8000, help="Port to listen on, default is 8000")
    server_options.add_argument('--host', type=str, default="0.0.0.0", help="Host to bind on, default is 0.0.0.0")
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    if args.init_database:
        from scripts import qdrant_create_collection
        from app.config import config

        qdrant_create_collection.create_coll(
            collections.namedtuple('Options', ['host', 'port', 'name'])(config.qdrant.host, config.qdrant.port,
                                                                        config.qdrant.coll))
    elif args.local_index_target_dir is not None:
        from app.config import environment

        environment.local_indexing = True
        if args.workers > 1:
            from scripts import parallel_local_indexing

            asyncio.run(parallel_local_indexing.main(args))
        else:
            from scripts import local_indexing

            asyncio.run(local_indexing.main(args))
    elif args.local_create_thumbnail:
        from app.config import environment

        environment.local_thumb = True
        if args.workers > 1:
            from scripts import parallel_create_thumbnail

            asyncio.run(parallel_create_thumbnail.main(args))
        else:
            from scripts import local_create_thumbnail

            asyncio.run(local_create_thumbnail.main())
    else:
        uvicorn.run("app.webapp:app", host=args.host, port=args.port)

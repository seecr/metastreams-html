#!/usr/bin/env python

from metastreams.html.server import create_server
from argparse import ArgumentParser
import asyncio

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--modules', help='Data directory', required=True)
    parser.add_argument('--port', help='Portnumber', type=int, default=8080)
    parser.add_argument('--static_path', help='path static files are served at.', default="/static")
    parser.add_argument('--static_dir', help='directory containing static files')
    args = parser.parse_args()

    loop = asyncio.get_event_loop()

    create_server(loop, args.port, args.modules, args.static_dir, args.static_path)
    loop.run_forever()

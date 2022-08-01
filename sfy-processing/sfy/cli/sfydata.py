#! /usr/bin/env python
import click
from tabulate import tabulate
from tqdm import tqdm
from datetime import datetime, timezone
import coloredlogs
import logging

logger = logging.getLogger(__name__)

from sfy.hub import Hub, StorageInfo
from sfy.cli.track import track
from sfy.cli.axl import axl
from sfy.cli.ctrl import ctrl
from sfy.cli.store import store


@click.group()
@click.option('--log', default='info', type=str, help='Python log level')
def sfy(log):
    coloredlogs.install(level=log)


sfy.add_command(track)
sfy.add_command(axl)
sfy.add_command(ctrl)
sfy.add_command(store)


@sfy.command(help='List available buoys or data')
@click.argument('dev', default=None, required=False)
@click.option('--start',
              default=None,
              help='Filter packages after this time',
              type=click.DateTime())
@click.option('--end',
              default=None,
              help='Filter packages before this time',
              type=click.DateTime())
def list(dev, start, end):
    hub = Hub.from_env()

    if dev is None:
        buoys = hub.buoys()

        last = [b.last() if 'lost+found' not in b.dev else None for b in buoys]
        last = [l.received_datetime if l else None for l in last]

        storage_info = [
            b.storage_info()
            if 'lost+found' not in b.dev else StorageInfo.empty()
            for b in buoys
        ]

        buoys = [[b.dev, b.name, l, si.current_id, si.sent_id]
                 for b, l, si in zip(buoys, last, storage_info)]
        buoys.sort(key=lambda b: b[2].timestamp() if b[2] else 0)

        print(
            tabulate(buoys,
                     headers=[
                         'Buoys',
                         'Name',
                         'Last contact',
                         'Current ID',
                         'Sent ID',
                     ]))
    else:
        buoy = hub.buoy(dev)
        logger.info(f"Listing packages for {buoy}")
        pcks = buoy.axl_packages_range(start, end)

        pcks = [[
            ax.start.strftime("%Y-%m-%d %H:%M:%S UTC"), ax.lon, ax.lat,
            ax.received_datetime.strftime("%Y-%m-%d %H:%M:%S UTC"),
            ax.storage_id, ax.fname
        ] for ax in pcks]
        print(
            tabulate(
                pcks,
                headers=['DataTime', 'Lon', 'Lat', 'TxTime', 'StID', 'File']))


@sfy.command(help='Print JSON')
@click.argument('dev')
@click.argument('file')
def json(dev, file):
    hub = Hub.from_env()
    buoy = hub.buoy(dev)
    ax = buoy.package(file)
    print(str(ax.json()))


@sfy.command(help='Show log messages')
@click.argument('dev')
@click.option('--start',
              default=None,
              help='Filter packages after this time',
              type=click.DateTime())
@click.option('--end',
              default=None,
              help='Filter packages before this time',
              type=click.DateTime())
def log(dev, start, end):
    import json

    hub = Hub.from_env()
    buoy = hub.buoy(dev)
    logger.info(f'Fetching log entries for {buoy}')

    pcks = buoy.fetch_packages_range(start, end)
    # pcks = buoy.packages_range(start, end)
    pcks = [p for p in pcks if 'health.qo' in p[1]]
    pcks = [p[2] for p in tqdm(pcks)]

    pcks = [json.loads(p) for p in pcks]
    pcks.sort(key=lambda p: p.get('when', 0))
    pcks = [[datetime.utcfromtimestamp(p.get('when', 0)), p['body']['text']]
            for p in pcks]
    print(tabulate(pcks, headers=['Time', 'Message']))


if __name__ == '__main__':
    sfy()

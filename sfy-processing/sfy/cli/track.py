#! /usr/bin/env python
import click
from tqdm import tqdm
import matplotlib.pyplot as plt
from cartopy import crs, feature as cfeature
import pandas as pd
import io

from sfy.hub import Hub


@click.group()
def track():
    pass


@track.command(help='Plot track of buoy')
@click.argument('dev')
@click.option('--fast', is_flag=True, help='Plot faster at lower quality.')
@click.option('--start',
              default=None,
              help='Filter packages after this time',
              type=click.DateTime())
@click.option('--end',
              default=None,
              help='Filter packages before this time',
              type=click.DateTime())
@click.option('--margins',
              help='Map limits margins, format: 0.5,0.5',
              default=None,
              type=str)
@click.option('--save', help='Save to file', default=None, type=click.File())
def map(dev, fast, start, end, margins, save):
    hub = Hub.from_env()
    buoy = hub.buoy(dev)
    print(buoy)

    pcks = buoy.position_packages_range(start, end)

    lon = [pck.longitude for pck in pcks]
    lat = [pck.latitude for pck in pcks]

    print('plotting..')
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1, projection=crs.Mercator())

    if fast:
        # ax.stock_img()
        ax.coastlines(resolution='10m')
        ax.natural_earth_shp(name='land', resolution='10m', zorder=-1)
    else:
        gsh = cfeature.GSHHSFeature(levels=[1],
                                    facecolor=cfeature.COLORS['land'])
        ax.add_feature(gsh, zorder=-1)

    ax.plot(lon, lat, '-o', transform=crs.PlateCarree(), label=buoy.dev)

    if margins is not None:
        ms = margins.split(',')
        mx = float(ms[0])
        my = float(ms[1])
        margins = (mx, my)
    else:
        margins = (0.2, 0.2)

    ax.margins(*margins)

    ax.gridlines(crs.PlateCarree(), draw_labels=True)

    plt.legend()
    plt.title(f'Track of {buoy.dev}')

    if save is not None:
        plt.savefig(save)
    else:
        plt.show()


@track.command(help='Output CSV of position')
@click.argument('dev')
@click.option('--start',
              default=None,
              help='Filter packages after this time',
              type=click.DateTime())
@click.option('--end',
              default=None,
              help='Filter packages before this time',
              type=click.DateTime())
@click.option('--tower',
              default=False,
              is_flag=True,
              help='Include positions based on cell tower',
              type=bool)
def csv(dev, start, end, tower):
    hub = Hub.from_env()
    buoy = hub.buoy(dev)

    pcks = buoy.position_packages_range(start, end)

    tm = [pck.best_position_time for pck in pcks]
    lon = [pck.longitude for pck in pcks]
    lat = [pck.latitude for pck in pcks]
    typ = [pck.position_type for pck in pcks]
    file = [pck.file for pck in pcks]
    bearing = [pck.body.get('bearing', None) for pck in pcks]
    velocity = [pck.body.get('velocity', None) for pck in pcks]
    distance = [pck.body.get('distance', None) for pck in pcks]
    temperature = [pck.body.get('temperature', None) for pck in pcks]

    df = pd.DataFrame({
        'Device': buoy.dev,
        'Time': tm,
        'Type': typ,
        'Longitude': lon,
        'Latitude': lat,
        'File': file,
        'Bearing': bearing,
        'Velocity': velocity,
        'Distance': distance,
        'Temperature': temperature,
    })

    if not tower:
        df = df[df['Type'] == 'gps']

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    print(buf.getvalue())


if __name__ == '__main__':
    track()

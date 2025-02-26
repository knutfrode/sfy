import numpy as np
import xarray as xr
from pathlib import Path


class AxlTimeseries:
    def z_spectrum(self):
        """
        Calculate spectrum
        """
        pass

    def z_spectrogram(self):
        """
        Calculate spectrogram
        """
        pass

    def extra_attrs(self):
        return {}

    def to_dataset(self):
        ds = xr.Dataset(
            data_vars={
                'w_z':
                xr.Variable(
                    ('time'),
                    self.z.astype(np.float32),
                    attrs={
                        'unit': 'm/s^2',
                        'long_name': 'sea_water_wave_z_acceleration',
                        'description':
                        'Vertical acceleration (including gravity)'
                    }),
                'w_x':
                xr.Variable(
                    ('time'),
                    self.x.astype(np.float32),
                    attrs={
                        'unit': 'm/s^2',
                        'long_name': 'sea_water_wave_x_acceleration',
                        'description': 'Horizontal x-axis acceleration'
                    }),
                'w_y':
                xr.Variable(
                    ('time'),
                    self.y.astype(np.float32),
                    attrs={
                        'unit': 'm/s^2',
                        'long_name': 'sea_water_wave_y_acceleration',
                        'description': 'Horizontal y-axis acceleration'
                    }),
                'lon':
                xr.Variable(
                    ('position_time'),
                    np.array(self.lons, dtype=np.float64),
                    attrs={
                        'units': "degrees_east",
                        'standard_name': "longitude",
                        'long_name': "longitude"
                    }),
                'lat':
                xr.Variable(
                    ('position_time'),
                    np.array(self.lats, dtype=np.float64),
                    attrs={
                        'units': "degrees_north",
                        'standard_name': "latitude",
                        'long_name': "latitude"
                    }),
                'package_start':
                xr.Variable(('received'), [
                    np.datetime64(int(s.timestamp() * 1000.), 'ms') if s else None
                    for s in self.start_times
                ],
                            attrs={
                                'description':
                                'Timestamp at start of each batch (package) of samples.'
                            }),
                'added':
                xr.Variable(('received'), [
                    np.datetime64(int(s.timestamp() * 1000.), 'ms') if s else None
                    for s in self.added_times
                ],
                            attrs={
                                'description':
                                'Time package was added to notecard.'
                            }),
                'storage_id':
                xr.Variable(('received'),
                            np.array([
                                id if id is not None else np.nan
                                for id in self.storage_ids
                            ]),
                            attrs={'description': 'ID of packge on SD-card'}),
            },
            coords={
                'time':
                xr.Variable(('time'), [
                    np.datetime64(int(s.timestamp() * 1000.), 'ms')
                    for s in self.time
                ]),
                'position_time':
                xr.Variable(
                    'position_time',
                    [np.datetime64(int(s), 's') if s else np.nan for s in self.position_times],
                    attrs={
                        'description': 'Time of position fix for each package'
                    }),
                'received':
                xr.Variable(('received'), [
                    np.datetime64(int(s.timestamp() * 1000.), 'ms')
                    for s in self.received_times
                ],
                            attrs={
                                'description':
                                'Time package was received by data-hub'
                            }),
            },
            attrs={
                'frequency': self.frequency,
                'frequency:unit': 'Hz',
                'dt': self.dt,
                'dt:unit': 's',
                'homepage': 'https://github.com/gauteh/sfy',
                'buoy_type': 'sfy',
                'buoy_device': self.device,
                'buoy_name': self.sn,
                **self.extra_attrs()
            })

        return ds

    def to_netcdf(self, filename: Path):
        """
        Write a CF-compliant NetCDF file to filename.
        """
        self.to_dataset().to_netcdf(filename, format='NETCDF4')

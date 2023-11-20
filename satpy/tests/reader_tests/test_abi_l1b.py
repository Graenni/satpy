#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2017 Satpy developers
#
# This file is part of satpy.
#
# satpy is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# satpy is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# satpy.  If not, see <http://www.gnu.org/licenses/>.
"""The abi_l1b reader tests package."""

import unittest
from unittest import mock

import numpy as np
import pytest
import xarray as xr

from satpy.tests.utils import make_dataid


def _create_fake_rad_dataarray(rad=None):
    x_image = xr.DataArray(0.)
    y_image = xr.DataArray(0.)
    time = xr.DataArray(0.)
    if rad is None:
        rad_data = (np.arange(10.).reshape((2, 5)) + 1.) * 50.
        rad_data = (rad_data + 1.) / 0.5
        rad_data = rad_data.astype(np.int16)
        rad = xr.DataArray(
            rad_data,
            dims=("y", "x"),
            attrs={
                "scale_factor": 0.5,
                "add_offset": -1.,
                "_FillValue": 1002,
                "units": "W m-2 um-1 sr-1",
                "valid_range": (0, 4095),
            }
        )
    rad.coords["t"] = time
    rad.coords["x_image"] = x_image
    rad.coords["y_image"] = y_image
    return rad


def _create_fake_rad_dataset(rad=None):
    rad = _create_fake_rad_dataarray(rad=rad)

    x__ = xr.DataArray(
        range(5),
        attrs={"scale_factor": 2., "add_offset": -1.},
        dims=("x",)
    )
    y__ = xr.DataArray(
        range(2),
        attrs={"scale_factor": -2., "add_offset": 1.},
        dims=("y",)
    )
    proj = xr.DataArray(
        [],
        attrs={
            "semi_major_axis": 1.,
            "semi_minor_axis": 1.,
            "perspective_point_height": 1.,
            "longitude_of_projection_origin": -90.,
            "latitude_of_projection_origin": 0.,
            "sweep_angle_axis": u"x"
        }
    )

    fake_dataset = xr.Dataset(
        data_vars={
            "Rad": rad,
            "band_id": np.array(8),
            # 'x': x__,
            # 'y': y__,
            "x_image": xr.DataArray(0.),
            "y_image": xr.DataArray(0.),
            "goes_imager_projection": proj,
            "yaw_flip_flag": np.array([1]),
            "planck_fk1": np.array(13432.1),
            "planck_fk2": np.array(1497.61),
            "planck_bc1": np.array(0.09102),
            "planck_bc2": np.array(0.99971),
            "esun": np.array(2017),
            "nominal_satellite_subpoint_lat": np.array(0.0),
            "nominal_satellite_subpoint_lon": np.array(-89.5),
            "nominal_satellite_height": np.array(35786.02),
            "earth_sun_distance_anomaly_in_AU": np.array(0.99)
        },
        coords={
            "t": rad.coords["t"],
            "x": x__,
            "y": y__,

        },
        attrs={
            "time_coverage_start": "2017-09-20T17:30:40.8Z",
            "time_coverage_end": "2017-09-20T17:41:17.5Z",
        },
    )
    return fake_dataset


class Test_NC_ABI_L1B_Base(unittest.TestCase):
    """Common setup for NC_ABI_L1B tests."""

    @mock.patch("satpy.readers.abi_base.xr")
    def setUp(self, xr_, rad=None, clip_negative_radiances=False):
        """Create a fake dataset using the given radiance data."""
        from satpy.readers.abi_l1b import NC_ABI_L1B

        xr_.open_dataset.return_value = _create_fake_rad_dataset(rad=rad)
        self.reader = NC_ABI_L1B("filename",
                                 {"platform_shortname": "G16", "observation_type": "Rad",
                                  "suffix": "custom",
                                  "scene_abbr": "C", "scan_mode": "M3"},
                                 {"filetype": "info"},
                                 clip_negative_radiances=clip_negative_radiances)


class TestABIYAML:
    """Tests for the ABI L1b reader's YAML configuration."""

    @pytest.mark.parametrize(("channel", "suffix"),
                             [("C{:02d}".format(num), suffix)
                              for num in range(1, 17)
                              for suffix in ("", "_test_suffix")])
    def test_file_patterns_match(self, channel, suffix):
        """Test that the configured file patterns work."""
        from satpy.readers import configs_for_reader, load_reader
        reader_configs = list(configs_for_reader("abi_l1b"))[0]
        reader = load_reader(reader_configs)
        fn1 = ("OR_ABI-L1b-RadM1-M3{}_G16_s20182541300210_e20182541300267"
               "_c20182541300308{}.nc").format(channel, suffix)
        loadables = reader.select_files_from_pathnames([fn1])
        assert len(loadables) == 1
        if not suffix and channel in ["C01", "C02", "C03", "C05"]:
            fn2 = ("OR_ABI-L1b-RadM1-M3{}_G16_s20182541300210_e20182541300267"
                   "_c20182541300308-000000_0.nc").format(channel)
            loadables = reader.select_files_from_pathnames([fn2])
            assert len(loadables) == 1


class Test_NC_ABI_L1B(Test_NC_ABI_L1B_Base):
    """Test the NC_ABI_L1B reader."""

    def test_basic_attributes(self):
        """Test getting basic file attributes."""
        from datetime import datetime
        assert self.reader.start_time == datetime(2017, 9, 20, 17, 30, 40, 800000)
        assert self.reader.end_time == datetime(2017, 9, 20, 17, 41, 17, 500000)

    def test_get_dataset(self):
        """Test the get_dataset method."""
        key = make_dataid(name="Rad", calibration="radiance")
        res = self.reader.get_dataset(key, {"info": "info"})
        exp = {"calibration": "radiance",
               "instrument_ID": None,
               "modifiers": (),
               "name": "Rad",
               "observation_type": "Rad",
               "orbital_parameters": {"projection_altitude": 1.0,
                                      "projection_latitude": 0.0,
                                      "projection_longitude": -90.0,
                                      "satellite_nominal_altitude": 35786020.,
                                      "satellite_nominal_latitude": 0.0,
                                      "satellite_nominal_longitude": -89.5,
                                      "yaw_flip": True},
               "orbital_slot": None,
               "platform_name": "GOES-16",
               "platform_shortname": "G16",
               "production_site": None,
               "scan_mode": "M3",
               "scene_abbr": "C",
               "scene_id": None,
               "sensor": "abi",
               "timeline_ID": None,
               "suffix": "custom",
               "units": "W m-2 um-1 sr-1"}

        assert res.attrs == exp
        # we remove any time dimension information
        assert "t" not in res.coords
        assert "t" not in res.dims
        assert "time" not in res.coords
        assert "time" not in res.dims

    @mock.patch("satpy.readers.abi_base.geometry.AreaDefinition")
    def test_get_area_def(self, adef):
        """Test the area generation."""
        self.reader.get_area_def(None)

        assert adef.call_count == 1
        call_args = tuple(adef.call_args)[0]
        assert call_args[3] == {"a": 1.0, "b": 1.0, "h": 1.0,
                                "lon_0": -90.0, "proj": "geos", "sweep": "x", "units": "m"}
        assert call_args[4] == self.reader.ncols
        assert call_args[5] == self.reader.nlines
        np.testing.assert_allclose(call_args[6], (-2, -2, 8, 2))


class Test_NC_ABI_L1B_ir_cal(Test_NC_ABI_L1B_Base):
    """Test the NC_ABI_L1B reader's default IR calibration."""

    def setUp(self):
        """Create fake data for the tests."""
        rad_data = (np.arange(10.).reshape((2, 5)) + 1.) * 50.
        rad_data = (rad_data + 1.) / 0.5
        rad_data = rad_data.astype(np.int16)
        rad = xr.DataArray(
            rad_data,
            dims=("y", "x"),
            attrs={
                "scale_factor": 0.5,
                "add_offset": -1.,
                "_FillValue": 1002,  # last rad_data value
            }
        )
        super(Test_NC_ABI_L1B_ir_cal, self).setUp(rad=rad)

    def test_ir_calibration_attrs(self):
        """Test IR calibrated DataArray attributes."""
        res = self.reader.get_dataset(
            make_dataid(name="C05", calibration="brightness_temperature"), {})

        # make sure the attributes from the file are in the data array
        assert "scale_factor" not in res.attrs
        assert "_FillValue" not in res.attrs
        assert res.attrs["standard_name"] == "toa_brightness_temperature"
        assert res.attrs["long_name"] == "Brightness Temperature"

    def test_clip_negative_radiances_attribute(self):
        """Assert that clip_negative_radiances is set to False."""
        assert not self.reader.clip_negative_radiances

    def test_ir_calibrate(self):
        """Test IR calibration."""
        res = self.reader.get_dataset(
            make_dataid(name="C05", calibration="brightness_temperature"), {})

        expected = np.array([[267.55572248, 305.15576503, 332.37383249, 354.73895301, 374.19710115],
                             [391.68679226, 407.74064808, 422.69329105, 436.77021913, np.nan]])
        assert np.allclose(res.data, expected, equal_nan=True)


class Test_NC_ABI_L1B_clipped_ir_cal(Test_NC_ABI_L1B_Base):
    """Test the NC_ABI_L1B reader's IR calibration (clipping negative radiance)."""

    def setUp(self):
        """Create fake data for the tests."""
        values = np.arange(10.)
        values[0] = -0.0001  # introduce below minimum expected radiance
        rad_data = (values.reshape((2, 5)) + 1.) * 50.
        rad_data = (rad_data + 1.) / 0.5
        rad_data = rad_data.astype(np.int16)
        rad = xr.DataArray(
            rad_data,
            dims=("y", "x"),
            attrs={
                "scale_factor": 0.5,
                "add_offset": -1.,
                "_FillValue": 1002,
            }
        )

        super().setUp(rad=rad, clip_negative_radiances=True)

    def test_clip_negative_radiances_attribute(self):
        """Assert that clip_negative_radiances has been set to True."""
        assert self.reader.clip_negative_radiances

    def test_ir_calibrate(self):
        """Test IR calibration."""
        res = self.reader.get_dataset(
            make_dataid(name="C07", calibration="brightness_temperature"), {})

        clipped_ir = 267.07775531
        expected = np.array([[clipped_ir, 305.15576503, 332.37383249, 354.73895301, 374.19710115],
                             [391.68679226, 407.74064808, 422.69329105, 436.77021913, np.nan]])
        assert np.allclose(res.data, expected, equal_nan=True)

    def test_get_minimum_radiance(self):
        """Test get_minimum_radiance from Rad DataArray."""
        from satpy.readers.abi_l1b import NC_ABI_L1B
        data = xr.DataArray(
               attrs={
                   "scale_factor": 0.5,
                   "add_offset": -1.,
                   "_FillValue": 1002,
               }
        )
        np.testing.assert_allclose(NC_ABI_L1B._get_minimum_radiance(NC_ABI_L1B, data), 0.0)


class Test_NC_ABI_L1B_vis_cal(Test_NC_ABI_L1B_Base):
    """Test the NC_ABI_L1B reader."""

    def setUp(self):
        """Create fake data for the tests."""
        rad_data = (np.arange(10.).reshape((2, 5)) + 1.)
        rad_data = (rad_data + 1.) / 0.5
        rad_data = rad_data.astype(np.int16)
        rad = xr.DataArray(
            rad_data,
            dims=("y", "x"),
            attrs={
                "scale_factor": 0.5,
                "add_offset": -1.,
                "_FillValue": 20,
            }
        )
        super(Test_NC_ABI_L1B_vis_cal, self).setUp(rad=rad)

    def test_vis_calibrate(self):
        """Test VIS calibration."""
        res = self.reader.get_dataset(
            make_dataid(name="C05", calibration="reflectance"), {})

        expected = np.array([[0.15265617, 0.30531234, 0.45796851, 0.61062468, 0.76328085],
                             [0.91593702, 1.06859319, 1.22124936, np.nan, 1.52656171]])
        assert np.allclose(res.data, expected, equal_nan=True)
        assert "scale_factor" not in res.attrs
        assert "_FillValue" not in res.attrs
        assert res.attrs["standard_name"] == "toa_bidirectional_reflectance"
        assert res.attrs["long_name"] == "Bidirectional Reflectance"


class Test_NC_ABI_L1B_raw_cal(Test_NC_ABI_L1B_Base):
    """Test the NC_ABI_L1B reader raw calibration."""

    def setUp(self):
        """Create fake data for the tests."""
        rad_data = (np.arange(10.).reshape((2, 5)) + 1.)
        rad_data = (rad_data + 1.) / 0.5
        rad_data = rad_data.astype(np.int16)
        rad = xr.DataArray(
            rad_data,
            dims=("y", "x"),
            attrs={
                "scale_factor": 0.5,
                "add_offset": -1.,
                "_FillValue": 20,
            }
        )
        super(Test_NC_ABI_L1B_raw_cal, self).setUp(rad=rad)

    def test_raw_calibrate(self):
        """Test RAW calibration."""
        res = self.reader.get_dataset(
            make_dataid(name="C05", calibration="counts"), {})

        # We expect the raw data to be unchanged
        expected = res.data
        assert np.allclose(res.data, expected, equal_nan=True)

        # check for the presence of typical attributes
        assert "scale_factor" in res.attrs
        assert "add_offset" in res.attrs
        assert "_FillValue" in res.attrs
        assert "orbital_parameters" in res.attrs
        assert "platform_shortname" in res.attrs
        assert "scene_id" in res.attrs

        # determine if things match their expected values/types.
        assert res.data.dtype == np.int16
        assert res.attrs["standard_name"] == "counts"
        assert res.attrs["long_name"] == "Raw Counts"


class Test_NC_ABI_L1B_invalid_cal(Test_NC_ABI_L1B_Base):
    """Test the NC_ABI_L1B reader with invalid calibration."""

    def test_invalid_calibration(self):
        """Test detection of invalid calibration values."""
        # Need to use a custom DataID class because the real DataID class is
        # smart enough to detect the invalid calibration before the ABI L1B
        # get_dataset method gets a chance to run.
        class FakeDataID(dict):
            def to_dict(self):
                return self

        did = FakeDataID(name="C05", calibration="invalid", modifiers=())
        with pytest.raises(ValueError, match="Unknown calibration 'invalid'"):
            self.reader.get_dataset(did, {})


class Test_NC_ABI_File(unittest.TestCase):
    """Test file opening."""

    @mock.patch("satpy.readers.abi_base.xr")
    def test_open_dataset(self, _):  # noqa: PT019
        """Test openning a dataset."""
        from satpy.readers.abi_l1b import NC_ABI_L1B

        openable_thing = mock.MagicMock()

        NC_ABI_L1B(openable_thing, {"platform_shortname": "g16"}, None)
        openable_thing.open.assert_called()


class Test_NC_ABI_L1B_H5netcdf(Test_NC_ABI_L1B):
    """Allow h5netcdf peculiarities."""

    def setUp(self):
        """Create fake data for the tests."""
        rad_data = np.int16(50)
        rad = xr.DataArray(
            rad_data,
            attrs={
                "scale_factor": 0.5,
                "add_offset": -1.,
                "_FillValue": np.array([1002]),
                "units": "W m-2 um-1 sr-1",
                "valid_range": (0, 4095),
            }
        )
        super(Test_NC_ABI_L1B_H5netcdf, self).setUp(rad=rad)

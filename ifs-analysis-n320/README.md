# ECMWF IFS Analysis N320 - Beyond Weather Icechunk Zarr

A cloud-native archive of the ECMWF Integrated Forecasting System (IFS) operational analysis, 6-hourly from 2011-01-01 to 2026-09-30, on the native N320 reduced Gaussian grid. It is published by [Beyond Weather](https://beyond-weather.com) through the [Registry of Open Data on AWS](https://registry.opendata.aws/beyond-weather-ecmwf-ifs-analysis/).

- **Tutorial:** [Get to Know a Dataset notebook](get-to-know-a-dataset.ipynb)
- **Bucket:** `s3://beyond-weather-ecmwf-ifs-analysis` (region `us-east-2`), public, no AWS account needed
- **Questions / issues:** https://github.com/Beyond-Weather-Git/open-data-examples/issues

## Overview

| | |
| --- | --- |
| Source | ECMWF IFS operational analysis (`class=od`, `stream=oper`, `type=an`), retrieved from the ECMWF MARS archive |
| Period | 2011-01-01 00 UTC to 2026-09-30 18 UTC |
| Time step | 6 hours (00, 06, 12, 18 UTC), 23,008 timesteps |
| Grid | N320 reduced Gaussian (`GRIB_N=320`), 542,080 points, ~31 km, interpolated by MARS from the operational model resolution |
| Vertical | 18 pressure levels: 1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50, 30, 10, 5, 2 hPa |
| Variables | 6 upper-air, 22 surface, 4 "static" (see data dictionary) |
| Format | Zarr v3 in an [Icechunk](https://icechunk.io) repository (format written with icechunk 2.0) |
| Size | ~1.3 TB compressed (~6.7 TB uncompressed float32) |
| Update frequency | Not currently updated |

## Bucket layout

```
s3://beyond-weather-ecmwf-ifs-analysis/
├── README.md
├── LICENSE.txt
└── data/
    └── ifs-analysis-n320/          # Icechunk repository
        ├── repo
        ├── refs/
        ├── snapshots/
        ├── manifests/
        ├── transactions/
        └── chunks/
```

The objects inside an Icechunk repository are named by content ID and are not meant to be read one by one. Open the repository with the `icechunk` library:

```python
import icechunk as ic
import xarray as xr

storage = ic.s3_storage(bucket="beyond-weather-ecmwf-ifs-analysis", prefix="data/ifs-analysis-n320",
                        region="us-east-2", anonymous=True)
session = ic.Repository.open(storage).readonly_session(branch="main")
ds = xr.open_zarr(session.store, chunks={})
```

### Opening the data

Two things are needed to read the data correctly: the `icechunk` library (the repository is not plain Zarr) and a Zarr v3 capable `zarr` (>= 3) with `xarray`. Install them with `pip install icechunk "zarr>=3" xarray dask`.

**Decompression is automatic.** Each chunk is Blosc/Zstandard compressed, and the Blosc codec is recorded in the Zarr v3 array metadata. `zarr` reads that metadata and decodes every chunk on access, so you never call a decompressor yourself. Do not read the objects under `chunks/` directly. They are Icechunk chunk objects, not Zarr keys.

What you do need to know is what is *not* undone on read:

- **Bit rounding is permanent.** Values come back as float32, but the discarded mantissa bits are zero. The kept precision per variable is in the `bwdl_keepbits` attribute.
- **Open lazily.** Pass `chunks={}` to `xr.open_zarr` so each stored chunk becomes one dask chunk and nothing is downloaded until you call `.load()` or `.compute()`. One chunk is one timestep, so select time before loading.
- **Missing values are NaN.** `sea_surface_temperature` and `sea_ice_cover` are NaN over land. Mask with `land_sea_mask` if you need to.

```python
import icechunk as ic
import xarray as xr

storage = ic.s3_storage(bucket="beyond-weather-ecmwf-ifs-analysis", prefix="data/ifs-analysis-n320",
                        region="us-east-2", anonymous=True)
repo = ic.Repository.open(storage)
session = repo.readonly_session(branch="main")
ds = xr.open_zarr(session.store, chunks={})

# Nothing is downloaded until .load(). Then zarr fetches and decompresses one stored chunk: the
# whole timestep for this variable, i.e. all 18 pressure levels (18 x 542,080 values). xarray then
# keeps only the 850 hPa level you asked for, so the result has 542,080 values.
t850 = ds["temperature"].sel(time="2024-07-15T12:00", pressure_level=850).load()
```

To see both steps, inspect the codec zarr applies on read and check the rounding on the values you just loaded:

```python
import numpy as np

temperature = ds["temperature"]

# Decompression: the codec stored in the array metadata, which zarr runs for you on every chunk read
print("Codec:", temperature.encoding["compressors"])

# Bit rounding: the mantissa bits kept (out of 23 for float32) and what was rounded away
keepbits = temperature.attrs["bwdl_keepbits"]
bits = t850.values.view(np.uint32)
print("keepbits:", keepbits)
print("Any non-zero bit below the kept ones:", bool((bits & ((1 << (23 - keepbits)) - 1)).any()))
```

`bwdl_keepbits` is not used to read the data. It only documents how many mantissa bits were kept when the data was written. The check above shows it holds: the bits below it are all zero.

#### From the Earthmover Marketplace

The dataset is also listed on the [Earthmover Marketplace](https://docs.earthmover.io/marketplace/data-users). The repository is the same Icechunk repository, so the decoding behaviour above is identical. You open it through Arraylake instead of S3. This needs a free Earthmover account and `arraylake >= 0.26.1` (`pip install --upgrade arraylake`). See the Earthmover docs for how to authenticate.

```python
import arraylake as al
import xarray as xr

client = al.Client()
repo = client.get_repo("beyond-weather/ecmwf-ifs-analysis")
session = repo.readonly_session(branch="main")
ds = xr.open_zarr(session.store, chunks={})
```

### Versioning

Every change to the dataset is an Icechunk commit on the `main` branch. To make an analysis reproducible, record `session.snapshot_id` and later open `repo.readonly_session(snapshot_id=...)`.

## Data model

| Dimension / coordinate | Size | Description |
| --- | --- | --- |
| `time` | 23,008 | Analysis valid time (`datetime64`, UTC) |
| `pressure_level` | 18 | Pressure in hPa, ordered 1000 → 2 |
| `point` | 542,080 | Index of the grid point on the N320 reduced Gaussian grid |
| `latitude(point)` | 542,080 | Latitude of each point (degrees north), 640 rows from 89.78°N to 89.78°S |
| `longitude(point)` | 542,080 | Longitude of each point (degrees east, 0 to 360), eastward from 0° within each row |

Points are in standard GRIB order: rows of constant latitude from north to south, each running eastward from 0°E. The number of points per row (`GRIB_pl` attribute) goes from 18 at the poles to 1,280 near the equator.

### Chunking and compression

- One chunk per timestep and variable: `(1, 542080)` for surface fields, `(1, 18, 542080)` for upper-air fields.
- Values are float32, **bit-rounded** to the number of mantissa bits in each variable's `bwdl_keepbits` attribute, then compressed with Blosc (Zstandard, level 9, byte shuffle). Bit rounding is lossy. The kept precision is chosen to stay well below analysis uncertainty, but the values are not bit-identical to the GRIB data in MARS.

## Data dictionary

All variables carry their original GRIB metadata as attributes (`GRIB_shortName`, `GRIB_paramId`, `GRIB_name`, `units`, ...). See the [ECMWF parameter database](https://codes.ecmwf.int/grib/param-db/) for full definitions.

### Upper-air variables, dims `(time, pressure_level, point)`

| Variable | GRIB short name | paramId | Units | keepbits |
| --- | --- | --- | --- | --- |
| `geopotential` | z | 129 | m² s⁻² | 14 |
| `temperature` | t | 130 | K | 12 |
| `specific_humidity` | q | 133 | kg kg⁻¹ | 9 |
| `u_component_of_wind` | u | 131 | m s⁻¹ | 6 |
| `v_component_of_wind` | v | 132 | m s⁻¹ | 5 |
| `vertical_velocity` | w | 135 | Pa s⁻¹ | 4 |

### Surface variables, dims `(time, point)`

| Variable | GRIB short name | paramId | Units | keepbits |
| --- | --- | --- | --- | --- |
| `surface_pressure` | sp | 134 | Pa | 12 |
| `mean_sea_level_pressure` | msl | 151 | Pa | 12 |
| `skin_temperature` | skt | 235 | K | 11 |
| `2m_temperature` | 2t | 167 | K | 11 |
| `2m_dewpoint_temperature` | 2d | 168 | K | 11 |
| `10m_u_component_of_wind` | 10u | 165 | m s⁻¹ | 5 |
| `10m_v_component_of_wind` | 10v | 166 | m s⁻¹ | 5 |
| `100m_u_component_of_wind` | 100u | 228246 | m s⁻¹ | 6 |
| `100m_v_component_of_wind` | 100v | 228247 | m s⁻¹ | 5 |
| `total_column_water` | tcw | 136 | kg m⁻² | 7 |
| `total_column_water_vapour` | tcwv | 137 | kg m⁻² | 7 |
| `total_cloud_cover` | tcc | 164 | 0-1 | 5 |
| `high_cloud_cover` | hcc | 188 | 0-1 | 5 |
| `medium_cloud_cover` | mcc | 187 | 0-1 | 4 |
| `low_cloud_cover` | lcc | 186 | 0-1 | 5 |
| `soil_temperature_level_1` | stl1 | 139 | K | 11 |
| `soil_temperature_level_2` | stl2 | 170 | K | 12 |
| `volumetric_soil_water_layer_1` | swvl1 | 39 | m³ m⁻³ | 10 |
| `volumetric_soil_water_layer_2` | swvl2 | 40 | m³ m⁻³ | 10 |
| `sea_surface_temperature` | sst | 34 | K | 11 |
| `sea_ice_cover` | ci | 31 | 0-1 | 3 |
| `snow_depth` | sd | 141 | m of water equivalent | 10 |

`sea_surface_temperature` and `sea_ice_cover` are only defined over sea and are NaN over land.

### "Static" variables, dims `(time, point)`

| Variable | GRIB short name | paramId | Units | keepbits |
| --- | --- | --- | --- | --- |
| `land_sea_mask` | lsm | 172 | 0-1 | 4 |
| `orography` | z (surface geopotential) | 129 | m² s⁻² | 4 |
| `standard_deviation_of_orography` | sdor | 160 | m | 3 |
| `slope_of_sub_gridscale_orography` | slor | 163 | - | 4 |

These fields are stored at every timestep because they change when ECMWF upgrades the IFS. Within 2011-2026 they change at the first analysis of IFS cycles 41r1 (2015-05-12 06 UTC), 41r2 (2016-03-08 06 UTC) and 48r1 (2023-06-27 06 UTC). Divide `orography` by g = 9.80665 m s⁻² to get height in metres.

## Known caveats

- **Not a reanalysis.** Each analysis comes from the IFS version that was operational at the time. Model and data assimilation upgrades (see the [IFS cycle history](https://confluence.ecmwf.int/display/FCST/Changes+to+the+forecasting+system)) can cause discontinuities. For climate trend studies, use ERA5.
- **Lossy compression.** See "Chunking and compression" above.
- **Interpolated grid.** The N320 grid is not the native resolution of the operational model (TL1279 until March 2016, TCo1279 after). MARS interpolates the fields to N320.

## Licence and attribution

The data is published under the [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) licence, following the [ECMWF terms of use](https://apps.ecmwf.int/datasets/licences/general/). The full text, including the list of modifications, is in [`LICENSE.txt`](LICENSE.txt). The same file is at the top level of the bucket.

- **Copyright statement:** Copyright © 2011-2026 European Centre for Medium-Range Weather Forecasts (ECMWF).
- **Source:** www.ecmwf.int
- **Licence statement:** This data is published under a Creative Commons Attribution 4.0 International (CC BY 4.0) licence. https://creativecommons.org/licenses/by/4.0/
- **Disclaimer:** ECMWF does not accept any liability whatsoever for any error or omission in the data, their availability, or for any loss or damage arising from their use.
- **Beyond Weather's disclaimer:** Beyond Weather provides its modifications and hosting as-is and as-available, without warranty of any kind, to the fullest extent permitted by law. Errors or omissions introduced by Beyond Weather's processing (for example bit-rounding or conversion) are not covered by ECMWF's disclaimer above.
- **No endorsement:** This modified dataset is not endorsed by, sponsored by or affiliated with ECMWF.
- **Modifications:** Beyond Weather selected the variables and pressure levels, converted the data from GRIB to Icechunk Zarr, renamed the variables, and bit-rounded the values (lossy).

If you build a service on this data, ECMWF asks for the copyright statement "This service is based on data and products of the European Centre for Medium-Range Weather Forecasts (ECMWF)" instead.

When you use the data, please cite it as:

> ECMWF IFS Analysis N320 - Beyond Weather Icechunk Zarr, accessed [DATE] at https://registry.opendata.aws/beyond-weather-ecmwf-ifs-analysis/

## How this dataset was produced

The data was retrieved from MARS one calendar month at a time per level type (`levtype=sfc` and `levtype=pl`), at `grid=N320`, for 00/06/12/18 UTC. It was decoded with cfgrib, renamed to the long variable names above, checked for completeness and data integrity (for example, no identical consecutive timesteps), bit-rounded, and appended to the Icechunk repo.

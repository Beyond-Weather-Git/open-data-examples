"""Builds get-to-know-a-dataset.ipynb from the AWS Open Data template structure.

Kept as a script so the notebook diff stays reviewable; run it after editing,
then commit the regenerated notebook with outputs cleared.
"""

import json
from pathlib import Path


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n")}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.strip("\n"),
    }


CELLS = [
    md(r"""
# Get to Know a Dataset: ECMWF IFS Analysis N320 - Beyond Weather Icechunk Zarr

This notebook serves as a guided tour of the [ECMWF IFS Analysis N320 - Beyond Weather Icechunk Zarr](https://registry.opendata.aws/beyond-weather-ecmwf-ifs-analysis/) dataset, published by [Beyond Weather](https://beyond-weather.com). More usage examples, tutorials, and documentation for this dataset and others can be found at the [Registry of Open Data on AWS](https://registry.opendata.aws/).

The dataset contains the operational analysis of ECMWF's Integrated Forecasting System (IFS), retrieved from the ECMWF MARS archive every 6 hours (00, 06, 12 and 18 UTC) from 2011-01-01 to 2024-12-31. It is stored on the native N320 reduced Gaussian grid (542,080 points, roughly 31 km spacing) with 18 pressure levels, as a single cloud-native [Icechunk](https://icechunk.io) / [Zarr v3](https://zarr.dev) store. The variable set matches the inputs of data-driven weather models such as ECMWF's [AIFS](https://www.ecmwf.int/en/forecasts/dataset/aifs-machine-learning-data), so the data can be used to train, fine-tune, initialise and verify them.
"""),
    md(r"""
### Q: How have you organized your dataset? Help us understand the key prefix structure of your S3 bucket.

At the top level of the `beyond-weather-ecmwf-ifs-analysis` bucket you will find:

1. `README.md`: a short description of the dataset with links to the full documentation
2. `LICENSE.txt`: the licence and attribution requirements
3. `data/`: one prefix per dataset. Today this holds a single dataset, `data/ifs-analysis-n320/`. Other grids or variable sets may be added later as siblings.

Each dataset prefix is an **Icechunk repository**. Icechunk is a transactional storage engine for Zarr: it stores the Zarr chunks plus manifests and snapshots that record which chunks belong to which version of the data. Inside the repository you will see the prefixes `chunks/`, `manifests/`, `snapshots/`, `transactions/` and `refs/`, plus a `repo` object. Object names under `chunks/` are content IDs, not human-readable paths. **Do not read these objects directly.** Open the repository with the `icechunk` Python library and use the Zarr/xarray view it gives you (shown below).

Full documentation, including a data dictionary, is at: https://github.com/Beyond-Weather-Git/open-data-examples/blob/main/ifs-analysis-n320/README.md
"""),
    code(r"""
# This notebook requires the following additional libraries
# (please install using the preferred method for your environment, e.g. pip, conda):
#
# icechunk >= 2.0
# zarr >= 3.1
# xarray >= 2025.6
# dask >= 2025.5
# numpy >= 2.0
# matplotlib >= 3.10
# boto3 >= 1.38

import boto3
import icechunk as ic
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from botocore import UNSIGNED
from botocore.config import Config
"""),
    md(r"""
First we define where the dataset lives and list the top level of the bucket. The bucket is public, so requests do not need to be signed and no AWS account is needed. The data is stored in `us-east-2`. Running your compute in that region is fastest.
"""),
    code(r"""
# Location of the S3 bucket for this dataset
BUCKET = "beyond-weather-ecmwf-ifs-analysis"
REGION = "us-east-2"
PREFIX = "data/ifs-analysis-n320"

# Public bucket: use unsigned requests
s3 = boto3.client("s3", region_name=REGION, config=Config(signature_version=UNSIGNED))

response = s3.list_objects_v2(Bucket=BUCKET, Delimiter="/")
for item in response.get("Contents", []):
    print(item["Key"])
for item in response.get("CommonPrefixes", []):
    print(item["Prefix"])
"""),
    md(r"""
Looking inside the dataset prefix shows the Icechunk repository layout described above.
"""),
    code(r"""
response = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{PREFIX}/", Delimiter="/")
for item in response.get("Contents", []):
    print(item["Key"])
for item in response.get("CommonPrefixes", []):
    print(item["Prefix"])
"""),
    md(r"""
### Q: What data formats are present in your dataset? What kinds of data are stored using these formats? Can you give any advice for how you work with these data formats?

The data is a **Zarr v3** store managed by **Icechunk**.

- **Zarr** is a chunked, compressed, N-dimensional array format designed for cloud object storage. Readers fetch only the chunks they need, using parallel HTTP range requests. xarray, dask and most of the Pangeo ecosystem can read it.
- **Icechunk** adds version control and ACID transactions on top of Zarr. Each update to the dataset (for example, appending new dates) is committed as an immutable *snapshot*. You can open the latest version on the `main` branch, or pin your analysis to a specific snapshot ID so it stays reproducible. Icechunk needs the `icechunk` Python package. Plain `zarr.open("s3://...")` will not work.

Why we chose this format: the training and verification pipelines of data-driven weather models read random timesteps of the full global state. One Zarr chunk per timestep and variable gives every read a single, predictable object to fetch, and Icechunk lets us extend the archive in place without readers ever seeing a half-written update.

Details specific to this dataset:

- **Grid.** Values are stored on ECMWF's **N320 reduced Gaussian grid** as a flat `point` dimension of 542,080 points, not as a lat/lon rectangle. The `latitude` and `longitude` coordinates give each point's location. Points run north to south in rows of constant latitude (640 rows), and each row goes eastward from 0°E. The number of points per row shrinks towards the poles, so grid spacing stays roughly uniform (~31 km). To get a regular lat/lon grid, use a regridding tool such as [earthkit-regrid](https://github.com/ecmwf/earthkit-regrid). Many analyses (zonal means, area averages, ML models on graphs or meshes) can work on the native points directly.
- **Dimensions.** `time` (6-hourly, 20,456 steps), `pressure_level` (18 levels from 1000 to 2 hPa, for upper-air variables) and `point`.
- **Chunking.** One chunk holds one timestep of one variable over the whole globe (`(1, 542080)` for surface fields, `(1, 18, 542080)` for upper-air fields). Reading global fields at a few times is cheap. Reading a long time series at a single location means touching one chunk per timestep. In that case, read in parallel with dask and run your code close to the data (in `us-east-2`).
- **Compression.** Chunks are compressed with Blosc/Zstandard after **bit rounding**. Each variable keeps only the number of mantissa bits listed in its `bwdl_keepbits` attribute, chosen to stay well below the analysis uncertainty. The values are therefore *lossy* float32 approximations of the GRIB values from MARS.
- **"Static" fields.** `land_sea_mask`, `orography`, `standard_deviation_of_orography` and `slope_of_sub_gridscale_orography` are stored at every timestep, because ECMWF changes them when the IFS model is upgraded (see the question section below).
- **Metadata.** Each variable keeps the GRIB metadata from MARS as attributes (`GRIB_shortName`, `GRIB_paramId`, `units`, ...), so you can look it up in the [ECMWF parameter database](https://codes.ecmwf.int/grib/param-db/).

Useful AWS services: run notebooks close to the data on [Amazon SageMaker AI](https://aws.amazon.com/sagemaker-ai/) or [Amazon EC2](https://aws.amazon.com/ec2/) in `us-east-2`. Scale out with dask on EC2/EKS, or with [Coiled](https://www.coiled.io/).
"""),
    md(r"""
### Q: Can you show us an example of downloading and loading data from your dataset?

We open the Icechunk repository anonymously, start a read-only session on the `main` branch, and hand its Zarr store to xarray. This step only reads metadata. Data is loaded lazily when you ask for it.
"""),
    code(r"""
storage = ic.s3_storage(bucket=BUCKET, prefix=PREFIX, region=REGION, anonymous=True)
repo = ic.Repository.open(storage)
session = repo.readonly_session(branch="main")

# Note the snapshot id if you want to come back to exactly this version later:
# repo.readonly_session(snapshot_id=...)
print("Snapshot:", session.snapshot_id)

ds = xr.open_zarr(session.store, consolidated=False, chunks={})
ds
"""),
    md(r"""
Every variable carries its GRIB metadata and the number of mantissa bits kept after bit rounding. Here are a few of them as a small data dictionary:
"""),
    code(r"""
for name in ["2m_temperature", "mean_sea_level_pressure", "temperature", "specific_humidity", "orography"]:
    attrs = ds[name].attrs
    print(
        f"{name:28s} shortName={attrs['GRIB_shortName']:4s} paramId={attrs['GRIB_paramId']:<7} "
        f"units={attrs['units']:12s} level={attrs['GRIB_typeOfLevel']:20s} keepbits={attrs['bwdl_keepbits']}"
    )
"""),
    md(r"""
Now we load real data: the 2 m temperature analysis for one time, which downloads a single chunk. Because the grid is a flat list of points, the result is a 1-D array with one value per grid point.
"""),
    code(r"""
t2m = ds["2m_temperature"].sel(time="2024-07-15T12:00").load()
print(t2m.sizes)
print(f"min {float(t2m.min()):.1f} K, max {float(t2m.max()):.1f} K, global mean {float(t2m.mean()):.1f} K (unweighted)")
"""),
    md(r"""
Grid points are spread almost evenly over the sphere, so a plain mean over `point` is already close to an area-weighted mean. You can also see the reduced Gaussian structure directly: there are 640 distinct latitudes, and polar rows have far fewer points than rows near the equator.
"""),
    code(r"""
latitude = ds["latitude"].values
longitude = ds["longitude"].values
row_latitudes, points_per_row = np.unique(latitude, return_counts=True)
print("number of latitude rows:", len(row_latitudes))
print("points in the northernmost row:", points_per_row[-1])
print("points in a row next to the equator:", points_per_row[len(points_per_row) // 2])
"""),
    md(r"""
### Q: A picture is worth a thousand words. Show us a visual (or several!) from your dataset that either illustrates something informative about your dataset, or that you think might excite someone to dig in further.

First, a global map of the 2 m temperature analysis we just loaded. We plot each grid point as a tiny marker, so no regridding is needed.
"""),
    code(r"""
# Shift longitudes from [0, 360) to [-180, 180) for a Greenwich-centred map
lon_centred = ((longitude + 180) % 360) - 180

fig, ax = plt.subplots(figsize=(14, 7), dpi=100)
scatter = ax.scatter(lon_centred, latitude, c=t2m.values - 273.15, s=0.3, cmap="RdYlBu_r",
                     vmin=-40, vmax=45, rasterized=True)
fig.colorbar(scatter, ax=ax, label="2 m temperature (°C)", shrink=0.8)
ax.set(xlim=(-180, 180), ylim=(-90, 90), xlabel="longitude", ylabel="latitude",
       title="IFS operational analysis, 2 m temperature, 2024-07-15 12 UTC (N320, 542,080 points)")
ax.set_aspect("equal")
plt.show()
"""),
    md(r"""
Second, a zonal-mean cross-section of temperature and zonal wind, a classic view of the atmosphere's structure. On a reduced Gaussian grid the zonal mean is trivial: every point in a row shares the same latitude, so we group by latitude. The plot shows the troposphere, the cold tropical tropopause, and the subtropical jets in the summer (northern) and winter (southern) hemispheres.
"""),
    code(r"""
when = "2024-07-15T12:00"
temperature = ds["temperature"].sel(time=when).load()
u_wind = ds["u_component_of_wind"].sel(time=when).load()

zonal_t = temperature.groupby("latitude").mean()
zonal_u = u_wind.groupby("latitude").mean()

fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
mesh = ax.pcolormesh(zonal_t.latitude, zonal_t.pressure_level, zonal_t.values - 273.15,
                     cmap="RdYlBu_r", shading="nearest")
contours = ax.contour(zonal_u.latitude, zonal_u.pressure_level, zonal_u.values,
                      levels=[-30, -20, -10, 10, 20, 30, 40, 50], colors="black", linewidths=0.8)
ax.clabel(contours, fmt="%d m/s", fontsize=8)
fig.colorbar(mesh, ax=ax, label="zonal-mean temperature (°C)")
ax.set_yscale("log")
ax.set_ylim(1000, 2)
ax.set_yticks([1000, 850, 500, 250, 100, 50, 10, 2], labels=["1000", "850", "500", "250", "100", "50", "10", "2"])
ax.set(xlabel="latitude", ylabel="pressure (hPa)",
       title=f"Zonal-mean temperature (colours) and zonal wind (contours), {when} UTC")
plt.show()
"""),
    md(r"""
### Q: What is one question that you have answered using these data? Can you show us how you came to that answer?

At Beyond Weather we use this archive to train and fine-tune data-driven forecast models (AIFS-style graph neural networks) on the native N320 grid. Unlike a reanalysis such as ERA5, an *operational* analysis is produced by whatever IFS version was running at the time. ECMWF upgrades the model several times a year. Some upgrades change the analysis itself, and some even change the "static" surface description of the planet. A model trained on 2011-2024 sees all of these versions mixed together, so one of the first questions we had to answer was:

**When did the underlying model change the static fields in this archive, and where?**

We can answer this cheaply. Load the orography (surface geopotential) and land-sea mask every 28 days, find the intervals where they change, then narrow each change down to the exact 6-hour step.
"""),
    code(r"""
coarse_step = 28 * 4  # 28 days of 6-hourly steps
orography = ds["orography"]
coarse = orography.isel(time=slice(None, None, coarse_step)).load()
changed = (np.abs(coarse.diff("time")).max("point") > 0).values

change_times = []
for i in np.flatnonzero(changed):
    # Narrow down to the exact step between two coarse samples
    window = orography.isel(time=slice(i * coarse_step, (i + 1) * coarse_step + 1)).load()
    fine = np.flatnonzero((np.abs(window.diff("time")).max("point") > 0).values)
    for j in fine:
        change_times.append(window.time.values[j + 1])

for change_time in change_times:
    print("static fields change at", np.datetime_as_string(change_time, unit="h"))
"""),
    md(r"""
These dates match three IFS cycle upgrades documented by ECMWF in its [IFS cycle change history](https://confluence.ecmwf.int/display/FCST/Changes+to+the+forecasting+system):

| Change in the data | IFS cycle | Notes |
| --- | --- | --- |
| May 2015 | 41r1 | land-sea mask and orography change |
| March 2016 | 41r2 | horizontal resolution upgrade to TCo1279 (~9 km): the orography and land-sea mask interpolated to N320 change |
| June 2023 | 48r1 | land-sea mask and orography change |

Let's see *where* the land-sea mask changed in the most recent upgrade:
"""),
    code(r"""
last_change = change_times[-1]
before = ds["land_sea_mask"].sel(time=last_change - np.timedelta64(6, "h")).load()
after = ds["land_sea_mask"].sel(time=last_change).load()
difference = (after - before).values
changed_points = np.abs(difference) > 0.01
print(f"{changed_points.sum():,} of {difference.size:,} points changed their land fraction")

fig, ax = plt.subplots(figsize=(14, 7), dpi=100)
# Background: land in light grey, sea in white
ax.scatter(lon_centred, latitude, c=after.values, s=0.3, cmap="Greys", vmin=0, vmax=4, rasterized=True)
scatter = ax.scatter(lon_centred[changed_points], latitude[changed_points], c=difference[changed_points],
                     s=1.5, cmap="BrBG", vmin=-1, vmax=1, rasterized=True)
fig.colorbar(scatter, ax=ax, label="change in land fraction (after - before)", shrink=0.8)
ax.set(xlim=(-180, 180), ylim=(-90, 90), xlabel="longitude", ylabel="latitude",
       title=f"Land-sea mask change at {np.datetime_as_string(last_change, unit='h')} UTC (IFS cycle 48r1)")
ax.set_aspect("equal")
plt.show()
"""),
    md(r"""
Most changes are along coastlines, at lakes and islands, and along the edges of the Antarctic ice shelves and Greenland. These are exactly the places where a model that learned 2011-2023 coastlines then sees a different surface in late 2023. This is why the static fields are stored at every timestep: when training or verifying a model, use the static fields *from the same timestep* as the dynamic fields rather than one fixed mask, and treat cycle-change dates as possible breakpoints.
"""),
    md(r"""
### Q: What is one unanswered question that you think could be answered using these data? Do you have any recommendations or advice for someone wanting to answer this question?

**How much of the skill of a data-driven forecast model comes from its training data, and could a model fine-tuned on this native-resolution operational analysis beat one trained on ERA5?**

Most open machine-learning weather models are pre-trained on ERA5 (0.25°, a frozen 2016 IFS version) and then fine-tuned on recent operational analyses. This archive offers 14 years of operational analysis at roughly 31 km on its native grid, with 6 years more than many fine-tuning sets. That allows a controlled experiment: fine-tune the same pre-trained model on (a) the last few years only and (b) the full 2011-2024 archive, then compare both against held-out 2024 analyses. A second open question is whether the IFS cycle changes found above leave a measurable trace in model errors, and whether conditioning a model on the cycle (or on a "cycle embedding") removes it.

Recommendations:

- Start from an openly available pre-trained model, for example with ECMWF's [Anemoi](https://anemoi.readthedocs.io) framework, which works natively with reduced Gaussian grids. The variables in this dataset follow the AIFS input set.
- Hold out a whole year (e.g. 2024) for verification. Consecutive 6-hourly analyses are highly correlated, so random splits overestimate skill.
- Use the timestep's own static fields (see above), and consider marking the cycle-change dates as features or as split boundaries.
- Work in `us-east-2` and stream batches with dask/xarray directly from the Icechunk store. One chunk per timestep and variable makes random-access training reads efficient.

We would love to hear about your results. Please open an issue on our [examples repository](https://github.com/Beyond-Weather-Git/open-data-examples/issues).
"""),
    md(r"""
### Data licence and attribution

Copyright © 2011-2024 European Centre for Medium-Range Weather Forecasts (ECMWF). Source: www.ecmwf.int. This data is published under a [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) licence, following the [ECMWF terms of use](https://apps.ecmwf.int/datasets/licences/general/). ECMWF does not accept any liability whatsoever for any error or omission in the data, their availability, or for any loss or damage arising from their use.

Beyond Weather modified the data: it selected the variables and levels, converted them from GRIB to Icechunk Zarr, renamed the variables, and bit-rounded the values. See [`LICENSE.txt`](https://beyond-weather-ecmwf-ifs-analysis.s3.us-east-2.amazonaws.com/LICENSE.txt) for the full text. If you use or redistribute the data, credit ECMWF with this wording and state any further changes you make.
"""),
]


def main() -> None:
    notebook = {
        "cells": CELLS,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    for index, cell in enumerate(notebook["cells"]):
        cell["id"] = f"cell-{index:02d}"
    target = Path(__file__).with_name("get-to-know-a-dataset.ipynb")
    target.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()

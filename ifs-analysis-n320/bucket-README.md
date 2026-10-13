# ECMWF IFS Analysis N320 - Beyond Weather Icechunk Zarr

The ECMWF Integrated Forecasting System (IFS) operational analysis, 6-hourly from 2011-01-01 to 2026-09-30, on the native N320 reduced Gaussian grid (542,080 points, ~31 km) with 18 pressure levels. Published by [Beyond Weather](https://beyond-weather.com) through the [Registry of Open Data on AWS](https://registry.opendata.aws/beyond-weather-ecmwf-ifs-analysis/).

## Contents

- `README.md`: this file
- `LICENSE.txt`: the licence and attribution requirements
- `data.zarr/`: the dataset, a Zarr v3 store in an [Icechunk](https://icechunk.io) repository
- `index.html`: a page for browsing the bucket in a web browser

The objects under `data.zarr/` are named by content ID. Do not read them one by one. Open the repository with the `icechunk` library (`pip install icechunk "zarr>=3" xarray dask`):

```python
import icechunk as ic
import xarray as xr

storage = ic.s3_storage(bucket="beyond-weather-ecmwf-ifs-analysis", prefix="data.zarr",
                        region="us-east-2", anonymous=True)
session = ic.Repository.open(storage).readonly_session(branch="main")
ds = xr.open_zarr(session.store, chunks={})
```

## Documentation

- Full documentation and data dictionary: https://github.com/Beyond-Weather-Git/open-data-examples/blob/main/ifs-analysis-n320/README.md
- Tutorial notebook: https://github.com/Beyond-Weather-Git/open-data-examples/blob/main/ifs-analysis-n320/get-to-know-a-dataset.ipynb
- Questions and issues: https://github.com/Beyond-Weather-Git/open-data-examples/issues

## Licence

Copyright © 2011-2026 European Centre for Medium-Range Weather Forecasts (ECMWF). Published under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), following the [ECMWF terms of use](https://apps.ecmwf.int/datasets/licences/general/). The data was modified by Beyond Weather and is not endorsed by ECMWF. See `LICENSE.txt` for the full text, the list of modifications and the disclaimers.

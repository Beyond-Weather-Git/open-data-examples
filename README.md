# Beyond Weather open data examples

Examples and documentation for Beyond Weather datasets on the [Registry of Open Data on AWS](https://registry.opendata.aws/).

| Dataset | Documentation | Tutorial |
| --- | --- | --- |
| ECMWF IFS Analysis N320 - Beyond Weather Icechunk Zarr | [README](ifs-analysis-n320/README.md) | [Get to Know a Dataset](ifs-analysis-n320/get-to-know-a-dataset.ipynb) |

`registry/` holds the draft Registry of Open Data entry. It is submitted by pull request to
[awslabs/open-data-registry](https://github.com/awslabs/open-data-registry) as `datasets/beyond-weather-ecmwf-ifs-analysis.yaml`.

To regenerate the tutorial notebook after editing `ifs-analysis-n320/build_notebook.py`, run
`python ifs-analysis-n320/build_notebook.py`. The notebook is committed with outputs cleared.

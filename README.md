# ecobalyse-data

Produce the input data required to make the [Ecobalyse](https://github.com/MTES-MCT/ecobalyse) application work. It uses LCA softwares (Brightway and Simapro) to get LCIA data from multiple databases (Ecoinvent, WFLDB, Agribalyse, …) and to produce JSON files required for [Ecobalyse](https://github.com/MTES-MCT/ecobalyse) to work.


## Pre-requisites

- [NodeJS](https://nodejs.org/fr/) 14+ and `npm` to format JSON files
- [uv](https://docs.astral.sh/uv/) to manage Python installs


## Configuration

### Environment variables

You need the following environment variables to be setup (you can use an `.env` file for that, see `.env.sample`):

- `ECOBALYSE_OUTPUT_DIR`: path were the files will be exported, usually the public repository `/home/user/ecobalyse/public/data`. A local copy of the files will be kept by default in the `public/data/` folder.

- `ECOBALYSE_LOCAL_EXPORT`: set it to `false` if you don’t want files to be exported in the local `public/data/` folder (`true` by default)
- `ECOBALYSE_PLOT_EXPORT`: if you want to generate graphs with differences between Simapro and Brightway in `graphs/` when running the export (`true` by default)
- `PYTHONPATH`: if you want to use the Python scripts directly without using `npm` be sure to add the current directory to your python PATH (`export PYTHONPATH=.`)
- `DB_FILES_DIR`: path where the input databases files will be stored

[dynaconf](https://www.dynaconf.com/) is used to manage the configuration. Every variable in `settings.toml` can be overridden following [12-factor application guide](https://12factor.net/config) using the `ECOBALYSE_` prefix. For example, if you want to deactivate the local export in `public/data/` you can set `ECOBALYSE_LOCAL_EXPORT=False`.


By default, Brightway stores data in `~/.local/share/Brightway3/`. It is highly recommended to setup the environment variable `BRIGHTWAY2_DIR` in order to chose where to put the data (the directory needs to exist).

### Input files and databases

You need to have the databases in the CSV Simapro export format and you need to compress the files using Zip. By default the script will look for the files in `../dbfiles/`, you can override this by setting the `DB_FILES_DIR` environment variable.

#### Food

- AGRIBALYSE31 = "AGB3.1.1.20230306.CSV.zip"  # Agribalyse 3.1
- GINKO = "CSV_369p_et_298chapeaux_final.csv.zip"  # additional organic processes
- PASTOECO = "pastoeco.CSV.zip"
- CTCPA = "Export emballages_PACK AGB_CTCPA.CSV.zip"
- WFLDB = "WFLDB.CSV.zip"

#### Textile/Ecoinvent

- EI391 = "Ecoinvent3.9.1.CSV.zip"
- WOOL = "wool.CSV.zip"

#### Method

- EF 3.1: "Environmental Footprint 3.1 (adapted) patch wtu.CSV.zip"

## Running

To import all databases:

    npm run import:all

To export all the JSON files:

    npm run export:all


## Jupyter

To start `jupyter` :

    uv run jupyter lab

### Brightway explorer

In a Jupyter notebook, enter `import notebooks.explore` and then validate with `shift-Enter`.

### Ingredients editor

In a Jupyter notebook, enter `import notebooks.ingredients` and then validate with `shift-Enter`.

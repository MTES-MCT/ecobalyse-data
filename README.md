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

- AGRIBALYSE = "AGB32_final.CSV.zip"  # Agribalyse 3.2
- GINKO = "CSV_369p_et_298chapeaux_final.csv.zip"  # additional organic processes
- PASTOECO = "pastoeco.CSV.zip"
- CTCPA = "Export emballages_PACK AGB_CTCPA.CSV.zip"
- WFLDB = "WFLDB.CSV.zip"

#### Textile/Ecoinvent

- EI391 = "Ecoinvent3.9.1.CSV.zip"
- WOOL = "wool.CSV.zip"

#### Method

- EF 3.1: "Environmental Footprint 3.1 (adapted).1.0.CSV.zip"

## Description of the process

### Importing LCA databases

The first step after installation is to import LCA databases into Brightway
with:

    npm run import:all

All these files are SimaPro-specific CSV files: Agribalyse provided by ADEME,
Ecoinvent exported from SimaPro, other databases provided by third parties,
and the LCIA method `EF 3.1`.

Each file lands in a different Brightway CLA database:

- Agribalyse 3.2
- PastoEco
- Ginko
- CTCPA
- WFLDB
- Ecoinvent 3.9.1
- Woolmark

And `EF 3.1` lands besides other methods of Brightway as:

- Environmental Footprint 3.1 (adapted) patch wtu

### Adding custom processes

Additional LCA processes can be added by defining what you want in a specific
JSON file called `activities_to_create.json` at the root of the repository.
This file currently supports two ways of creating a process: either
`from_scratch` or `from_existing`. All the new processes end-up in another
database called `Ecobalyse`.

The process creation takes place at the end of the import process and is
replayed each time. This mean you can modify the file and relaunch the import
process seceral times and check the result quickly.

#### Creating an LCA process from scratch

The JSON fields are self-explanatory. Here is an example of creating organic
cow milk, with alias `cow-milk-organic-national-average` (a way for humans to
refer to a specific process), with an empty comment, which will be constructed
by putting 20% of 5 different organic milk taken from database Agribalyse
3.2, with an (actualy unused) id, and whose name will be as defined (with an
appended `, constructed by Ecobalyse`):

```
 {
    "activityCreationType": "from_scratch",
    "alias": "cow-milk-organic-national-average",
    "comment": "",
    "database": "Agribalyse 3.2",
    "exchanges": [
      {
        "activity": {
          "activity": "Cow milk, organic, system number 1, at farm gate {FR} U",
          "database": "Agribalyse 3.2"
        },
        "amount": 0.2
      },
      {
        "activity": {
          "activity": "Cow milk, organic, system number 2, at farm gate {FR} U",
          "database": "Agribalyse 3.2"
        },
        "amount": 0.2
      },
      {
        "activity": {
          "activity": "Cow milk, organic, system number 3, at farm gate {FR} U",
          "database": "Agribalyse 3.2"
        },
        "amount": 0.2
      },
      {
        "activity": {
          "activity": "Cow milk, organic, system number 4, at farm gate {FR} U",
          "database": "Agribalyse 3.2"
        },
        "amount": 0.2
      },
      {
        "activity": {
          "activity": "Cow milk, organic, system number 5, at farm gate {FR} U",
          "database": "Agribalyse 3.2"
        },
        "amount": 0.2
      }
    ],
    "id": "2bf307e8-8cb0-400b-a4f1-cf615d9e96f4",
    "newName": "Cow milk, organic, national average, at farm gate FR U"
  },
```

#### Creating an LCA process from an existing one

Here below we create a modified wheat flour by replacing the conventional wheat
with organic wheat, by digging just one level inside the existing wheat flour
in Agribalyse, and by giving it the specified new name (with an appended `,
constructed by Ecobalyse`. (LCA processes are like giant trees where we can
replace a process ay any level.


```
 {
    "activityCreationType": "from_existing",
    "alias": "wheat-flour-organic-national-average",
    "comment": "",
    "database": "Agribalyse 3.2",
    "existingActivity": {
      "activity": "Wheat flour, at plant {FR} U",
      "database": "Agribalyse 3.2"
    },
    "id": "db791ac8-02b9-41b0-bc2b-2913e745bd19",
    "newName": "Wheat flour, organic at industrial mill {FR} U {{wheat-flour-organic-national-average}}, created by Ecobalyse",
    "replacementPlan": {
      "replace": [
        {
          "from": {
            "activity": "Soft wheat grain, conventional, breadmaking quality, 15% moisture, at farm gate {FR} U",
            "database": "Agribalyse 3.2"
          },
          "to": {
            "activity": "Soft wheat grain, organic, 15% moisture, Central Region, at feed plant {FR} U",
            "database": "Agribalyse 3.2"
          }
        }
      ],
      "upstreamPath": [
        {
          "activity": "Global milling process, soft wheat, steel-roller-milled, industrial production, French production mix, at plant, 1 kg bulk flour at the exit gate (PDi) {FR} U",
          "database": "Agribalyse 3.2"
        },
        {
          "activity": "Soft wheat, consumption mix {FR} U",
          "database": "Agribalyse 3.2"
        }
      ]
    }
  },
```

### Selecting what you want in Ecobalyse

The next configuration file called `activities.json` allows to select what we
want in Ecobalyse in a single file:

- the list of processes to be exported from Brightway
- the list of ingredients (for the food sector)
- the list of materials (for the textile sector)
- the list of `custom` processes, with hardcoded impacts (in long-term deprecation)

Note that the identifiers of the ingredients (`id`) and materials
(`material_id`) are expected to be persistent. As a summary they should only
change when the semantics of the `displayName` changes.

### other configuration files

- `impacts.json`: the definition of the LCIA methods, their normalizations and
  weightings. We currently define PEF and ECS (Ecobalyse environment cost).

Note that other non-LCA-depedent JSON file are located in the `ecobalyse`
repository, such as examples of textile products, food recipes, etc.

## Export process

Then run the export process:

    npm run export:all

This will create:

- `processes_impacts.json` file with detailed impacts
- `processes.json` without detailed impacts
- `ingredients.json` with the list of ingredients (for food)
- `materials.json`with the list of materials (for textile)

All these files are loaded by the Ecobalyse frontend (see in
https://github.com/MTES-MCT/ecobalyse/ ) and exported both in this repository
and in a second configurable location (typically the Ecobalyse repository).

## Jupyter

You can start a `jupyter` server to explore the processes in Brightway or do other Python tasks:

    uv run jupyter lab

The password is empty by default.

### Brightway explorer

In a Jupyter notebook, enter `import notebooks.explore` and then validate with `shift-Enter`.

### Ingredients editor (in deprecation)

In a Jupyter notebook, enter `import notebooks.ingredients` and then validate with `shift-Enter`.

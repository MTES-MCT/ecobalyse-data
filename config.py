from os.path import abspath, dirname, join

from dynaconf import Dynaconf, Validator

PROJECT_ROOT_DIR = dirname(abspath(__file__))

PREFIX = "ECOBALYSE"
settings = Dynaconf(
    root_path=PROJECT_ROOT_DIR,  # defining root_path
    envvar_prefix=PREFIX,
    settings_files=["settings.toml"],
    environments=True,
    load_dotenv=True,
    dotenv_verbose=True,
    default_env="default",  # env where the default values will be taken from
    env="development",  # this is the active env, by default
    env_switcher="ECOBALYSE_ENV",
    validators=[
        # Check that the output dir was set
        Validator(
            "OUTPUT_DIR",
            must_exist=True,
            messages={
                "must_exist_true": "🚨 ERROR: For the export to work properly, you need to specify "
                + PREFIX
                + "_{name} env variable. It needs to point to the 'public/data/' directory of https://github.com/MTES-MCT/ecobalyse/ repository. Please, edit your .env file accordingly or add the {name} variable to your `settings.toml` file."
            },
        ),
    ],
)


ecosystemic_services_list = ["hedges", "plotSize", "cropDiversity"]


def get_absolute_path(
    relative_path, base_path=settings.get("base_path", PROJECT_ROOT_DIR)
):
    return join(base_path, relative_path)


# `envvar_prefix` = export envvars with `export ECOBALYSE_FOO=bar`.
# `settings_files` = Load these files in the order.

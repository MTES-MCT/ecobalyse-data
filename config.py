import logging
from os.path import abspath, dirname, join

from dynaconf import Dynaconf, Validator
from platformdirs import user_cache_path

PROJECT_ROOT_DIR = dirname(abspath(__file__))

settings = Dynaconf(
    root_path=PROJECT_ROOT_DIR,  # defining root_path
    # We keep the ECOBALYSE_ prefix for compatibility but we’ll use EB_ from now on
    envvar_prefix="ECOBALYSE,EB",
    settings_files=["settings.toml"],
    environments=True,
    load_dotenv=True,
    dotenv_verbose=True,
    default_env="default",  # env where the default values will be taken from
    env="development",  # this is the active env, by default
    env_switcher="ECOBALYSE_ENV",
    validators=[
        Validator(
            "LOG_LEVEL",
            default="INFO",
            is_in=(logging.getLevelNamesMapping().keys()),
        ),
        # Check that the output dir was set
        Validator(
            "OUTPUT_DIR",
            must_exist=True,
            messages={
                "must_exist_true": "🚨 For the export to work properly, you need to specify "
                "the EB_{name} env variable.\nIt needs to point to the 'public/data/' directory "
                "of the https://github.com/MTES-MCT/ecobalyse/ repository. \nPlease, edit your .env file "
                "accordingly."
            },
        ),
        # The S3 related variables are read from the environment
        Validator("S3_ENDPOINT", must_exist=True),
        Validator("S3_REGION", must_exist=True),
        Validator("S3_ACCESS_KEY_ID", must_exist=True),
        Validator("S3_SECRET_ACCESS_KEY", must_exist=True),
        Validator("S3_BUCKET", must_exist=True),
        Validator("S3_DB_PREFIX", must_exist=True),
        Validator(
            "DB_CACHE_DIR",
            default=user_cache_path("ecobalyse") / "db-cache",
            apply_default_on_none=True,
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

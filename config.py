from dynaconf import Dynaconf, Validator

settings = Dynaconf(
    envvar_prefix="ECOBALYSE",
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
                "must_exist_true": "🚨 ERROR: For the export to work properly, you need to specify {name} env variable. It needs to point to the 'public/data/' directory of https://github.com/MTES-MCT/ecobalyse/ repository. Please, edit your .env file accordingly."
            },
        ),
    ],
)

# `envvar_prefix` = export envvars with `export ECOBALYSE_FOO=bar`.
# `settings_files` = Load these files in the order.

# Configure logger
import sys

import bw2data
from loguru import logger

from common import brightway_patch as brightway_patch
from config import settings

print("Syncing datapackages...")

logger.remove()  # Remove default handler
logger.add(sys.stderr, format="{time} {level} {message}", level="INFO")

bw2data.projects.set_current(settings.bw.project)
for method in bw2data.methods:
    logger.info(f"Syncing method {method}...")
    bw2data.Method(method).process()

for database in bw2data.databases:
    logger.info(f"Syncing database {database}...")
    bw2data.Database(database).process()
print("done")

import bw2data

from common import brightway_patch as brightway_patch
from config import settings

print("Syncing datapackages...")
bw2data.projects.set_current(settings.bw.project)
for method in bw2data.methods:
    bw2data.Method(method).process()

for database in bw2data.databases:
    bw2data.Database(database).process()
print("done")

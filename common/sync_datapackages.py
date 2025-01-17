import bw2data

from common import brightway_patch as brightway_patch

PROJECT = "default"
print("Syncing datapackages...")
bw2data.projects.set_current(PROJECT)
for method in bw2data.methods:
    bw2data.Method(method).process()

for database in bw2data.databases:
    bw2data.Database(database).process()
print("done")

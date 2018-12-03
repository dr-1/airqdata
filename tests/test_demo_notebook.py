#!/usr/bin/env python3

"""Test the demo notebook."""

import json
import os
import sys

here = os.path.dirname(__file__)
project_dir = os.path.normpath(os.path.join(here, os.path.pardir))
sys.path.append(project_dir)
notebook_file = os.path.join(project_dir, "demo.ipynb")
with open(notebook_file, "r") as file:
    notebook = json.load(file)
cell_count = len(notebook["cells"])
failure_count = 0
for i, cell in enumerate(notebook["cells"], start=1):
    counter = "Cell {i}/{total}:\t".format(i=i, total=cell_count)
    if cell["cell_type"] != "code":
        print(counter + "skipped: cell type is " + cell["cell_type"])
        continue
    code = "".join(line for line in cell["source"]
                   if not line.startswith("%"))
    try:
        exec(code)
    except Exception as e:
        print(counter + "FAILED:\t" + str(e))
        failure_count += 1
        continue
    print(counter + "passed")
if failure_count:
    print("\n{failure_count} cell{s} failed"
          .format(failure_count=failure_count, s=(failure_count > 1) * "s"))
else:
    print("\nAll cells ran successfully")

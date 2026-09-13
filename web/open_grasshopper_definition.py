"""Open the tactile Grasshopper definition in the running Rhino instance."""

import os
import Rhino

Rhino.RhinoApp.RunScript("_Grasshopper", False)

from Grasshopper import Instances
from Grasshopper.Kernel import GH_DocumentIO


definition_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "tactile", "1.gh")
document_io = GH_DocumentIO()

if not document_io.Open(definition_path):
    raise RuntimeError("Could not open {}".format(definition_path))

if Instances.ActiveCanvas is None:
    raise RuntimeError("Grasshopper canvas is not available")

Instances.ActiveCanvas.Document = document_io.Document
document_io.Document.Enabled = True
document_io.Document.NewSolution(True)

print("Opened {}".format(definition_path))

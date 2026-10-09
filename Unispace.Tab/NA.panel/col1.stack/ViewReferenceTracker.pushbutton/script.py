# -*- coding: utf-8 -*-
"""
View Reference Tracker
Shows which detail views are placed on sheets and how many times they're referenced.
"""
__title__ = 'View Reference\nTracker'
__author__ = 'Matt Vogel'
__doc__ = 'Track view placements and references across sheets.'

import os
import sys

# Add current directory to path for imports
script_dir = os.path.dirname(__file__)
if script_dir not in sys.path:
    sys.path.append(script_dir)

from window import ViewReferenceTrackerWindow

# Get document and UI document
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

# Launch the window
try:
    window = ViewReferenceTrackerWindow(doc, uidoc)
except Exception as e:
    from Autodesk.Revit.UI import TaskDialog
    dialog = TaskDialog("Error")
    dialog.MainInstruction = "Failed to launch View Reference Tracker"
    dialog.MainContent = str(e)
    dialog.Show()

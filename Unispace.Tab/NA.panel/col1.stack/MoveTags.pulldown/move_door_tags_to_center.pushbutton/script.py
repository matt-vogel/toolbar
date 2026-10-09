# -*- coding: utf-8 -*-
__title__ = 'Center Door Tags in View'
__author__ = 'Matt Vogel'
__doc__ = 'Centers all door tags in the current view on their host doors.'

from pyrevit import revit, DB
from Autodesk.Revit.DB import XYZ, FilteredElementCollector, BuiltInCategory, Transaction, IndependentTag

# Get the current Revit document
doc = revit.doc

def center_tag_on_door_in_view(view_id):
    # Filter for all door tags in the current view
    tags = FilteredElementCollector(doc, view_id).OfCategory(BuiltInCategory.OST_DoorTags).WhereElementIsNotElementType().ToElements()
    
    # print("Number of door tags found: {0}".format(len(tags)))  # Debugging output

    # Start a transaction to modify the document
    t = Transaction(doc, 'Center Door Tags in View')
    t.Start()

    try:
        # Iterate through all door tags and center them on their host doors
        for tag in tags:
            # Make sure the tag is an IndependentTag
            if isinstance(tag, IndependentTag):
                # Get the door element that the tag is tagging
                door = doc.GetElement(tag.TaggedLocalElementId)
                if door:
                    # Get the bounding box of the door in the current view
                    door_bbox = door.get_BoundingBox(doc.ActiveView)
                    if door_bbox:  # Check if the bounding box is valid
                        # Calculate the center point of the door
                        door_center = XYZ((door_bbox.Min.X + door_bbox.Max.X) / 2, (door_bbox.Min.Y + door_bbox.Max.Y) / 2, door_bbox.Min.Z)
                        # Set the tag head position to the center point of the door
                        tag.TagHeadPosition = door_center
                        # print("Moved tag ID {0} to center of door ID {1}".format(tag.Id, door.Id))  # Debugging output
            #         else:
            #             print("No bounding box found for door with Id: {0}".format(door.Id))  # Debugging output
            #     else:
            #         # print("No door found for tag with Id: {0}".format(tag.Id))  # Debugging output
            # else:
            #     # print("Tag ID {0} is not an IndependentTag".format(tag.Id))  # Debugging output
        
        # Commit the transaction
        t.Commit()
    except Exception as e:
        # If there's an error, roll back the changes
        t.RollBack()
        print("Error: {0}".format(str(e)))  # Debugging output

# Get the current view ID
current_view_id = doc.ActiveView.Id

# Call the function with the current view ID
center_tag_on_door_in_view(current_view_id)
# Import necessary pyRevit and Revit API modules
from pyrevit import revit, DB, forms, script
import math
import clr
clr.AddReference('RevitServices')
clr.AddReference('RevitAPI')
clr.AddReference('RevitNodes')
clr.AddReference('RevitAPIUI')
clr.AddReference('System')
from System.Collections.Generic import List

import custom_dialog  # Import the custom dialog module

# Get the current Revit document
doc = __revit__.ActiveUIDocument.Document

# Define a function to get all rooms in the project or current view
def get_all_rooms(doc, current_view_rooms):
    if current_view_rooms:
        # Create a filtered element collector for rooms in the current view
        room_collector = DB.FilteredElementCollector(doc, doc.ActiveView.Id).OfCategory(DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType()
    else:
        # Create a filtered element collector for all rooms in the project
        room_collector = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType()
    return room_collector.ToElements()

# Define a function to filter out unplaced rooms
def filter_unplaced_rooms(rooms):
    placed_rooms = [room for room in rooms if room.Location is not None]
    return placed_rooms

# Define a function to center the room point
def center_room_point(room):
    geo_opts = DB.Options()
    geo = room.get_Geometry(geo_opts)
    centroid = None

    for geom in geo:
        if isinstance(geom, DB.Solid):
            try:
                centroid = geom.ComputeCentroid()
                break
            except Exception:
                continue

    if centroid is None:
        return

    room_location = room.Location.Point
    new_point = DB.XYZ(centroid.X, centroid.Y, room_location.Z)

    if room.IsPointInRoom(new_point):
        with DB.Transaction(doc, "Center Room Point") as t:
            t.Start()
            room.Location.Point = new_point
            t.Commit()
    else:
        with DB.Transaction(doc, "Reset Room Point") as t:
            t.Start()
            room.Location.Point = room_location
            t.Commit()

# Function to extract floor number from a string like "Level 1"
def extract_floor_number(s):
    digits = ""
    for char in s:
        if char.isdigit():
            digits += char
        elif digits:
            break
    if digits and digits[0] == '0':
        return digits
    if digits and int(digits) < 10:
        return "0%s" % digits
    if digits:
        return digits
    else:
        return None

# Function to convert a number to a letter
def number_to_letter(num):
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    num = int(num)  # Ensure num is an integer
    result = ''
    while num > 0:
        num -= 1
        remainder = num % 26
        result = alphabet[remainder] + result
        num = num // 26
    return result

# Function to get the X axis name based on grid spacing
def room_x_axis_name(room_point, point_top_left, grid_spacing):
    room_name_x = (room_point.X - point_top_left.X) / grid_spacing
    room_name_x = abs(room_name_x)
    room_name_x = math.ceil(room_name_x)
    room_name_x = int(room_name_x)  # Ensure it's an integer
    if room_name_x < 10:
        return "0{}".format(room_name_x)
    else:
        return str(room_name_x)

# Function to get the Y axis name based on grid spacing
def room_y_axis_name(room_point, point_top_left, grid_spacing):
    room_name_y = (room_point.Y - point_top_left.Y) / grid_spacing
    room_name_y = abs(room_name_y)
    room_name_y = math.ceil(room_name_y)  # Ensure it's an integer
    room_name_y = int(room_name_y)  # Explicitly convert to integer
    room_name_y = number_to_letter(room_name_y)
    return room_name_y

# Function to append a letter to duplicate room numbers
def append_letter(room_numbers_dict, room_number, room_area):
    if room_number in room_numbers_dict:
        existing_area = room_numbers_dict[room_number]
        if room_area < existing_area:
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                new_room_number = room_number + letter
                if new_room_number not in room_numbers_dict:
                    return new_room_number
        else:
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                new_room_number = room_number + letter
                if new_room_number not in room_numbers_dict:
                    room_numbers_dict[new_room_number] = room_area
                    return new_room_number
    else:
        return room_number

# Function to append a number to duplicate room numbers
def append_number(room_numbers_dict, room_number, room_area):
    if room_number in room_numbers_dict:
        existing_area = room_numbers_dict[room_number]
        if room_area < existing_area:
            for i in range(1, 100):
                new_room_number = "{}.{:02d}".format(room_number, i)
                if new_room_number not in room_numbers_dict:
                    return new_room_number
        else:
            for i in range(1, 100):
                new_room_number = "{}.{:02d}".format(room_number, i)
                if new_room_number not in room_numbers_dict:
                    room_numbers_dict[new_room_number] = room_area
                    return new_room_number
    else:
        return room_number

# Function to center room tags on their room points
def tags_to_room_center():
    room_tags = DB.FilteredElementCollector(doc, doc.ActiveView.Id).OfCategory(
                DB.BuiltInCategory.OST_RoomTags).WhereElementIsNotElementType().ToElements()
    
    with DB.Transaction(doc, 'Move Room Tags on Room Points') as t:
        t.Start()
        for room_tag in room_tags:
            room_tag_pt = room_tag.Location.Point
            room = room_tag.Room
            room_pt = room.Location.Point
            new_x = room_pt.X - room_tag_pt.X
            new_y = room_pt.Y - room_tag_pt.Y
            new_z = room_pt.Z - room_tag_pt.Z

            translation = DB.XYZ(new_x, new_y, new_z)
            room_tag.Location.Move(translation)
        t.Commit()

# Function to generate column labels (A, B, ..., Z, AA, AB, AC, ...)
def get_column_label(index):
    label = ""
    while index >= 0:
        label = chr(index % 26 + 65) + label
        index = index // 26 - 1
    return label

# Function to draw a grid using red lines
def draw_grid(point_top_left, grid_spacing):
    # Get the current view
    view = doc.ActiveView

    # Check if the view has an active crop region
    if view.CropBoxActive:
        crop_box = view.CropBox
        min_x = min(crop_box.Min.X, crop_box.Max.X)
        max_x = max(crop_box.Min.X, crop_box.Max.X)
        min_y = min(crop_box.Min.Y, crop_box.Max.Y)
        max_y = max(crop_box.Min.Y, crop_box.Max.Y)
    else:
        # Fallback to using the bounding box if no crop region is active
        bounding_box = view.CropBox
        min_x = min(bounding_box.Min.X, bounding_box.Max.X)
        max_x = max(bounding_box.Min.X, bounding_box.Max.X)
        min_y = min(bounding_box.Min.Y, bounding_box.Max.Y)
        max_y = max(bounding_box.Min.Y, bounding_box.Max.Y)

    # Calculate the number of rows and columns needed to cover the view
    num_cols = math.ceil((max_x - point_top_left.X) / grid_spacing)
    num_rows = math.ceil((point_top_left.Y - min_y) / grid_spacing)

    # Define the line style name for red lines
    line_style_name = "01 - Ultra Light Red"

    # Start a new transaction to create elements
    t1 = DB.Transaction(doc, 'Draw Grid Lines')
    t1.Start()

    # Find the line style by name
    line_style = None
    categories = doc.Settings.Categories
    lines_category = categories.get_Item(DB.BuiltInCategory.OST_Lines)
    sub_categories = lines_category.SubCategories

    for sub_cat in sub_categories:
        if sub_cat.Name == line_style_name:
            line_style = sub_cat.GetGraphicsStyle(DB.GraphicsStyleType.Projection)
            break

    if line_style is None:
        raise Exception("Line style '{0}' not found".format(line_style_name))

    # Get a valid text type
    text_types = DB.FilteredElementCollector(doc).OfClass(DB.TextNoteType).ToElements()
    if not text_types:
        raise Exception("No text types found in the document.")
    text_type_id = text_types[0].Id  # Use the first available text type

    # Collect all created elements to group later
    created_elements = List[DB.ElementId]()

    # Draw vertical lines and add numbering
    for i in range(int(num_cols) + 1):  # Convert num_cols to int
        x = point_top_left.X + i * grid_spacing
        start_point = DB.XYZ(x, min_y, 0)
        end_point = DB.XYZ(x, point_top_left.Y + 5.0, 0)  # Extend 5' to the north
        line = DB.Line.CreateBound(start_point, end_point)
        detail_line = doc.Create.NewDetailCurve(view, line)
        detail_line.LineStyle = line_style
        created_elements.Add(detail_line.Id)

        # Add numbering text slightly to the right of the line
        text_position = DB.XYZ(x + 1.0, point_top_left.Y + 5.0, 0)  # Adjust as needed
        text_note = DB.TextNote.Create(doc, view.Id, text_position, str(i + 1), text_type_id)
        created_elements.Add(text_note.Id)

    # Draw horizontal lines and add lettering
    for j in range(int(num_rows) + 1):  # Convert num_rows to int
        y = point_top_left.Y - j * grid_spacing
        start_point = DB.XYZ(point_top_left.X - 5.0, y, 0)  # Start 5' to the left
        end_point = DB.XYZ(max_x, y, 0)
        line = DB.Line.CreateBound(start_point, end_point)
        detail_line = doc.Create.NewDetailCurve(view, line)
        detail_line.LineStyle = line_style
        created_elements.Add(detail_line.Id)

        # Add lettering text slightly below the line
        text_position = DB.XYZ(point_top_left.X - 5.0, y - 1.0, 0)  # Adjust as needed
        text_note = DB.TextNote.Create(doc, view.Id, text_position, get_column_label(j), text_type_id)
        created_elements.Add(text_note.Id)

    # Commit the transaction for creating elements
    t1.Commit()

    # Start a new transaction to create the group
    t2 = DB.Transaction(doc, 'Create Group')
    t2.Start()

    # Create a group for the created elements
    group = doc.Create.NewGroup(created_elements)

    # Commit the transaction for creating the group
    t2.Commit()

# Main script execution
if __name__ == "__main__":
    output = script.get_output()
    
    # Ask the user if drawings have been issued to consultants
    issued_to_consultants = forms.alert("Have drawings been issued to consultants yet? If yes, mass room renumbering should not be done to avoid coordination confusion.", yes=True, no=True)
    
    # If the user cancels or closes the alert, exit the script
    if issued_to_consultants is None:
        script.exit()

    # If the drawings have been issued, end the script
    if issued_to_consultants:
        forms.alert("Mass room renumbering will not be done to avoid coordination confusion.", title="Process Terminated")
        script.exit()
    
    # Show the custom dialog
    result = custom_dialog.show_dialog()
    if result:
        multi_floor = result["option1"]
        create_red_grid = result["option2"]
        center_room_tags = result["option3"]
        current_view_rooms = result["option4"]
        numbering_strategy = result["numbering_strategy"]
        # output.print_md("**Option 1:** %s" % result["option1"])
        # output.print_md("**Option 2:** %s" % result["option2"])
        # output.print_md("**Option 3:** %s" % result["option3"])
        # output.print_md("**Numbering Strategy:** %s" % result["numbering_strategy"])
    else:
        script.exit()
    
    # Display a popup message to the user
    start_point_alert = forms.alert("Pick Upper leftmost point of the plan. This will be the start point of the grid. No rooms should be North or West of this point.", title="Select Start Point")
    
    # If the user cancels or closes the alert, exit the script
    if start_point_alert is None:
        script.exit()
    
    # Allow the user to pick a point on the plan
    uidoc = __revit__.ActiveUIDocument
    try:
        point_top_left = uidoc.Selection.PickPoint("Pick Upper leftmost point of the plan")
    except Autodesk.Revit.Exceptions.OperationCanceledException:
        script.exit()
    
    # Define grid spacing (e.g., 10 feet)
    grid_spacing = 10.0  # Adjust as needed
    
    if create_red_grid:
        # Draw the grid
        draw_grid(point_top_left, grid_spacing)

    # Get all rooms in the project or current view
    all_rooms = get_all_rooms(doc, current_view_rooms)
    
    # Filter out unplaced rooms
    placed_rooms = filter_unplaced_rooms(all_rooms)
    
    # Output the results
    # output.print_md("**Total rooms in project:** {}".format(len(all_rooms)))
    # output.print_md("**Placed rooms in project:** {}".format(len(placed_rooms)))
    
    # Dictionary to keep track of room numbers and their areas
    room_numbers_dict = {}
    
    # List to store room number updates
    room_updates = []
    
    # Print details of placed rooms and center their points
    for room in placed_rooms:
        room_name = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME).AsString()
        room_number = room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER).AsString()
        
        # Center the room point
        center_room_point(room)
        
        # Get room location point
        room_location = room.Location.Point
        room_x = room_location.X
        room_y = room_location.Y
        
        # Get room level
        room_level = room.Level.Name
        
        # Extract floor number from level name
        floor_number = extract_floor_number(room_level)
        
        # Get grid-based names for the room
        x_axis_name = room_x_axis_name(room_location, point_top_left, grid_spacing)
        y_axis_name = room_y_axis_name(room_location, point_top_left, grid_spacing)
        
        # Construct the new room number
        if multi_floor:
            new_room_number = "{}{}{}".format(floor_number, y_axis_name, x_axis_name)
        else:
            new_room_number = "{}{}".format(y_axis_name, x_axis_name)
        
        # Get room area
        room_area = room.get_Parameter(DB.BuiltInParameter.ROOM_AREA).AsDouble()

        # Ensure the room number is unique and assign the smaller room the appended letter or number
        if numbering_strategy == "Alphabetic (A, B, etc)":
            new_room_number = append_letter(room_numbers_dict, new_room_number, room_area)
        else:
            new_room_number = append_number(room_numbers_dict, new_room_number, room_area)

        room_numbers_dict[new_room_number] = room_area
        
        # Store the room and its new number for later renumbering
        room_updates.append((room, new_room_number))
        
        # output.print_md("**Room Name:** {}, **Room Number:** {}, **Coordinates:** ({}, {}), **Level:** {}, **New Room Number:** {}".format(room_name, room_number, room_x, room_y, room_level, new_room_number))
    
    # Start a transaction to renumber the rooms
    with DB.Transaction(doc, "Renumber Rooms") as t:
        t.Start()
        temp_room_numbers = []
        for room, new_room_number in room_updates:
            # Temporarily set room number to avoid clashes
            temp_room_number = "TEMP_{}".format(new_room_number)
            temp_room_numbers.append(temp_room_number)
            room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER).Set(temp_room_number)
        
        # Set the final new room numbers
        for room, new_room_number in room_updates:
            room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER).Set(new_room_number)
        
        t.Commit()
    # Center room tags on their room points if requested
    if center_room_tags:
        tags_to_room_center()
    # output.print_md("**Room renumbering completed successfully!**")
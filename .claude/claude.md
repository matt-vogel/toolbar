# Unispace Revit Toolbar Development Guide

This guide documents patterns, conventions, and best practices for developing tools in the Unispace pyRevit toolbar.

## Project Overview

This is a custom pyRevit extension for Revit 2024 that provides productivity tools for Unispace workflows. The toolbar includes regional panels (NA, APAC), helper tools, and learning resources.

**Extension Root**: `toolbar.extension/`

## Directory Structure

```
toolbar.extension/
├── lib/                          # Shared libraries
│   ├── GUI/                      # WPF UI components and forms
│   │   ├── WPF_Base.py          # Base class for WPF windows
│   │   ├── Resources/
│   │   │   └── WPF_styles.xaml  # Shared dark theme styles
│   │   ├── FindReplace.py       # Reusable find/replace dialog
│   │   └── SelectFromDict.py    # Selection dialog utility
│   ├── Snippets/                # Reusable Revit API snippets
│   │   ├── _context_manager.py  # Transaction context managers
│   │   ├── _views.py            # View manipulation utilities
│   │   ├── _sheets.py           # Sheet utilities
│   │   └── _filters.py          # Element filter helpers
│   ├── Selection/               # Element selection utilities
│   └── Renaming/                # Base classes for renaming ops
│
├── Unispace.Tab/                # Main tab
│   ├── NA.panel/                # North America panel
│   │   ├── col1.stack/          # Stacked buttons
│   │   └── Renumber.pulldown/   # Dropdown menu
│   ├── APAC.panel/              # Asia-Pacific panel
│   ├── Helpers.panel/           # Helper tools
│   ├── Learning.panel/          # Learning resources
│   └── Working.Panel/           # Work-in-progress tools
```

## Creating New Pushbuttons

### 1. Folder Structure

Pushbuttons must follow this naming convention: `ButtonName.pushbutton/`

**Required files:**
- `script.py` - Entry point (executed when button clicked)
- `icon.png` - Button icon (32x32px recommended)

**Optional files:**
- Additional Python modules for logic separation
- XAML files for custom UI
- Resource files (images, config, etc.)

### 2. Script.py Template

```python
# -*- coding: utf-8 -*-
"""
Brief description of what the tool does.
"""
__title__ = 'Button Name'  # Can include \n for multi-line in UI
__author__ = 'Matt Vogel'
__doc__ = 'Longer description of functionality.'

# Standard imports
from pyrevit import revit, DB, forms, script
from Autodesk.Revit.DB import Transaction, FilteredElementCollector, BuiltInCategory

# Get document references
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app = __revit__.Application

# Main logic here
try:
    # Your code
    pass
except Exception as e:
    from Autodesk.Revit.UI import TaskDialog
    dialog = TaskDialog("Error")
    dialog.MainInstruction = "Error message"
    dialog.MainContent = str(e)
    dialog.Show()
```

### 3. Metadata Fields

- `__title__`: Display name in UI (supports `\n` for line breaks)
- `__author__`: Developer name
- `__doc__`: Tooltip description shown on hover
- `__context__`: (Optional) Context requirements (e.g., 'selection', 'active-view')

## WPF Window Development

### Base Class Pattern

All custom WPF windows should inherit from `my_WPF` base class:

```python
import os
import sys
import clr
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
import wpf

# Add lib path for imports
lib_path = os.path.join(
    os.path.dirname(__file__),
    '..', '..', '..', '..', 'lib'
)
if lib_path not in sys.path:
    sys.path.append(lib_path)

from GUI.WPF_Base import my_WPF

class MyToolWindow(my_WPF):
    def __init__(self, doc, uidoc):
        self.doc = doc
        self.uidoc = uidoc

        # Load shared WPF styles (dark theme)
        self.add_wpf_resource()

        # Load XAML
        path_xaml = os.path.join(os.path.dirname(__file__), 'MyTool.xaml')
        wpf.LoadComponent(self, path_xaml)

        # Initialize UI
        self.populate_data()

        # Show window (use ShowDialog() for modal, Show() for modeless)
        self.ShowDialog()

    def button_close(self, sender, e):
        """Inherited from my_WPF - closes window"""
        self.Close()

    def header_drag(self, sender, e):
        """Inherited from my_WPF - allows window dragging"""
        if e.LeftButton == MouseButtonState.Pressed:
            DragMove(self)
```

### XAML Structure

Windows should use the shared dark theme and follow this structure:

```xml
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Tool Name" Height="600" Width="800"
        Background="#181735"
        WindowStartupLocation="CenterScreen"
        WindowStyle="None"
        AllowsTransparency="True">

    <Border BorderBrush="#EE82EE" BorderThickness="1" CornerRadius="10">
        <Grid>
            <!-- Header with drag handle and close button -->
            <Grid Background="#0f0f2d" MouseLeftButtonDown="header_drag">
                <TextBlock Text="Title" Foreground="White"/>
                <Button Content="Close" Click="button_close"/>
            </Grid>

            <!-- Content here -->
        </Grid>
    </Border>
</Window>
```

### WPF Styles Available

The shared `WPF_styles.xaml` provides:

**Colors:**
- Background: `#0f0f2d` (header), `#181735` (main)
- Accent: `#EE82EE` (magenta), `DodgerBlue`
- Hover: `#FF4C70`
- Text: White, Gray

**Styled Controls:**
- Button (rounded corners, hover effects)
- CheckBox (gradient pink/blue)
- TextBox, TextBlock, Label
- ListBox, ComboBox
- ScrollBar (custom thumb)
- Border (10px corner radius default)

## Revit API Patterns

### Document Access

```python
# Standard pattern used throughout toolbar
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app = __revit__.Application
rvt_year = int(app.VersionNumber)  # For version-specific logic
```

### Transactions

**Basic Pattern:**
```python
from Autodesk.Revit.DB import Transaction

t = Transaction(doc, 'Transaction Name')
t.Start()
try:
    # Modify elements here
    t.Commit()
except Exception as e:
    t.RollBack()
    print("Error: {}".format(str(e)))
```

**Context Manager (from lib):**
```python
from Snippets._context_manager import ef_Transaction

with ef_Transaction(doc, 'Transaction Name', debug=True):
    # Modifications auto-commit
    pass
```

### FilteredElementCollector

**In entire document:**
```python
elements = FilteredElementCollector(doc)\
    .OfCategory(BuiltInCategory.OST_Rooms)\
    .WhereElementIsNotElementType()\
    .ToElements()
```

**In specific view:**
```python
elements = FilteredElementCollector(doc, view.Id)\
    .OfCategory(BuiltInCategory.OST_DoorTags)\
    .WhereElementIsNotElementType()\
    .ToElements()
```

**All sheets:**
```python
from Autodesk.Revit.DB import ViewSheet

sheets = FilteredElementCollector(doc)\
    .OfClass(ViewSheet)\
    .ToElements()
```

### Parameter Access

**Built-in parameters:**
```python
# Get value
room_number = room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER).AsString()

# Set value
param = room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER)
param.Set("101")
```

**Custom/shared parameters:**
```python
# Using LookupParameter (preferred for custom params)
detail_param = viewport.LookupParameter("Detail Number")
if detail_param and not detail_param.IsReadOnly:
    detail_number = detail_param.AsString()
    detail_param.Set("5")
```

**Common parameter patterns in this toolbar:**
- Detail numbers: `viewport.LookupParameter("Detail Number")`
- Sheet numbers: `sheet.SheetNumber` (property, not parameter)
- View names: `view.Name` (property)

### Common Utilities Available

**From `lib/Snippets/_sheets.py`:**
```python
from Snippets._sheets import get_views_on_sheet

views = get_views_on_sheet(sheet, uidoc)
```

**From `lib/Snippets/_views.py`:**
```python
from Snippets._views import get_sheet_from_view

sheet = get_sheet_from_view(view)
```

**From `lib/Snippets/_filters.py`:**
```python
from Snippets._filters import create_filter, get_family_types
```

## Coding Style & Conventions

### Naming Conventions

- **Variables**: `lowercase_with_underscores`
- **Functions**: `lowercase_with_underscores()`
- **Classes**: `PascalCase`
- **Constants**: `UPPERCASE_WITH_UNDERSCORES`

**Common variable names:**
- `doc` - Document
- `uidoc` - UIDocument
- `app` - Application
- `vp` - Viewport
- `t` - Transaction

### Error Handling

Always wrap main logic in try/except with user-friendly messages:

```python
try:
    # Main logic
    pass
except Exception as e:
    from Autodesk.Revit.UI import TaskDialog
    dialog = TaskDialog("Error")
    dialog.MainInstruction = "User-friendly error message"
    dialog.MainContent = str(e)
    dialog.Show()
```

### User Interaction

**Alerts:**
```python
from pyrevit import forms

# Simple message
forms.alert("Message text")

# Yes/No question
result = forms.alert("Question?", yes=True, no=True)
if result:
    # User clicked yes
    pass
```

**TaskDialog (for more complex dialogs):**
```python
from Autodesk.Revit.UI import TaskDialog, TaskDialogCommonButtons, TaskDialogResult

dialog = TaskDialog("Title")
dialog.MainInstruction = "Main message"
dialog.MainContent = "Additional details"
dialog.CommonButtons = TaskDialogCommonButtons.Yes | TaskDialogCommonButtons.No
result = dialog.Show()

if result == TaskDialogResult.Yes:
    # User clicked yes
    pass
```

### Comments & Documentation

- Use docstrings for functions/classes
- Add inline comments for complex logic
- Include examples in docstrings when helpful
- Document assumptions and limitations

## Platform-Specific Notes (Windows)

### File Operations

**IMPORTANT**: This repo runs on Windows. Command patterns:

✅ **Correct:**
```bash
cmd /c copy "source" "dest"
powershell -Command "Copy-Item 'source' 'dest'"
```

❌ **Incorrect (will fail):**
```bash
copy "source" "dest"  # Bash built-in, not Windows
cp "source" "dest"    # Unix command
```

### Path Handling

Use `os.path.join()` for cross-platform compatibility:

```python
# Good
path = os.path.join(dir_path, 'subfolder', 'file.py')

# Avoid hardcoded separators
path = dir_path + '\\subfolder\\file.py'  # Less portable
```

## Common Patterns Reference

### Checking Sheet Size

```python
def check_sheet_size_from_titleblock(sheet, expected_width, expected_height):
    """Check if sheet matches expected dimensions (in inches)"""
    title_blocks = FilteredElementCollector(doc, sheet.Id)\
        .OfCategory(BuiltInCategory.OST_TitleBlocks)\
        .WhereElementIsNotElementType()\
        .ToElements()

    if title_blocks:
        title_block = title_blocks[0]
        width_param = title_block.Parameter[DB.BuiltInParameter.SHEET_WIDTH]
        height_param = title_block.Parameter[DB.BuiltInParameter.SHEET_HEIGHT]

        if width_param and height_param:
            width = int(round(width_param.AsDouble() * 12.0))  # Feet to inches
            height = int(round(height_param.AsDouble() * 12.0))
            return width == expected_width and height == expected_height

    return False
```

### Unit Conversion

Revit uses feet internally:

```python
def inches_to_feet(inches):
    return inches / 12.0

def feet_to_inches(feet):
    return feet * 12.0
```

### View Type Filtering

```python
from Autodesk.Revit.DB import ViewType

if view.ViewType == ViewType.FloorPlan:
    # Floor plan specific logic
    pass
elif view.ViewType == ViewType.Section:
    # Section specific logic
    pass
elif view.ViewType == ViewType.DraftingView:
    # Drafting view specific logic
    pass

# Skip legends
if view.ViewType == ViewType.Legend:
    continue
```

### Viewport Operations

```python
# Get viewports on a sheet
viewport_ids = sheet.GetAllViewports()
for vp_id in viewport_ids:
    viewport = doc.GetElement(vp_id)
    view = doc.GetElement(viewport.ViewId)

    # Get viewport detail number
    detail_param = viewport.LookupParameter("Detail Number")
    if detail_param and not detail_param.IsReadOnly:
        detail_number = detail_param.AsString()
```

## Testing & Debugging

### Testing New Tools

1. **Restart Revit** after creating/modifying pushbuttons
2. pyRevit needs to reload to detect changes
3. Test in a non-production project first
4. Verify transactions commit properly
5. Check error handling paths

### Common Issues

**Import Errors:**
- Ensure lib path is added to `sys.path`
- Check relative path calculation (count `..` correctly)
- Verify file names match import statements

**Transaction Errors:**
- Element modification outside transaction
- Transaction not committed/rolled back
- Multiple transactions open simultaneously

**UI Issues:**
- XAML file not found (check path)
- WPF styles not loaded (call `add_wpf_resource()`)
- Event handlers not connected (check XAML Click/Changed attributes)

## Examples in Codebase

**Good reference implementations:**

1. **AutoRenumberViewPorts** - Complex logic, grid calculations, viewport manipulation
   - Location: `NA.panel/Renumber.pulldown/AutoRenumberViewPorts.pushbutton/script.py`

2. **ViewReferenceTracker** - WPF window, data collection, tree views
   - Location: `NA.panel/col1.stack/ViewReferenceTracker.pushbutton/`

3. **Move Door Tags** - Simple, focused tool with error handling
   - Location: `NA.panel/col1.stack/move_door_tags_to_center.pushbutton/script.py`

## Additional Resources

- **pyRevit Documentation**: https://pyrevitlabs.notion.site/pyrevitlabs/pyRevit-bd907d6292ed4ce997c46e84b6ef67a0
- **Revit API Docs**: https://www.revitapidocs.com/
- **This toolbar's lib/**: Pre-built utilities for common operations

---

**Last Updated**: 2026-01-12
**Revit Version**: 2024
**pyRevit Version**: 4.8+

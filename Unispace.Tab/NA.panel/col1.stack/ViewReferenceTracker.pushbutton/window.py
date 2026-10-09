# -*- coding: utf-8 -*-
"""WPF Window for View Reference Tracker"""
__author__ = 'Matt Vogel'

import os
import sys

# Add lib path for imports FIRST (before other imports)
lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), 'lib')
if lib_path not in sys.path:
    sys.path.append(lib_path)

# CRITICAL: Import pyrevit.forms BEFORE wpf - needed for wpf import to work
from pyrevit import forms

import clr
clr.AddReference("System")
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
clr.AddReference("WindowsBase")
import wpf

from System.Windows import Window, MessageBox, MessageBoxButton, MessageBoxImage
from System.Windows.Controls import TreeViewItem, Button, StackPanel, TextBlock, Separator
from System.Windows import Thickness, HorizontalAlignment, VerticalAlignment
from System.Windows.Media import Brushes
import System

from data_collector import ViewReferenceCollector, ViewInfo, SheetInfo

from Autodesk.Revit.DB import ViewType, ViewSheet
from Autodesk.Revit.UI import TaskDialog


class ViewReferenceTrackerWindow(Window):
    """Main window for View Reference Tracker"""

    def __init__(self, doc, uidoc):
        self.doc = doc
        self.uidoc = uidoc
        self.collector = ViewReferenceCollector(doc)
        self.current_filters = self._get_active_filters()
        self.selected_view_info = None

        # Load XAML (no custom WPF styles - using standard Windows style)
        path_xaml = os.path.join(os.path.dirname(__file__), 'ViewReferenceTracker.xaml')
        wpf.LoadComponent(self, path_xaml)

        # Initial data load
        self.refresh_data()

        # Show window
        self.ShowDialog()

    def _get_active_filters(self):
        """Get currently active view type filters from checkboxes"""
        filters = {
            'floor_plans': True,
            'sections': True,
            'elevations': True,
            'drafting': True,
            '3d': True,
            'templates': False
        }

        # Update from UI if available
        if hasattr(self, 'chk_floor_plans'):
            filters['floor_plans'] = self.chk_floor_plans.IsChecked
            filters['sections'] = self.chk_sections.IsChecked
            filters['elevations'] = self.chk_elevations.IsChecked
            filters['drafting'] = self.chk_drafting.IsChecked
            filters['3d'] = self.chk_3d.IsChecked
            filters['templates'] = self.chk_templates.IsChecked

        return filters

    def _should_include_view(self, view_type):
        """Check if view type should be included based on current filters"""
        filters = self.current_filters

        if view_type == ViewType.FloorPlan or view_type == ViewType.CeilingPlan or view_type == ViewType.AreaPlan:
            return filters['floor_plans']
        elif view_type == ViewType.Section:
            return filters['sections']
        elif view_type == ViewType.Elevation:
            return filters['elevations']
        elif view_type == ViewType.DraftingView:
            return filters['drafting']
        elif view_type == ViewType.ThreeD:
            return filters['3d']

        return False

    def refresh_data(self):
        """Refresh data from model and rebuild UI"""
        try:
            # Show status
            self.status_text.Text = "Loading sheets and views..."
            self.loading_overlay_left.Visibility = System.Windows.Visibility.Visible

            # Clear existing data
            self.tree_sheets.Items.Clear()
            self.tree_unreferenced.Items.Clear()
            self.panel_details.Children.Clear()

            # Collect data
            self.collector = ViewReferenceCollector(self.doc)
            self.collector.collect_sheets_only()  # Fast initial load

            # Now collect references (this might take time)
            self.status_text.Text = "Analyzing references..."
            self.collector._collect_references()
            self.collector._identify_unreferenced_views()

            # Populate tree
            self._populate_tree()

            # Hide loading
            self.loading_overlay_left.Visibility = System.Windows.Visibility.Collapsed
            self.status_text.Text = "Ready - {} sheets, {} views".format(
                len(self.collector.sheets),
                len(self.collector.views)
            )

        except Exception as e:
            self.loading_overlay_left.Visibility = System.Windows.Visibility.Collapsed
            self.status_text.Text = "Error: {}".format(str(e))
            MessageBox.Show("Error loading data: {}".format(str(e)), "Error")

    def _populate_tree(self):
        """Populate the tree view with sheets and views"""
        # Sort sheets by number
        sorted_sheets = sorted(self.collector.sheets.values(), key=lambda s: s.sheet_number)

        for sheet_info in sorted_sheets:
            # Check if sheet has any views that match filters
            filtered_views = [v for v in sheet_info.views if self._should_include_view(v.view_type)]
            if not filtered_views:
                continue

            # Create sheet tree item
            sheet_item = TreeViewItem()
            sheet_item.Header = sheet_info.get_display_text()
            sheet_item.Tag = sheet_info
            sheet_item.FontSize = 13

            # Add views to sheet
            for view_info in filtered_views:
                view_item = TreeViewItem()
                view_item.Header = self._create_view_header(view_info)
                view_item.Tag = view_info
                view_item.FontSize = 12
                sheet_item.Items.Add(view_item)

            self.tree_sheets.Items.Add(sheet_item)

        # Populate unreferenced views
        self._populate_unreferenced()

    def _create_view_header(self, view_info):
        """Create a formatted header for a view item"""
        # Icon based on whether view is on sheet
        icon = "📄" if view_info.placement_count > 0 else "⚠"
        return "{} {}".format(icon, view_info.get_display_text())

    def _populate_unreferenced(self):
        """Populate unreferenced views section"""
        # Filter unreferenced views by type
        filtered_unref = [v for v in self.collector.unreferenced_views
                          if self._should_include_view(v.view_type)]

        # Update expander header
        self.expander_unreferenced.Header = "Unreferenced Views ({})".format(len(filtered_unref))

        for view_info in filtered_unref:
            view_item = TreeViewItem()

            # Determine icon
            if view_info.placement_count == 0:
                icon = "⚠"  # Not placed anywhere
            else:
                icon = "📄"  # Placed but not referenced

            view_item.Header = "{} {}".format(icon, view_info.get_display_text())
            view_item.Tag = view_info
            view_item.FontSize = 12

            self.tree_unreferenced.Items.Add(view_item)

    def _show_view_details(self, view_info):
        """Show reference details for a selected view in right panel"""
        self.selected_view_info = view_info
        self.panel_details.Children.Clear()

        # View title
        title = TextBlock()
        title.Text = "References for: {}".format(view_info.view_name)
        title.FontSize = 14
        title.FontWeight = System.Windows.FontWeights.Bold
        title.Foreground = Brushes.Black
        title.Margin = Thickness(0, 0, 0, 15)
        self.panel_details.Children.Add(title)

        # If no references
        if view_info.reference_count == 0:
            self._show_zero_reference_details(view_info)
            return

        # Lazy load references if needed
        if not view_info.referenced_from:
            self.loading_overlay_right.Visibility = System.Windows.Visibility.Visible
            self.collector.collect_references_for_view(view_info.view_id)
            self.loading_overlay_right.Visibility = System.Windows.Visibility.Collapsed

        # Group references by sheet
        refs_by_sheet = {}
        for ref_info in view_info.referenced_from:
            sheet_key = ref_info.source_sheet_number if ref_info.source_sheet_number else "Working Views"
            if sheet_key not in refs_by_sheet:
                refs_by_sheet[sheet_key] = []
            refs_by_sheet[sheet_key].append(ref_info)

        # Display grouped references
        for sheet_key in sorted(refs_by_sheet.keys()):
            ref_list = refs_by_sheet[sheet_key]

            # Sheet header
            sheet_header = TextBlock()
            if sheet_key == "Working Views":
                sheet_header.Text = "Working Views (not on sheets)"
                sheet_header.Foreground = Brushes.Gray
            else:
                first_ref = ref_list[0]
                sheet_header.Text = "Sheet {} - {}".format(
                    first_ref.source_sheet_number,
                    first_ref.source_sheet_name
                )
                sheet_header.Foreground = Brushes.Black

            sheet_header.FontSize = 13
            sheet_header.FontWeight = System.Windows.FontWeights.Bold
            sheet_header.Margin = Thickness(0, 10, 0, 5)
            self.panel_details.Children.Add(sheet_header)

            # References under this sheet
            for ref_info in ref_list:
                ref_panel = self._create_reference_panel(ref_info)
                self.panel_details.Children.Add(ref_panel)

            # Separator
            sep = Separator()
            sep.Margin = Thickness(0, 5, 0, 5)
            self.panel_details.Children.Add(sep)

    def _show_zero_reference_details(self, view_info):
        """Show details for view with zero references"""
        # Status message
        status = TextBlock()
        if view_info.placement_count == 0:
            status.Text = "⚠ This view is not placed on any sheet"
        else:
            status.Text = "📄 This view is placed on {} sheet(s) but has no references".format(
                view_info.placement_count
            )
        status.FontSize = 12
        status.Foreground = Brushes.Gray
        status.Margin = Thickness(0, 0, 0, 15)
        status.TextWrapping = System.Windows.TextWrapping.Wrap
        self.panel_details.Children.Add(status)

        # Show placement info if placed
        if view_info.placement_count > 0:
            placed_header = TextBlock()
            placed_header.Text = "Placed on:"
            placed_header.FontSize = 13
            placed_header.FontWeight = System.Windows.FontWeights.Bold
            placed_header.Foreground = Brushes.Black
            placed_header.Margin = Thickness(0, 5, 0, 5)
            self.panel_details.Children.Add(placed_header)

            for sheet_id, sheet_num, sheet_name, vp_id in view_info.placed_on_sheets:
                sheet_panel = StackPanel()
                sheet_panel.Orientation = System.Windows.Controls.Orientation.Horizontal
                sheet_panel.Margin = Thickness(10, 5, 0, 5)

                sheet_text = TextBlock()
                sheet_text.Text = "{} - {}".format(sheet_num, sheet_name)
                sheet_text.Foreground = Brushes.Black
                sheet_text.Margin = Thickness(0, 0, 15, 0)
                sheet_text.VerticalAlignment = VerticalAlignment.Center
                sheet_panel.Children.Add(sheet_text)

                # Open button
                open_btn = Button()
                open_btn.Content = "Open Sheet"
                open_btn.Width = 90
                open_btn.Height = 25
                open_btn.Tag = sheet_id
                open_btn.Click += self.open_sheet_click
                sheet_panel.Children.Add(open_btn)

                self.panel_details.Children.Add(sheet_panel)

        # Action buttons
        actions_header = TextBlock()
        actions_header.Text = "Actions:"
        actions_header.FontSize = 13
        actions_header.FontWeight = System.Windows.FontWeights.Bold
        actions_header.Foreground = Brushes.Black
        actions_header.Margin = Thickness(0, 15, 0, 5)
        self.panel_details.Children.Add(actions_header)

        # Highlight in browser button
        browser_btn = Button()
        browser_btn.Content = "Highlight in Project Browser"
        browser_btn.Width = 200
        browser_btn.Height = 30
        browser_btn.Margin = Thickness(10, 5, 0, 5)
        browser_btn.Tag = view_info.view_id
        browser_btn.Click += self.highlight_in_browser_click
        self.panel_details.Children.Add(browser_btn)

    def _create_reference_panel(self, ref_info):
        """Create a panel for a single reference"""
        panel = StackPanel()
        panel.Orientation = System.Windows.Controls.Orientation.Vertical
        panel.Margin = Thickness(10, 5, 10, 5)

        # Reference row (view name + detail number)
        ref_row = StackPanel()
        ref_row.Orientation = System.Windows.Controls.Orientation.Horizontal

        # Icon for non-sheet references
        if not ref_info.is_on_sheet:
            icon = TextBlock()
            icon.Text = "ⓘ"
            icon.Foreground = Brushes.Gray
            icon.Margin = Thickness(0, 0, 5, 0)
            icon.ToolTip = "This view is not on a sheet"
            ref_row.Children.Add(icon)

        ref_text = TextBlock()
        detail_str = " (Detail {})".format(ref_info.detail_number) if ref_info.detail_number else ""
        ref_text.Text = "• {}{}".format(ref_info.source_view_name, detail_str)
        ref_text.Foreground = Brushes.Black
        ref_text.Margin = Thickness(0, 0, 0, 5)
        ref_row.Children.Add(ref_text)

        panel.Children.Add(ref_row)

        # Button row (only if on sheet)
        if ref_info.is_on_sheet:
            button_row = StackPanel()
            button_row.Orientation = System.Windows.Controls.Orientation.Horizontal
            button_row.Margin = Thickness(20, 0, 0, 0)

            # Open Sheet button
            open_btn = Button()
            open_btn.Content = "Open Sheet"
            open_btn.Width = 90
            open_btn.Height = 25
            open_btn.Margin = Thickness(0, 0, 10, 0)
            open_btn.Tag = ref_info.source_sheet_id
            open_btn.Click += self.open_sheet_click
            button_row.Children.Add(open_btn)

            # Select Reference button
            select_btn = Button()
            select_btn.Content = "Select Reference"
            select_btn.Width = 120
            select_btn.Height = 25
            select_btn.Tag = (ref_info.source_view_id, ref_info.ref_element_id)
            select_btn.Click += self.select_reference_click
            button_row.Children.Add(select_btn)

            panel.Children.Add(button_row)

        return panel

    # ======================================== EVENT HANDLERS ========================================

    def button_close(self, sender, e):
        """Close window"""
        self.Close()

    def refresh_click(self, sender, e):
        """Refresh button clicked"""
        self.refresh_data()

    def filter_changed(self, sender, e):
        """Filter checkbox changed"""
        self.current_filters = self._get_active_filters()
        # Repopulate tree with new filters
        self.tree_sheets.Items.Clear()
        self.tree_unreferenced.Items.Clear()
        self._populate_tree()

    def tree_selection_changed(self, sender, e):
        """Tree selection changed"""
        tree = sender
        selected_item = tree.SelectedItem

        if selected_item and selected_item.Tag:
            tag = selected_item.Tag
            if isinstance(tag, ViewInfo):
                self._show_view_details(tag)
            elif isinstance(tag, SheetInfo):
                # Sheet selected - show sheet info
                self.panel_details.Children.Clear()
                title = TextBlock()
                title.Text = "Sheet: {} - {}".format(tag.sheet_number, tag.sheet_name)
                title.FontSize = 14
                title.FontWeight = System.Windows.FontWeights.Bold
                title.Foreground = Brushes.Black
                self.panel_details.Children.Add(title)

    def open_sheet_click(self, sender, e):
        """Open sheet button clicked"""
        sheet_id = sender.Tag

        try:
            sheet = self.doc.GetElement(sheet_id)
            if sheet:
                # Check if we need to prompt user
                if self.uidoc.ActiveView.Id != sheet_id:
                    result = MessageBox.Show(
                        "Open sheet {} - {}?".format(sheet.SheetNumber, sheet.Name),
                        "Open Sheet",
                        MessageBoxButton.YesNo,
                        MessageBoxImage.Question
                    )

                    if result == System.Windows.MessageBoxResult.Yes:
                        self.uidoc.ActiveView = sheet
                        self.status_text.Text = "Opened sheet {}".format(sheet.SheetNumber)
            else:
                MessageBox.Show("Sheet not found. It may have been deleted.", "Error", MessageBoxButton.OK, MessageBoxImage.Error)
        except Exception as ex:
            MessageBox.Show("Error opening sheet: {}".format(str(ex)), "Error", MessageBoxButton.OK, MessageBoxImage.Error)

    def select_reference_click(self, sender, e):
        """Select reference button clicked"""
        source_view_id, ref_element_id = sender.Tag

        try:
            # Check if view is open
            view = self.doc.GetElement(source_view_id)
            element = self.doc.GetElement(ref_element_id)

            if not view or not element:
                MessageBox.Show("View or reference not found.", "Error", MessageBoxButton.OK, MessageBoxImage.Error)
                return

            # Prompt to open view if not active
            if self.uidoc.ActiveView.Id != source_view_id:
                result = MessageBox.Show(
                    "The reference is in view '{}'. Open this view?".format(view.Name),
                    "Open View",
                    MessageBoxButton.YesNo,
                    MessageBoxImage.Question
                )

                if result == System.Windows.MessageBoxResult.Yes:
                    self.uidoc.ActiveView = view
                else:
                    return

            # Select the reference element
            from Autodesk.Revit.UI.Selection import Selection
            from System.Collections.Generic import List
            from Autodesk.Revit.DB import ElementId

            element_ids = List[ElementId]()
            element_ids.Add(ref_element_id)
            self.uidoc.Selection.SetElementIds(element_ids)

            self.status_text.Text = "Selected reference in {}".format(view.Name)

        except Exception as ex:
            MessageBox.Show("Error selecting reference: {}".format(str(ex)), "Error", MessageBoxButton.OK, MessageBoxImage.Error)

    def highlight_in_browser_click(self, sender, e):
        """Highlight view in project browser"""
        view_id = sender.Tag

        try:
            self.uidoc.ShowElements(view_id)
            self.status_text.Text = "Highlighted in Project Browser"
        except Exception as ex:
            MessageBox.Show("Error highlighting in browser: {}".format(str(ex)), "Error", MessageBoxButton.OK, MessageBoxImage.Error)

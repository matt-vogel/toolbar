# -*- coding: utf-8 -*-
"""Data collection and processing for View Reference Tracker"""
__author__ = 'Matt Vogel'

from Autodesk.Revit.DB import (
    FilteredElementCollector, ViewSheet, Viewport, View,
    ViewType, BuiltInCategory, ViewSection, ViewPlan,
    Element
)
from collections import defaultdict


class ViewInfo(object):
    """Data class to hold view information"""
    def __init__(self, view_id, view_name, view_type, detail_number=None):
        self.view_id = view_id
        self.view_name = view_name
        self.view_type = view_type
        self.detail_number = detail_number
        self.placement_count = 0  # How many times placed on sheets
        self.reference_count = 0  # How many references point to this view
        self.reference_count_non_sheet = 0  # References from non-sheet views
        self.placed_on_sheets = []  # List of (sheet_id, sheet_number, sheet_name, viewport_id)
        self.referenced_from = []  # List of ReferenceInfo objects

    def get_display_text(self):
        """Generate display text for tree view"""
        refs_text = str(self.reference_count)
        if self.reference_count_non_sheet > 0:
            refs_text = "{} sheet, {} other".format(
                self.reference_count - self.reference_count_non_sheet,
                self.reference_count_non_sheet
            )

        return "{} ({} placed, {} refs)".format(
            self.view_name,
            self.placement_count,
            refs_text if self.reference_count > 0 else "0"
        )


class ReferenceInfo(object):
    """Data class to hold reference information"""
    def __init__(self, source_view_id, source_view_name, source_sheet_id,
                 source_sheet_number, source_sheet_name, ref_element_id,
                 detail_number=None, is_on_sheet=True):
        self.source_view_id = source_view_id
        self.source_view_name = source_view_name
        self.source_sheet_id = source_sheet_id
        self.source_sheet_number = source_sheet_number
        self.source_sheet_name = source_sheet_name
        self.ref_element_id = ref_element_id
        self.detail_number = detail_number
        self.is_on_sheet = is_on_sheet


class SheetInfo(object):
    """Data class to hold sheet information"""
    def __init__(self, sheet_id, sheet_number, sheet_name):
        self.sheet_id = sheet_id
        self.sheet_number = sheet_number
        self.sheet_name = sheet_name
        self.views = []  # List of ViewInfo objects
        self.unreferenced_count = 0

    def get_display_text(self):
        """Generate display text for tree view"""
        unref_text = " [{}unreferenced]".format(self.unreferenced_count) if self.unreferenced_count > 0 else ""
        return "{} - {} ({} views){}".format(
            self.sheet_number,
            self.sheet_name,
            len(self.views),
            unref_text
        )


class ViewReferenceCollector(object):
    """Collects view placement and reference data from Revit model"""

    def __init__(self, doc):
        self.doc = doc
        self.sheets = {}  # Dict: sheet_id -> SheetInfo
        self.views = {}   # Dict: view_id -> ViewInfo
        self.view_to_sheet = {}  # Dict: view_id -> sheet_id (for views placed on sheets)
        self.unreferenced_views = []  # List of ViewInfo for views not on sheets or with 0 refs

    def collect_all_data(self):
        """Main method to collect all data"""
        self._collect_sheets_and_viewports()
        self._collect_references()
        self._identify_unreferenced_views()

    def collect_sheets_only(self):
        """Fast initial load - just sheets and view counts"""
        self._collect_sheets_and_viewports()

    def collect_references_for_view(self, view_id):
        """Lazy load references for a specific view"""
        if view_id not in self.views:
            return []

        view_info = self.views[view_id]
        if not view_info.referenced_from:
            # Collect references for this specific view
            self._collect_references_for_single_view(view_id)

        return view_info.referenced_from

    def _collect_sheets_and_viewports(self):
        """Collect all sheets and their viewports"""
        # Get all sheets
        all_sheets = FilteredElementCollector(self.doc).OfClass(ViewSheet).ToElements()

        for sheet in all_sheets:
            if sheet.IsTemplate:
                continue

            sheet_id = sheet.Id
            sheet_number = sheet.SheetNumber
            sheet_name = sheet.Name

            sheet_info = SheetInfo(sheet_id, sheet_number, sheet_name)
            self.sheets[sheet_id] = sheet_info

            # Get viewports on this sheet
            viewport_ids = sheet.GetAllViewports()

            for vp_id in viewport_ids:
                viewport = self.doc.GetElement(vp_id)
                view_id = viewport.ViewId
                view = self.doc.GetElement(view_id)

                # Skip certain view types
                if view.ViewType == ViewType.Legend:
                    continue

                # Get detail number from viewport
                detail_number = None
                detail_param = viewport.LookupParameter("Detail Number")
                if detail_param and not detail_param.IsReadOnly:
                    detail_number = detail_param.AsString()

                # Create or update ViewInfo
                if view_id not in self.views:
                    view_info = ViewInfo(view_id, view.Name, view.ViewType, detail_number)
                    self.views[view_id] = view_info
                else:
                    view_info = self.views[view_id]

                # Update placement info
                view_info.placement_count += 1
                view_info.placed_on_sheets.append((sheet_id, sheet_number, sheet_name, vp_id))

                # Track which sheet this view is on (for reference tracking)
                self.view_to_sheet[view_id] = sheet_id

                # Add view to sheet
                sheet_info.views.append(view_info)

        # Sort views on each sheet by detail number
        for sheet_info in self.sheets.values():
            sheet_info.views.sort(key=lambda v: (v.detail_number or "", v.view_name))

    def _collect_references(self):
        """Collect all section/callout/elevation references - OPTIMIZED"""
        # Collect all reference elements across the entire document at once
        # This is much faster than iterating through each view

        # Get all sections
        all_sections = FilteredElementCollector(self.doc)\
            .OfCategory(BuiltInCategory.OST_Sections)\
            .WhereElementIsNotElementType()\
            .ToElements()

        # Get all callouts
        all_callouts = FilteredElementCollector(self.doc)\
            .OfCategory(BuiltInCategory.OST_Callouts)\
            .WhereElementIsNotElementType()\
            .ToElements()

        # Get all elevation markers
        all_elevations = FilteredElementCollector(self.doc)\
            .OfCategory(BuiltInCategory.OST_Elev)\
            .WhereElementIsNotElementType()\
            .ToElements()

        # Process sections
        for section in all_sections:
            try:
                ref_view_id = section.ViewId
                if ref_view_id and ref_view_id in self.views:
                    # Get the view this section is in
                    owner_view_id = section.OwnerViewId
                    source_view = self.doc.GetElement(owner_view_id)
                    if source_view and not source_view.IsTemplate:
                        source_is_on_sheet = owner_view_id in self.view_to_sheet
                        self._add_reference(ref_view_id, source_view, section.Id, source_is_on_sheet)
            except:
                pass

        # Process callouts
        for callout in all_callouts:
            try:
                ref_view_id = callout.ViewId
                if ref_view_id and ref_view_id in self.views:
                    owner_view_id = callout.OwnerViewId
                    source_view = self.doc.GetElement(owner_view_id)
                    if source_view and not source_view.IsTemplate:
                        source_is_on_sheet = owner_view_id in self.view_to_sheet
                        self._add_reference(ref_view_id, source_view, callout.Id, source_is_on_sheet)
            except:
                pass

        # Process elevations
        for elevation in all_elevations:
            try:
                # Elevation markers can reference multiple views
                owner_view_id = elevation.OwnerViewId
                source_view = self.doc.GetElement(owner_view_id)
                if source_view and not source_view.IsTemplate:
                    source_is_on_sheet = owner_view_id in self.view_to_sheet

                    for i in range(4):  # Elevation markers can have up to 4 views
                        try:
                            ref_view_id = elevation.GetViewId(i)
                            if ref_view_id and ref_view_id in self.views:
                                self._add_reference(ref_view_id, source_view, elevation.Id, source_is_on_sheet)
                        except:
                            pass
            except:
                pass

    def _collect_references_for_single_view(self, target_view_id):
        """Collect references that point to a specific view (lazy loading)"""
        all_views = FilteredElementCollector(self.doc).OfClass(View).ToElements()

        for source_view in all_views:
            if source_view.IsTemplate:
                continue

            source_view_id = source_view.Id
            source_is_on_sheet = source_view_id in self.view_to_sheet

            # Check sections, callouts, elevations in this view
            self._collect_section_references(source_view, source_is_on_sheet, target_view_id)
            self._collect_callout_references(source_view, source_is_on_sheet, target_view_id)
            self._collect_elevation_references(source_view, source_is_on_sheet, target_view_id)

    def _collect_section_references(self, source_view, source_is_on_sheet, target_view_id=None):
        """Collect section references from a view"""
        try:
            sections = FilteredElementCollector(self.doc, source_view.Id)\
                .OfCategory(BuiltInCategory.OST_Sections)\
                .WhereElementIsNotElementType()\
                .ToElements()

            for section in sections:
                # Check if this section references another view
                ref_view_id = None
                try:
                    ref_view_id = section.ViewId
                except:
                    pass

                if ref_view_id and ref_view_id in self.views:
                    # If target_view_id is specified, only process that view
                    if target_view_id and ref_view_id != target_view_id:
                        continue

                    self._add_reference(ref_view_id, source_view, section.Id, source_is_on_sheet)
        except:
            pass  # View might not support this category

    def _collect_callout_references(self, source_view, source_is_on_sheet, target_view_id=None):
        """Collect callout references from a view"""
        try:
            callouts = FilteredElementCollector(self.doc, source_view.Id)\
                .OfCategory(BuiltInCategory.OST_Callouts)\
                .WhereElementIsNotElementType()\
                .ToElements()

            for callout in callouts:
                # Check if this callout references another view
                ref_view_id = None
                try:
                    ref_view_id = callout.ViewId
                except:
                    pass

                if ref_view_id and ref_view_id in self.views:
                    if target_view_id and ref_view_id != target_view_id:
                        continue

                    self._add_reference(ref_view_id, source_view, callout.Id, source_is_on_sheet)
        except:
            pass

    def _collect_elevation_references(self, source_view, source_is_on_sheet, target_view_id=None):
        """Collect elevation marker references from a view"""
        try:
            elevations = FilteredElementCollector(self.doc, source_view.Id)\
                .OfCategory(BuiltInCategory.OST_Elev)\
                .WhereElementIsNotElementType()\
                .ToElements()

            for elevation in elevations:
                # Elevation markers can reference multiple views
                # We need to check each elevation view
                try:
                    elevation_marker = elevation
                    # Get views associated with this marker
                    for i in range(4):  # Elevation markers can have up to 4 views
                        try:
                            ref_view_id = elevation_marker.GetViewId(i)
                            if ref_view_id and ref_view_id in self.views:
                                if target_view_id and ref_view_id != target_view_id:
                                    continue

                                self._add_reference(ref_view_id, source_view, elevation.Id, source_is_on_sheet)
                        except:
                            pass
                except:
                    pass
        except:
            pass

    def _add_reference(self, target_view_id, source_view, ref_element_id, source_is_on_sheet):
        """Add a reference to a view"""
        view_info = self.views[target_view_id]

        # Get source sheet info if available
        source_sheet_id = None
        source_sheet_number = ""
        source_sheet_name = ""
        detail_number = None

        if source_is_on_sheet:
            source_sheet_id = self.view_to_sheet.get(source_view.Id)
            if source_sheet_id:
                sheet = self.doc.GetElement(source_sheet_id)
                source_sheet_number = sheet.SheetNumber
                source_sheet_name = sheet.Name

                # Try to get detail number for the source viewport
                viewports = sheet.GetAllViewports()
                for vp_id in viewports:
                    vp = self.doc.GetElement(vp_id)
                    if vp.ViewId == source_view.Id:
                        detail_param = vp.LookupParameter("Detail Number")
                        if detail_param:
                            detail_number = detail_param.AsString()
                        break

        # Create reference info
        ref_info = ReferenceInfo(
            source_view.Id,
            source_view.Name,
            source_sheet_id,
            source_sheet_number,
            source_sheet_name,
            ref_element_id,
            detail_number,
            source_is_on_sheet
        )

        view_info.referenced_from.append(ref_info)
        view_info.reference_count += 1

        if not source_is_on_sheet:
            view_info.reference_count_non_sheet += 1

    def _identify_unreferenced_views(self):
        """Identify views that are unreferenced"""
        # Views placed on sheets but with 0 references
        for view_info in self.views.values():
            if view_info.reference_count == 0:
                self.unreferenced_views.append(view_info)

        # Views not placed on any sheet
        all_views = FilteredElementCollector(self.doc).OfClass(View).ToElements()
        for view in all_views:
            if view.IsTemplate:
                continue
            if view.ViewType == ViewType.Legend:
                continue
            if view.ViewType == ViewType.ProjectBrowser:
                continue
            if view.ViewType == ViewType.SystemBrowser:
                continue

            view_id = view.Id
            if view_id not in self.views:
                # This view is not placed on any sheet
                view_info = ViewInfo(view_id, view.Name, view.ViewType)
                view_info.placement_count = 0
                view_info.reference_count = 0
                self.unreferenced_views.append(view_info)

        # Update sheet unreferenced counts
        for sheet_info in self.sheets.values():
            sheet_info.unreferenced_count = sum(1 for v in sheet_info.views if v.reference_count == 0)

#
# This file is part of ampy.
#
# Copyright (C) 2013-2017 The University of Waikato, Hamilton, New Zealand.
#
# Authors: Shane Alcock
#          Brendon Jones
#
# All rights reserved.
#
# This code has been developed by the WAND Network Research Group at the
# University of Waikato. For further information please see
# http://www.wand.net.nz/
#
# ampy is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# ampy is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ampy; if not, write to the Free Software Foundation, Inc.
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# Please report any bugs, questions or comments to contact@wand.net.nz
#

import json
import operator

from libampy.ampmesh import AmpMesh
from libampy.viewmanager import ViewManager
from libampy.nntsc import NNTSCConnection
from libampy.cache import AmpyCache
from libampy.eventmanager import EventManager
from libampy.asnnames import ASNManager

from libnntscclient.logger import *

from libampy.collections.ampicmp import AmpIcmp
from libampy.collections.amptraceroute import AmpTraceroute, AmpAsTraceroute
from libampy.collections.amptraceroute import AmpTraceroutePathlen
from libampy.collections.ampdns import AmpDns
from libampy.collections.amphttp import AmpHttp
from libampy.collections.amptcpping import AmpTcpping
from libampy.collections.ampthroughput import AmpThroughput
from libampy.collections.ampudpstream import AmpUdpstream
from libampy.collections.ampyoutube import AmpYoutube
from libampy.collections.ampfastping import AmpFastping
from libampy.collections.ampexternal import AmpExternal
from libampy.collections.ampsip import AmpSip
from libampy.collections.rrdsmokeping import RRDSmokeping

class Ampy(object):
    """
    Primary class for ampy, which acts as a bridge between the Cuz website
    and the various database backends that support the site, particularly
    the NNTSC database.

    This class implements all of the external API methods required by the
    Cuz website. The website should only need to import this module to
    access all of the ampy functionality.

    API Functions
    -------------
    start:
        Prepares Ampy for operation. Must be called prior to calling any
        other API functions.
    get_collections:
        Fetches a list of supported collections from the NNTSC database.
    get_meshes:
        Fetches a list of available AMP meshes.
    get_amp_sources:
        Fetches a list of available AMP source sites.
    get_amp_destinations:
        Fetches a list of available AMP destination sites.
    get_matrix_members:
        Fetches all the sites that are needed to construct a matrix.
    get_amp_site_info:
        Fetches detailed information about an AMP mesh member.
    get_amp_mesh_info:
        Fetches detailed information about an AMP mesh.
    get_recent_data:
        Fetches aggregated values for a time period starting at now and
        going back a specified duration, i.e. the most recent measurements.
    get_historic_data:
        Fetches aggregated time series data for a specified time period.
    get_view_legend:
        Constructs suitable legend labels for each group present in a view.
    get_selection_options:
        Given a set of chosen group properties, returns a set of possible
        options for the next group property.
    test_graphtab_view:
        Given an existing view for another collection, checks if there is
        a valid equivalent view for a collection.
    create_graphtab_view:
        Given an existing view for another collection, creates an
        equivalent view for a collection.
    get_event_view:
        Given a stream id that an event was detected on, creates a suitable
        view for displaying that event on a graph.
    modify_view:
        Adds or removes a group from an existing view.
    get_matrix_data:
        Fetches all data to populate a matrix constructed from AMP meshes.
    get_view_events:
        Fetches all events for streams belonging to a given view that
        occurred over a certain time period.
    get_single_event:
        Fetches a specific event that matches a given stream ID and event ID.
    get_event_groups:
        Fetches all event groups for a specified time period.
    get_event_group_members:
        Fetches all events that belong to a specified event group.
    get_asn_names:
        Translates a list of ASNs into their corresponding names.
    get_matching_asns:
        Fetches known ASNs that contain a substring in either the ASN or the
        AS name.
    get_matching_sources:
        Fetches known AMP sources that contain a substring in their AMP name.
    get_matching_targets:
        Fetches known AMP targets that contain a substring in their AMP name.
    get_event_filter:
        Fetches an event filter for a given user.
    modify_event_filter:
        Creates, deletes or changes an event filter.
    get_users:
        Fetch a list of all users.
    get_user:
        Fetch information about a single user.
    add_user:
        Add a new user.
    update_user:
        Update the details of an existing user.
    delete_user:
        Delete an existing user.
    enable_user:
        Enable an existing user so they can login.
    disable_user:
        Disable an existing user so they can no longer login.
    """

    def __init__(self, ampdbconf, viewconf, nntscconf, eventconf,
            asdbconf=None):
        """
        Init function for the Ampy class.

        Parameters:
          ampdbconf -- config for connecting to the AMP mesh database.
          viewconf -- config for connecting to the Views database.
          nntscconf -- config for connecting to the NNTSC exporter.
          eventconf -- config for connecting to the Events database.

        Refer to the AmpyDatabase class for more details on the
        configuration required for connecting to databases via ampy.

        Refer to the NNTSCConnection class for more details on the
        configuration required for connecting to a NNTSC exporter.
        """
        self.ampmesh = AmpMesh(ampdbconf)
        self.viewmanager = ViewManager(viewconf)
        self.nntscconfig = nntscconf
        self.cache = AmpyCache(12)
        self.eventmanager = EventManager(eventconf)
        self.asmanager = ASNManager(asdbconf, self.cache)

        self.collections = {}
        self.savedcoldata = {}
        self.started = False

    def start(self):
        """
        Ensures ampy is ready for subsequent API calls by populating the
        internal list of available collections.

        Must be called once the Ampy instance is instantiated, i.e. before
        making any other API calls. start() only needs to be called once
        per Ampy instance.

        Returns:
          None if the collection query fails, otherwise returns the number
          of supported collections.
        """
        # Only fetch the collections the first time this is called.
        if self.started:
            return len(self.savedcoldata)

        retval = self._query_collections()
        if retval is None:
            return None
        self.started = True
        return retval

    def get_collections(self):
        """
        Fetches a list of collections available via this Ampy instance.

        Returns:
          a list of collection names
        """
        return list(self.savedcoldata.keys())

    def get_meshes(self, endpoint, amptest=None, site=None, public=None):
        """
        Fetches all source or destination meshes.

        Parameters:
          endpoint -- either "source" or "destination", depending on
                      which meshes are required.
          amptest -- limit results to meshes that are targets for a given test.
                     If None, no filtering of meshes is performed. This
                     parameter is ignored if querying for source meshes.
                     Possible values include 'latency', 'hops', 'dns', 'http'
                     and 'tput'.
          site -- optional argument to filter only meshes that this
                  site is a member of.

        Returns:
          a list of dictionaries that describe the available meshes or
          None if an error occurs while querying for the meshes.

        Mesh dictionary format:
          The returned dictionaries should contain three elements:
            name -- the internal unique identifier string for the mesh
            longname -- a string containing a mesh name that is more
                        suited for public display
            description -- a string describing the purpose of the mesh in
                           reasonable detail
        """
        return self.ampmesh.get_meshes(endpoint, amptest, site, public)

    def get_matrix_members(self, sourcemesh, destmesh):
        """
        Fetches all the sites that are needed to construct a matrix.

        Parameters:
          sourcemesh -- the mesh that represents the test sources
          destmesh -- the mesh that represents the test targets

        Returns:
          a tuple containing two lists: the first is the list of sources,
          the second is the list of targets.
          Returns None if the query fails.
        """
        sources = self.ampmesh.get_mesh_sources(sourcemesh)
        if sources is None:
            return None

        dests = self.ampmesh.get_mesh_destinations(destmesh)
        if dests is None:
            return None

        return (sources, dests)

    def get_amp_sites(self):
        """
        Fetches all known AMP sites.

        Parameters:
          None

        Returns:
          a list of all AMP sites
        """
        return self.ampmesh.get_sites()

    def get_amp_sources(self):
        """
        Fetches all known AMP sources.

        Parameters:
          None

        Returns:
          a list of all AMP sources
        """
        return self.ampmesh.get_sources()

    def get_amp_destinations(self):
        """
        Fetches all known AMP destinations.

        Parameters:
          None

        Returns:
          a list of all AMP destinations
        """
        return self.ampmesh.get_destinations()

    def get_amp_meshless_sites(self):
        return self.ampmesh.get_meshless_sites()

    def get_amp_mesh_destinations(self, mesh):
        """
        Fetches all AMP sites that belong to the given mesh and that are
        valid test destinations.

        Parameters:
          mesh -- the mesh to which destinations should belong

        Returns:
          a list of all AMP destinations in the mesh
        """
        return self.ampmesh.get_mesh_destinations(mesh)

    def get_amp_site_info(self, sitename):
        """
        Fetches details about a particular AMP mesh member.

        Parameters:
          sitename -- the name of the mesh member to query for

        Returns:
          a dictionary containing detailed information about the site.

        The resulting dictionary contains the following items:
          ampname -- a string containing the internal name for the site
          longname -- a string containing a site name that is suitable for
                      public display
          location -- a string containing the city or data-centre where the
                      amplet is located (if there is one for that site)
          description -- a string containing any additional descriptive
                         information about the site
          active -- a boolean flag indicating whether the site is currently
                    active
        """
        return self.ampmesh.get_site_info(sitename)

    def get_amp_mesh_info(self, meshname):
        """
        Fetches details about a particular AMP mesh.

        Parameters:
          meshname -- the name of the mesh to query for

        Returns:
          a dictionary containing detailed information about the site.

        The resulting dictionary contains the following items:
          meshname -- a string containing the internal name for the site
          longname -- a string containing a mesh name that is suitable for
                      public display
          description -- a string containing any additional descriptive
                         information about the mesh
          src -- a boolean flag indicating whether this is a source mesh
          dst -- a boolean flag indicating whether this is a destination mesh
          active -- a boolean flag indicating whether the mesh is currently
                    active
        """
        return self.ampmesh.get_mesh_info(meshname)

    def get_amp_source_schedule(self, source, schedule_id=None):
        """
        Fetch all scheduled tests that originate at this source.

        Parameters:
          source -- the name of the source site/mesh to fetch the schedule for

        Returns:
          a list containing the scheduled tests from this source
        """
        return self.ampmesh.get_source_schedule(source, schedule_id)

    def get_amp_schedule_by_id(self, schedule_id):
        return self.ampmesh.get_schedule_by_id(schedule_id)

    def schedule_new_amp_test(self, settings):
        return self.ampmesh.schedule_new_test(settings)

    def update_amp_test(self, schedule_id, settings):
        return self.ampmesh.update_test(schedule_id, settings)

    def is_amp_test_enabled(self, schedule_id):
        return self.ampmesh.get_enable_status(schedule_id)

    def enable_amp_test(self, schedule_id):
        return self.ampmesh.enable_disable_test(schedule_id, True)

    def disable_amp_test(self, schedule_id):
        return self.ampmesh.enable_disable_test(schedule_id, False)

    def delete_amp_test(self, schedule_id):
        return self.ampmesh.delete_test(schedule_id)

    def get_amp_site_endpoints(self):
        return self.ampmesh.get_site_endpoints()

    def add_amp_test_endpoints(self, schedule_id, src, dst):
        return self.ampmesh.add_endpoints_to_test(schedule_id, src, dst)

    def delete_amp_test_endpoints(self, schedule_id, src, dst):
        return self.ampmesh.delete_endpoints(schedule_id, src, dst)

    def update_amp_site(self, ampname, longname, loc, description):
        return self.ampmesh.update_site(ampname, longname, loc, description)

    def update_amp_mesh(self, ampname, longname, description, public, issource):
        return self.ampmesh.update_mesh(ampname, longname, description, public,
                issource)

    def add_amp_site(self, ampname, longname, location, description):
        return self.ampmesh.add_site(ampname, longname, location, description)

    def add_amp_mesh(self, ampname, longname, description, public, issource):
        return self.ampmesh.add_mesh(ampname, longname, description, public,
                issource)

    def delete_amp_site(self, ampname):
        return self.ampmesh.delete_site(ampname)

    def delete_amp_mesh(self, ampname):
        return self.ampmesh.delete_mesh(ampname)

    def add_amp_mesh_member(self, meshname, ampname):
        return self.ampmesh.add_mesh_member(meshname, ampname)

    def delete_amp_mesh_member(self, meshname, ampname):
        return self.ampmesh.delete_mesh_member(meshname, ampname)

    def get_flagged_mesh_tests(self, meshname):
        return self.ampmesh.get_flagged_mesh_tests(meshname)

    def flag_mesh_test(self, meshname, test):
        return self.ampmesh.flag_mesh_test(meshname, test)

    def unflag_mesh_test(self, meshname, test):
        return self.ampmesh.unflag_mesh_test(meshname, test)


    def get_recent_data(self, viewstyle, view_id, duration, detail):
        """
        Fetches summary statistics for each label within a view that
        summarise the most recent measurements collected for each label.

        The resulting data will be aggregated into a single value for the
        entire time period, making this function best suited for summary
        statistics (e.g. matrix tooltips) rather than drawing time series
        graphs.

        See get_historic_data if you need time series data.

        Parameters:
          viewstyle -- the name of the collection that the view belongs to.
          view_id -- the view to fetch recent data for.
          duration -- the length of the time period to fetch data for, in
                      seconds.
          detail --  the level of detail, e.g. 'full', 'matrix'. This will
                     determine which data columns are queried and how they
                     are aggregated.

        Returns:
          a tuple containing two elements. The first is a dictionary
          mapping label identifier strings to a list containing the
          summary statistics for that label. The second is a list of
          labels which failed to fetch recent data due to a database query
          timeout.

        """
        recentdata = {}
        timeouts = []

        # Most of the work here is finding all of the labels for the
        # view we're given.
        viewgroups = self._view_to_groups(viewstyle, view_id)
        if viewgroups is None:
            log("Failed to fetch recent data")
            return None

        for colname, vgs in viewgroups.items():
            col = self._getcol(colname)
            if col is None:
                log("Failed to create collection module %s" % (colname))
                return None

            alllabels = []
            for (gid, descr) in vgs:
                grouplabels = col.group_to_labels(gid, descr, True)
                if grouplabels is None:
                    log("Unable to convert group %d into stream labels" % (gid))
                    continue
                alllabels += grouplabels

            result = col.get_collection_recent(self.cache, alllabels,
                    duration, detail)

            if result is not None:
                recentdata.update(result[0])
                timeouts += result[1]

        return recentdata, timeouts


    def get_historic_data(self, viewstyle, view_id, start, end,
            detail, binsize=None):
        """
        Fetches aggregated time series data for each label within a view.

        Parameters:
          viewstyle -- the name of the collection that the view belongs to.
          view_id -- the view to fetch time series data for.
          start -- a timestamp indicating when the time series should begin.
          end -- a timestamp indicating when the time series should end.
          detail --  the level of detail, e.g. 'full', 'matrix'. This will
                     determine which data columns are queried and how they
                     are aggregated.
          binsize -- the minimum desired aggregation frequency. This is
                     automatically calculated based on the time period that
                     you asked for, but you can use this option to ensure
                     that the bins are not smaller than your expected data
                     frequency. Set to None if you do not have a suitable
                     minimum. Set to -1 if you want raw unaggregated data.

        Returns:
          a dictionary keyed by label where each value is a list containing
          the aggregated time series data for the specified time period.
          Returns None if an error occurs while fetching the data.

        """
        history = {}
        description = {}

        viewgroups = self._view_to_groups(viewstyle, view_id)
        if viewgroups is None:
            log("Failed to fetch historic data")
            return None

        for colname, vgs in viewgroups.items():
            col = self._getcol(colname)
            if col is None:
                log("Failed to create collection module %s" % (colname))
                return None

            # save the description so we can pass it back with the raw data
            if binsize is not None and binsize < 0:
                for gid, descr in vgs:
                    description[gid] = col.parse_group_description(descr)
                    description[gid]["collection"] = colname

            # Find all labels for this view and their corresponding streams
            alllabels = []
            for (gid, descr) in vgs:
                grouplabels = col.group_to_labels(gid, descr, True)
                if grouplabels is None:
                    log("Unable to convert group %d into stream labels" % (gid))
                    continue
                alllabels += grouplabels
            colhist = col.get_collection_history(self.cache, alllabels, start,
                    end, detail, binsize)

            if colhist is None:
                log("Error while fetching historical data for %s" % (colname))
                return None

            history.update(colhist)

        # if binsize is -1 then this is a raw data fetch and we need to
        # return some better descriptions of the groups
        if binsize is not None and binsize < 0:
            return description, history
        return history

    def get_view_legend(self, viewstyle, view_id):
        """
        Generates appropriate legend label strings for each group in a given
        view.

        Parameters:
          viewstyle -- the name of the collection that the view belongs to.
          view_id -- the view to generate legend labels for.

        Returns:
          a list of dictionaries, where each dictionary describes a group.
          Returns None if an error occurs.

        Group dictionary format:
          A group dictionary contains three elements:
            group_id -- a unique string identifying the group
            label -- the text to display on the legend for the group
            lines -- a list of 'lines' that will be drawn on the graph for
                     the group

          A line is a tuple, containing the following three elements:
            * a unique string identifying the line (includes the group id)
            * text to display if the line is moused over on the graph or
              legend
            * a unique integer index that indicates which colour should be
              used to draw the line on a graph. Indexes start at zero for
              the first line and increment from there.

        """
        viewgroups = self._view_to_groups(viewstyle, view_id)
        if viewgroups is None:
            log("Failed to generate legend")
            return None

        legend = []

        # What we need:
        # A set of 'legend' entries, one per group
        # For each entry, we also need a set of 'lines', one per group member
        nextlineid = 0

        # Sort the groups in the view by collection then description.
        # This ensures that A) the legend will be in a consistent order
        # and B) the ordering is more obvious to the user (i.e. alphabetical
        # starting with the first group property)
        colkeys = list(viewgroups.keys())
        colkeys.sort()

        for colname in colkeys:
            col = self._getcol(colname)
            if col is None:
                log("Failed to create collection module %s" % (colname))
                return None

            colgroups = viewgroups[colname]
            colgroups = sorted(colgroups, key=operator.itemgetter(1))

            for gid, descr in colgroups:
                added = self._add_legend_item(legend, col, gid, descr, \
                        nextlineid)
                nextlineid += added

        return legend

    def get_full_selection_options(self, collection):
        """
        Return a list of all the stream properties for a collection.

        Parameters:
          collection -- the name of the collection to fetch properties for.

        Returns:
            a list of all the stream properties for the given collection
        """
        col = self._getcol(collection)
        if col is None:
            log("Error while fetching selection options")
            return None

        return col.streamproperties

    def get_selection_options(self, collection, selected, term, page, pagesize=30):
        """
        Given a set of known stream properties, finds the next unknown
        stream property where there is more than one choice available
        and returns a list of available options for that property. Any
        stream properties along the way that have only one possible choice
        are also returned.

        This is primarily used to populate dropdown lists on the modal
        dialogs for selecting what series to display on a graph.

        Selection options are divided into "pages", which are used to return a
        manageable number of options at a time. This allows callers to
        iteratively load more options as the user scrolls, rather than
        trying to load and insert all of the possible options into a dropdown
        at once which can be quite laggy if there are many possible options
        to present.

        Parameters:
          collection -- the name of the collection to use to interpret
                        the options.
          selected -- a list containing the stream properties that
                      have already been selected, e.g. the choices already
                      made on the modal dialog, in order.
          term -- only options containing the 'term' string will be returned.
                  Set to "" to match all options.
          page -- a *string* representing the index of the page to return.
                  Pages are indexed starting from "1".
          pagesize -- the number of options to include in a page.

        Returns:
          a dictionary where the key is a stream property and the value is
          a dictionary of possible choices for that stream property, given the
          properties already chosen in the 'selected' dictionary. The 'choices'
          dictionary contains two items:
            - 'maxitems', which lists the total number of options available for
              this property
            - 'items', a list of dictionaries describing each item. There are
              two fields in the dictionary: 'text' and 'id'.

          Returns None if an error occurs while fetching the selection
          options.
        """

        col = self._getcol(collection)
        if col is None:
            log("Error while fetching selection options")
            return None

        seldict = col.create_properties_from_list(selected,
                col.streamproperties)
        if seldict is None:
            log("Unable to understand selected options")
            return None

        # The collection module does most of the work here
        options = col.get_selections(seldict, term, page, pagesize, False)
        return options



    def test_graphtab_view(self, viewstyle, tabcollection, view_id):
        """
        Checks whether it would be possible to generate a valid view that
        is equivalent to a view from another related collection.

        Used to determine which 'related' collections should be included
        in the quick-switch tabs on the right of a graph.

        Essentially, this function attempts to convert the group
        descriptions from the original view into group descriptions for
        the current collection.

        If any view group is successfully translated to the new collection,
        this is considered a success even if other groups cannot be
        translated.

        Parameters:
          viewstyle -- the name of the collection that the original view
                        belongs to.
          tabcollection -- the name of the collection that the view is to
                           be translated to.
          view_id -- the ID number of the view that is to be translated.

        Returns:
          True if the view can be translated to the new collection.
          False if the view cannot be translated.
          None if an error occurs while evaluating the translation.

        Note:
          If viewstyle and tabcollection are the same, this function
          should ALWAYS return True.
        """

        if viewstyle == tabcollection:
            return True

        groups = self._view_to_groups(viewstyle, view_id)
        if groups is None:
            log("Error while constructing tabview")
            return None

        # Make sure our target collection is also up-to-date
        tabcol = self._getcol(tabcollection)
        if tabcol is None:
            log("Error while constructing tabview")
            return None

        maxgroups = tabcol.get_maximum_view_groups()

        totalgroups = 0
        matched = 0

        for colname, vgs in groups.items():
            col = self._getcol(colname)
            if col is None:
                log("Error while getting original collection %s" % (colname))
                return None

            for gid, descr in vgs:
                # Don't allow switching to a view which can only show 1 group
                totalgroups += 1
                if totalgroups > maxgroups:
                    return False

                # Translate each group in turn
                grouprule = col.parse_group_description(descr)

                tabrule = tabcol.translate_group(grouprule)
                if tabrule is None:
                    continue

                labels = tabcol.group_to_labels('tabcheck', tabrule, True)
                for lab in labels:
                    # We can bail as soon as we get one group with a stream
                    if len(lab['streams']) > 0:
                        matched += 1
                        break

        if matched == len(groups):
            return True

        # If we get here, none of the translated groups would match any
        # streams in the database
        return False

    def create_graphtab_view(self, viewstyle, tabcollection, view_id):
        """
        Creates a new view for a collection based on an existing view
        for another collection.

        This is used to construct the view to be displayed if a user
        clicks on a 'related' graph tab while looking at a graph.

        Essentially, this function converts the group descriptions from the
        original view into group descriptions for the current collection.
        If a group cannot be converted, it will not be included on the
        new graph.

        Parameters:
          viewstyle -- the name of the collection that the original view
                        belongs to.
          tabcollection -- the name of the collection that the view is to
                           be translated to.
          view_id -- the ID number of the view that is to be translated.

        Returns:
            The ID number of the new view.
            Returns None if an error occurs while creating the new view or
            if none of the groups from the original view can be represented
            in the specified new collection.

        Note:
          If viewstyle and tabcollection are the same, this function should
          ALWAYS return the view_id that was passed in.
        """
        if viewstyle == tabcollection:
            return view_id

        groups = self._view_to_groups(viewstyle, view_id)
        if groups is None:
            log("Error while constructing tabview")
            return None

        # Make sure our target collection is also up-to-date
        tabcol = self._getcol(tabcollection)
        if tabcol is None:
            log("Error while constructing tabview")
            return None

        # Translate each group in turn
        tabgroups = set()

        for colname, vgs in groups.items():
            col = self._getcol(colname)
            if col is None:
                log("Error while getting original collection %s" % (colname))
                return None

            for gid, descr in vgs:
                grouprule = col.parse_group_description(descr)

                tabrule = tabcol.translate_group(grouprule)
                if tabrule is None:
                    continue

                tabid = self.viewmanager.get_group_id(tabcollection, tabrule)
                if tabid is None:
                    continue

                tabgroups.add(tabid)

        # If no groups were successfully translated to the new collection,
        # bail as we have nothing to draw on the graph.
        # Normally, this wouldn't happen as someone should have called
        # test_graphtab_view before drawing the tab that would trigger this
        # function call but you can never predict how people will abuse
        # this API in the future
        if len(tabgroups) == 0:
            log("Unable to create tabview %s to %s for view %s" % \
                    (viewstyle, tabcollection, view_id))
            log("No valid groups were found for new tab")
            return None

        # View groups should always be in sorted order
        tabgroups = list(tabgroups)
        tabgroups.sort()

        # Create ourselves a new view
        tabview = self.viewmanager.get_view_id(tabcol.viewstyle, \
                tabgroups)
        if tabview is None:
            log("Unable to create tabview %s to %s for view %s" % \
                    (collection, tabcollection, view_id))
            log("Could not create new view")
            return None

        return tabview

    def get_stream_properties(self, collection, stream):
        col = self._getcol(collection)
        if col is None:
            log("Error while fetching stream properties")
            return None

        # Find the stream in our stream hierarchy
        streamprops = col.find_stream(stream)
        if streamprops is None:
            log("Error while fetching stream properties")
            log("Stream %s does not exist for collection %s" % \
                    (stream, collection))
            return None

        return streamprops

    def get_event_view(self, collection, stream):
        """
        Given a stream that an event was detected on by netevmon, generates
        a suitable view for showing the event on a graph.

        This is used to create links to graphs from events shown on the
        dashboard. Events have no concept of views or view groups; instead
        we only have the ID of *one* of the streams that contributed to the
        time series that the event was detected on. Therefore, we need to
        be able to convert the single stream into a group that covers all
        of the streams that contributed to the event time series.

        Parameters:
          collection -- the name of the collection that the stream
                        belongs to.
          stream -- the ID of the stream that the event was detected on.

        Returns:
          the ID of the view generated for that stream

        """

        # Check if we have a cache entry for this stream
        cachedview = self.cache.search_stream_view(stream)
        if cachedview is not None:
            # Reset the cache timeout
            self.cache.store_stream_view(stream, cachedview)
            return cachedview

        if collection == "amp-latency":
            possibles = ['amp-icmp', 'amp-dns', 'amp-tcpping', 'amp-fastping']
        else:
            possibles = [collection]

        streamprops = None
        for c in possibles:
            col = self._getcol(c)
            if col is None:
                continue

            # Find the stream in our stream hierarchy
            streamprops = col.find_stream(stream)
            if streamprops is not None:
                collection = c
                break

        if streamprops is None:
            log("Error while creating event view")
            log("Stream %s does not exist for collection %s" % \
                    (stream, collection))
            return None

        # Convert the stream properties into a group description that we can
        # use to create a view. Note that the group may include other streams
        # in addition to the one we are looking for -- this is intentional.
        eventgroup = col.create_group_description(streamprops)
        if eventgroup is None:
            log("Error while creating event view")
            log("Unable to generate group for stream id %s (%s)" % \
                    (stream, collection))
            return None

        view = self.viewmanager.add_groups_to_view(col.viewstyle, collection, \
                0, [eventgroup])

        # Put the view in the cache for future lookups
        self.cache.store_stream_view(stream, view)
        return view

    def modify_view(self, collection, view_id, viewstyle, action, options):
        """
        Adds or removes a group from an existing view.

        Parameters:
          collection -- if adding groups, this is the name of the
                        collection that the new groups belong to. If
                        removing a group, this is the style of the view
                        that is being removed from.
          view_id -- the ID number of the view to be modified
          action -- either "add" if adding a group or "del" if removing one.
          options -- if adding a group, this is an ordered list of group
                     properties describing the group to add. If removing a
                     group, this is a list containing the ID of the group to
                     be removed.

        Returns:
          the ID of the resulting modified view.
          If the view is unchanged, the original view ID will be returned.
          None if an error occurs while creating the new view.

        Note that the options parameter is always a list. In the case of
        adding a group, the options list should be a complete list of group
        properties in the order that they appear in the collection's group
        properties list. For example, adding an amp-icmp group would require
        options to be a list containing a source, a destination, a packet
        size and an address family (in that order).

        In the case of removing a group, the list should contain only one
        item: the group ID of the group to be removed.

        """

        if len(options) == 0:
            return view_id


        if action == "add":
            col = self._getcol(collection, False)
            if col is None:
                return None
            # Allow options to be specified as a list or a dictionary. The
            # list format requires knowledge of special formatting for some
            # fields (e.g. DNS flags) that other code doesn't know about.
            # Using create_group_description() lets the collection specific
            # code do all the formatting work for us.
            if isinstance(options, dict):
                newgroup = col.create_group_description(options)
            else:
                newgroup = col.create_group_from_list(options)
            if newgroup is None:
                return view_id

            # TODO: what should we do if maxgroups > 1, i.e. finite and more
            # than one?
            if col.get_maximum_view_groups() == 1:
                view_id = 0

            return self.viewmanager.add_groups_to_view(viewstyle,
                    collection, view_id, [newgroup])
        elif action == "del":
            # XXX In theory, we could support removing more than one group?
            groupid = int(options[0])
            return self.viewmanager.remove_group_from_view(
                    viewstyle, view_id, groupid)
        else:
            return view_id

    def get_matrix_data(self, collection, viewstyle, options, duration):
        """
        Fetches all of the data required to populate an AMP matrix.

        Parameters:
          collection -- the name of the collection that the matrix
                        belongs to.
          viewstyle -- a string describing which data from the collection to
                       create a matrix for.
          options -- an ordered list describing which meshes should appear
                     in the matrix.
          duration -- the amount of recent data that should be queried for
                      each matrix cell, in seconds.

        Returns:
          a tuple containing five elements. The first is a dictionary
          mapping label identifier strings to a list containing the
          summary statistics for that label. The second is a list of
          labels which failed to fetch recent data due to a database query
          timeout. The third is a list of source mesh members. The fourth
          is a list of destination mesh members. The fifth is a dictionary
          containing the view ids for the graphs that each matrix cell
          will link to.

          Returns None if an error occurs while determining the matrix
          groups or querying for the matrix data.

        The options parameter must contain at least two items: the source
        and destination meshes for the matrix. Any subsequent items are
        ignored.

        """

        col = self._getcol(collection)
        if col is None:
            log("Error while fetching matrix data")
            return None

        # Work out which groups are required for this matrix
        matrixgroups = self._get_matrix_groups(col, viewstyle, options)
        if matrixgroups is None:
            return None

        groups, sources, destinations, views = matrixgroups

        fetcheddata = col.get_collection_recent(self.cache, groups, duration,
                "matrix")
        if fetcheddata is None:
            return None

        return fetcheddata[0], fetcheddata[1], sources, destinations, views

    def get_view_events(self, viewstyle, view_id, start, end):
        """
        Finds all events that need to be displayed for a given graph.

        Parameters:
          viewstyle -- the name of the collection that the view belongs to.
          view_id -- the ID of the view that is being shown on the graph.
          start -- the timestamp at the start of the time period shown on
                   the graph.
          end -- the timestamp at the end of the time period shown on the
                 graph.

        Returns:
          A list of events that were detected between 'start' and 'end'
          for all streams that are part of the view being displayed.
          Returns None if an error occurs while fetching the events.
        """

        groups = self._view_to_groups(viewstyle, view_id)
        if groups is None:
            log("Error while fetching events for a view")
            return None

        # Convert our view groups into a set of stream labels. In particular,
        # we will need the list of streams for each label as the events are
        # associated with stream IDs, not labels or groups or views.
        alllabels = []

        for colname, vgs in groups.items():
            col = self._getcol(colname)
            if col is None:
                log("Error while creating module for collection %s" % (colname))
                return None

            for gid, descr in vgs:
                grouplabels = col.group_to_labels(gid, descr, True)
                if grouplabels is None:
                    log("Unable to convert group %d into stream labels" % (gid))
                    continue

                for gl in grouplabels:
                    gl['groupid'] = gid
                alllabels += grouplabels

        return self.eventmanager.fetch_events(alllabels, start, end)

    def get_single_event(self, stream, eventid):
        """
        Finds the event that matches the given stream ID and event ID.

        Parameters:
          stream -- the ID of the stream that the requested event belongs to.
          eventid -- the ID of the event within that stream that is being
                     requested.

        Returns:
          a dictionary describing the event in question, or None if there is
          no such event or an error occurs while querying for it.
        """
        return self.eventmanager.fetch_specific_event(stream, eventid)

    def get_event_groups(self, start, end):
        """
        Finds all of the event groups that occured within a given time
        period.

        Parameters:
          start -- the timestamp at the start of the time period of
                   interest.
          end -- the timestamp at the end of the time period of interest.

        Returns:
          a list of event groups or None if an error occurs while querying
          the event database.
        """
        return self.eventmanager.fetch_groups(start, end)

    def get_event_group_members(self, eventgroupid):
        """
        Fetches the events that belong to a specific event group.

        Used to populate the event list when a user clicks on an event
        group on the dashboard.

        Parameters:
          groupid -- the unique id of the event group

        Returns:
          a list of events or None if there was an error while querying
          the event database.
        """
        members = self.eventmanager.fetch_event_group_members(eventgroupid)
        return members


    def get_asn_names(self, asns):
        """
        Looks up the names for a list of ASNs.

        Parameters:
          asns -- a list of AS numbers to find names for.

        Returns:
          a dictionary where the key is the ASN and the value is the
          name for the AS (according to our AS->name database) or None if the
          lookup fails.
        """
        result = {}
        toquery = set()
        for a in asns:
            if a == "-2":
                asname = "RFC 1918"
            elif a == "-1":
                asname = "No response"
            elif a == "0":
                asname = "Unknown"
            elif a == "Private":
                asname = "Private Address Space"
            else:
                aslabel = "AS" + a
                asname = self.cache.search_asname(aslabel)
                if asname is None:
                    toquery.add(aslabel)

            if asname is not None:
                result[a] = asname

        queried = self.asmanager.queryASNames(toquery)

        if queried is None:
            return None

        for a, n in queried.items():
            result[a] = n
        return result

    def get_matching_asns(self, pageindex=1, pagesize=30, term=""):
        """
        Looks up the names and ASNs for all known Autonomous Systems, on a
        page by page basis.

        Fetches are page-based because generally trying to load all of the
        ASNs at once tends to cripple a browser.

        Params:
          pageindex -- the index of the page to fetch, where 1 = the first N
                       ASNs
          pagesize -- the number of ASNs that appear on each page.
          term -- a substring that must appear in either the ASN or the AS
                  name.

        Returns:
          a dictionary of three items:
            'total': the total number of ASNs matching the provided term
            'pagesize': the requested page size
            'asns': a list of dicts describing the requested page's worth of
                    ASNs in the database. Each dict has two keys: 'id': the
                    ASN, and 'text': the AS name.
        """
        pindex = int(pageindex)
        result = self.asmanager.getASNsByName(pagesize, ((pindex-1) * pagesize),
                term)

        return {
            'total': result[0],
            'pagesize': pagesize,
            'asns': result[1]
        }

    def get_matching_sources(self, pageindex=1, pagesize=30, term=""):
        """
        Looks up the names of AMP sources that contain a given substring,
        on a page by page basis.

        Fetches are page-based to be consistent with the get_matching_asns
        function, but also to ensure we can scale to large numbers of AMP
        monitors.

        Params:
          pageindex -- the index of the page to fetch, where 1 = the first N
                       ASNs
          pagesize -- the number of sources that appear on each page.
          term -- a substring that must appear in the source's AMP name.

        Returns:
          a dictionary of three items:
            'total': the total number of sources matching the provided term
            'pagesize': the requested page size
            'sources': a list of dicts describing the requested page's worth of
                    AMP sources in the database. Each dict has two keys: 'id'
                    and 'text' which are both the AMP name of the source. The
                    duplication is to simplify populating dropdowns with the
                    returned sources.
        """

        pindex = int(pageindex)
        result = self.ampmesh.get_endpoints_by_name(True, pagesize,
                ((pindex-1) * pagesize), term)

        return {
            'total': result[0],
            'pagesize': pagesize,
            'sources': result[1]
        }

    def get_matching_targets(self, pageindex=1, pagesize=30, term=""):

        """
        Looks up the names of AMP targets that contain a given substring,
        on a page by page basis.

        Fetches are page-based to be consistent with the get_matching_asns
        function, but also to ensure we can scale to large numbers of AMP
        targets.

        Params:
          pageindex -- the index of the page to fetch, where 1 = the first N
                       ASNs
          pagesize -- the number of targets that appear on each page.
          term -- a substring that must appear in the target's AMP name.

        Returns:
          a dictionary of three items:
            'total': the total number of targets matching the provided term
            'pagesize': the requested page size
            'sources': a list of dicts describing the requested page's worth of
                    AMP targets in the database. Each dict has two keys: 'id'
                    and 'text' which are both the AMP name of the target. The
                    duplication is to simplify populating dropdowns with the
                    returned target.
        """

        pindex = int(pageindex)
        result = self.ampmesh.get_endpoints_by_name(False, pagesize,
                ((pindex-1) * pagesize), term)

        return {
            'total': result[0],
            'pagesize': pagesize,
            'targets': result[1]
        }

    def get_event_filter(self, username, filtername):
        """
        Looks up the event filter belonging to a given user and assigned
        a particular name.

        Parameters:
          username -- the user who owns the event filter
          filtername -- the name of the event filter

        Returns:
          a string containing stringified JSON that describes the matching
          filter or None if there is no filter for that username, filtername
          combination.
        """
        return self.eventmanager.get_event_filter(username, filtername)

    def modify_event_filter(self, method, username, filtername, filterstring):
        """
        Creates, modifies or deletes an event filter.

        Parameters:
          method -- either "add", "del" or "update", describing the operation
          to be performed.
          username -- the user who owns the event filter
          filtername -- the name of the event filter
          filterstring -- a string containing stringified JSON that will act
                          as the new filter for the given username, filtername
                          combination. If the method is "del", this parameter
                          is ignored.

        Returns:
          a tuple containing the username and filtername if the operation is
          successful. None if the operation is unsuccessful.
        """

        if method == "add":
            return self.eventmanager.create_event_filter(username, filtername, filterstring)

        if method == "del":
            return self.eventmanager.delete_event_filter(username, filtername)

        if method == "update":
            # the webpage doesn't know the user email address, and neither
            # does the eventmanager so we need to query for it here. An empty
            # email address will prevent alerts from being sent.
            email = None
            filter_ = json.loads(filterstring)
            if "email" in filter_:
                # True or False to enable/disable email alerting
                if filter_["email"]:
                    user = self.viewmanager.get_user(username)
                    if user and user["email"]:
                        email = user["email"]
            return self.eventmanager.update_event_filter(username, filtername,
                    filterstring, email)

        log("Invalid event filter modification type: %s" % (method))
        return None


    def _query_collections(self):
        """
        Fetches the set of available collections from NNTSC and updates
        the internal collection dictionary accordingly.

        Returns:
          the number of collections fetched or None if an error occurs
          while querying the database.
        """
        nntscdb = NNTSCConnection(self.nntscconfig)

        collections = nntscdb.request_collections()
        if collections is None:
            log("Failed to query NNTSC for existing collections")
            return None

        for col in collections:
            name = col['module'] + "-" + col['modsubtype']
            self.savedcoldata[name] = col['id']

        return len(list(self.savedcoldata.keys()))

    def _getcol(self, collection, updatestreams=True):
        """
        Finds the collection module that matches the provided collection
        name. If this Ampy instance does not have an instance of that
        collection module, one is created.

        When adding new collection modules, this function needs to be
        updated to ensure that Ampy will be able to utilise the new module.

        Parameters:
          collection -- the name of the collection required.

        Returns:
          an instance of the collection module matching the given name, or
          None if the name does not match any known collections.

        """
        newcol = None
        # If we have a matching collection, return that otherwise create a
        # new instance of the collection

        if collection in self.collections:
            col = self.collections[collection]
            if updatestreams:
                if col.update_streams() is None:
                    log("Failed to update stream map for collection %s" % \
                            (collection))
                    return None
            return col

        if collection not in self.savedcoldata:
            log("Collection type %s does not exist in NNTSC database" % \
                    (collection))
            return None

        colid = self.savedcoldata[collection]
        if collection == "amp-icmp":
            newcol = AmpIcmp(colid, self.viewmanager, self.nntscconfig)
        if collection == "amp-astraceroute":
            newcol = AmpAsTraceroute(colid, self.viewmanager, self.nntscconfig, self.asmanager)
        if collection == "amp-traceroute":
            newcol = AmpTraceroute(colid, self.viewmanager, self.nntscconfig, self.asmanager)
        if collection == "amp-traceroute_pathlen":
            newcol = AmpTraceroutePathlen(colid, self.viewmanager, self.nntscconfig, self.asmanager)
        if collection == "amp-dns":
            newcol = AmpDns(colid, self.viewmanager, self.nntscconfig)
        if collection == "amp-http":
            newcol = AmpHttp(colid, self.viewmanager, self.nntscconfig)
        if collection == "amp-tcpping":
            newcol = AmpTcpping(colid, self.viewmanager, self.nntscconfig)
        if collection == "amp-throughput":
            newcol = AmpThroughput(colid, self.viewmanager, self.nntscconfig)
        if collection == "amp-udpstream":
            newcol = AmpUdpstream(colid, self.viewmanager, self.nntscconfig)
        if collection == "amp-youtube":
            newcol = AmpYoutube(colid, self.viewmanager, self.nntscconfig)
        if collection == "amp-fastping":
            newcol = AmpFastping(colid, self.viewmanager, self.nntscconfig)
        if collection == "amp-external":
            newcol = AmpExternal(colid, self.viewmanager, self.nntscconfig)
        if collection == "amp-sip":
            newcol = AmpSip(colid, self.viewmanager, self.nntscconfig)
        if collection == "rrd-smokeping":
            newcol = RRDSmokeping(colid, self.viewmanager, self.nntscconfig)

        if newcol is None:
            log("Unknown collection type: %s" % (collection))
            return None

        self.collections[collection] = newcol

        if updatestreams:
            if newcol.update_streams() is None:
                log("Failed to update stream map for collection %s" % \
                        (collection))
                return None

        return newcol

    def _view_to_groups(self, viewstyle, view_id):
        """
        Internal utility function that finds the set of view groups for
        a given view.

        Used as a first step by many of the API functions.

        Parameters:
          viewstyle -- a string with the name of the 'collection' that the
                        view belongs to.
          view_id -- the ID number of the view.

        Returns:
          A dictionary of groups for the view, keyed by the collection
          that the group belongs to. The values are a tuple containing
          the group ID and the string describing the group.

          Returns None if any of the steps undertaken during this
          function fails.
        """

        # Check if the groups are in the cache
        cachedgroups = self.cache.search_view_groups(view_id)
        if cachedgroups is not None:
            # Refresh the cache timeout
            self.cache.store_view_groups(view_id, cachedgroups)
            return cachedgroups


        # Otherwise, we'll have to query the views database
        viewgroups = self.viewmanager.get_view_groups(viewstyle, view_id)
        if viewgroups is None:
            log("Unable to find groups for view id %s (%s)" % \
                    (view_id, viewstyle))
            return None


        # Put these groups in the cache
        if len(viewgroups) > 0:
            self.cache.store_view_groups(view_id, viewgroups)

        return viewgroups

    def _get_matrix_groups(self, col, viewstyle, options):
        """
        Internal function for finding the groups necessary to populate
        a matrix.

        Parameters:
          col -- the module for the collection being shown on the matrix.
          viewstyle -- the view style to use when creating new groups / views.
          options -- a list of parameters describing the matrix properties.

        Returns:
          a tuple containing three items:
            1. a list of dictionaries describing each of the groups that
               should be present in the matrix.
            2. a list of sites belonging to the source mesh.
            3. a list of sites belonging to the destination mesh.

          Returns None if an error occurs while finding matrix groups.

        The options parameter must contain at least two items: the source and
        destination meshes for the matrix. Any subsequent items are used
        by the collection module to determine the groups that correspond to
        each matrix cell. Using amp-icmp as an example, the third item in
        the options list should be a packet size. If provided, this would
        limit the matrix cells to only include streams that matched the
        given packet size.

        The returned group dictionaries contain at least two items:
          labelstring -- a unique string identifying that group
          streams -- a list of stream IDs that belong to the group

        """

        if len(options) < 4:
            log("Invalid options for fetching matrix streams")
            return None

        # Make sure we have an up-to-date list of streams before looking
        # up any groups
        if col.update_streams() is None:
            log("Error while fetching matrix streams")
            return None

        # First two options must be the source and destination meshes
        sourcemesh = options[0]
        destmesh = options[1]

        # Third option describes the direction / family / etc that we are
        # currently looking at
        optdict = {
            'split': options[2],
            'metric': options[3]
        }

        sources = self.ampmesh.get_mesh_sources(sourcemesh)
        if sources is None:
            log("Error while fetching matrix streams")
            return None

        destinations = self.ampmesh.get_mesh_destinations(destmesh)
        if destinations is None:
            log("Error while fetching matrix streams")
            return None

        groups = []
        views = {}

        # For each source / dest combination, update the list of groups to
        # include any groups that should be queried to colour the
        # corresponding matrix cell.
        #
        # Note that there may be more than one group per cell, e.g. one half
        # of the cell may show ipv4 streams and the other may show ipv6
        # streams.
        for s in sources:
            for d in destinations:
                col.update_matrix_groups(self.cache, s, d, optdict, groups, views,
                        self.viewmanager, viewstyle)

        return groups, sources, destinations, views

    def _add_legend_item(self, legend, col, gid, descr, nextlineid):
        """
        Adds a legend entry for a group to a list of existing legend entries.

        Parameters:
          legend -- the list of existing legend entries
          col -- the collection module for the group
          gid -- the id number of the group
          descr -- the textual description of the group
          nextlineid -- the next free unique identifier for graph lines

        Returns:
          the number of entries added to the legend list
        """

        added = 0
        legendtext, aggmethod = col.get_legend_label(descr)
        if legendtext is None:
            legendtext = "Unknown"

        # Don't lookup the streams themselves if we can avoid it
        grouplabels = col.group_to_labels(gid, descr, False)
        if grouplabels is None:
            log("Unable to convert group %d into stream labels" % (gid))
            return added
        lines = []

        # Yes, we could assign line ids within group_to_labels but
        # then anyone implementing a collection has to make sure they
        # remember to do it. Also these ids are only needed for legends,
        # but group_to_labels is also used for other purposes so it
        # is cleaner to do it here even if it means an extra iteration
        # over the grouplabels list.
        for gl in grouplabels:
            lines.append((gl['labelstring'], gl['shortlabel'], nextlineid))
            nextlineid += 1
            added += 1

        legend.append({'group_id':gid, 'label':legendtext, 'lines':lines,
                'collection':col.collection_name, 'aggmethod': aggmethod})
        return added

    def get_users(self):
        return self.viewmanager.get_users()

    def get_user(self, username):
        return self.viewmanager.get_user(username)

    def add_user(self, username, longname, email, roles, password):
        return self.viewmanager.add_user(username, longname, email, roles,
                password)

    def update_user(self, username, longname, email, roles, password):
        return self.viewmanager.update_user(username, longname, email, roles,
                password)

    def delete_user(self, username):
        # TODO are these separate transactions?
        # delete the event filters first, then the user
        if self.eventmanager.delete_event_filter(username):
            return self.viewmanager.delete_user(username)
        return False

    def enable_user(self, username):
        return self.viewmanager.enable_disable_user(username, True)

    def disable_user(self, username):
        return self.viewmanager.enable_disable_user(username, False)

# vim: set smartindent shiftwidth=4 tabstop=4 softtabstop=4 expandtab :

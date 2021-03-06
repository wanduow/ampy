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

from libnntscclient.logger import log
from libampy.collections.ampicmp import AmpIcmp

class AmpTcpping(AmpIcmp):
    def __init__(self, colid, viewmanager, nntscconf):
        super(AmpTcpping, self).__init__(colid, viewmanager, nntscconf)
        self.streamproperties = [
            'source', 'destination', 'port', 'packet_size', 'family'
        ]
        self.groupproperties = [
            'source', 'destination', 'port', 'packet_size', 'aggregation'
        ]
        self.collection_name = 'amp-tcpping'
        self.default_packet_sizes = ["64", "60"]
        self.viewstyle = 'amp-latency'
        self.integerproperties = ['port']
        self.portpreferences = [443, 53, 80]

    def create_group_description(self, properties):
        if 'family' in properties:
            properties['aggregation'] = properties['family'].upper()

        for prop in self.groupproperties:
            if prop not in properties:
                log("Required group property '%s' not present in %s group" % \
                    (prop, self.collection_name))
                return None

        return "FROM %s TO %s PORT %s SIZE %s %s" % ( \
                properties['source'], properties['destination'],
                properties['port'],
                properties['packet_size'], properties['aggregation'].upper())

    def parse_group_description(self, description):
        regex = "FROM (?P<source>[.a-zA-Z0-9_-]+) "
        regex += "TO (?P<destination>[.a-zA-Z0-9_-]+) "
        regex += "PORT (?P<port>[0-9]+) "
        regex += "SIZE (?P<size>[a-zA-Z0-9]+) "
        regex += "(?P<split>[A-Z0-9]+)"

        parts = self._apply_group_regex(regex, description)

        if parts is None:
            return None

        if parts.group("split") not in self.splits:
            log("%s group description has no aggregation method" % \
                    (self.collection_name))
            log(description)
            return None

        keydict = {
            "source": parts.group("source"),
            "destination": parts.group("destination"),
            "port": parts.group("port"),
            "packet_size": parts.group("size"),
            "aggregation": parts.group("split")
        }

        return keydict

    def get_legend_label(self, description):
        groupparams = self.parse_group_description(description)
        if groupparams is None:
            log("Failed to parse group description to generate legend label")
            return None

        label = "%s to %s:%s TCP" % (groupparams['source'],
                groupparams['destination'], groupparams['port'])
        return label, self.splits[groupparams['aggregation']]

    def _group_to_search(self, groupparams):
        return {
            'source': groupparams['source'],
            'destination': groupparams['destination'],
            'port': int(groupparams['port']),
            'packet_size': groupparams['packet_size']
        }

    def update_matrix_groups(self, cache, source, dest, optdict, groups, views,
            viewmanager, viewstyle):

        baseprop = {'source': source, 'destination': dest}

        sels = self.streammanager.find_selections(baseprop, "", "1", 30000, False)
        if sels is None:
            return None

        req, ports = sels
        if req != 'port':
            log("Unable to find suitable ports for %s matrix cell %s to %s" \
                    % (self.collection_name, source, dest))
            return None

        if ports == {} or 'items' not in ports:
            views[(source, dest)] = -1
            return

        minport = None
        for port in self.portpreferences:
            for found in ports['items']:
                if port == int(found['text']):
                    baseprop['port'] = port
                    break
                if minport is None or int(found['text']) < minport:
                    minport = int(found['text'])

        if 'port' not in baseprop:
            # Just use the lowest port number for now
            baseprop['port'] = minport

        sels = self.streammanager.find_selections(baseprop, "", "1", 30000, False)
        if sels is None:
            return None

        # Find a suitable packet size, based on our test preferences
        if sels[0] != 'packet_size':
            log("Unable to find suitable packet sizes for %s matrix cell %s to %s" \
                    % (self.collection_name, source, dest))
            return None

        if sels[1] == {} or 'items' not in sels[1]:
            views[(source, dest)] = -1
            return

        for size in self.default_packet_sizes:
            if any(size == found['text'] for found in sels[1]['items']):
                baseprop['packet_size'] = size
                break

        if 'packet_size' not in baseprop:
            minsize = 0
            for size in sels[1]['items']:
                if size['text'] == "random":
                    continue
                try:
                    if int(size['text']) < minsize or minsize == 0:
                        minsize = int(size['text'])
                except TypeError:
                    # packet size is not an int, so ignore it
                    pass

            if minsize == 0:
                return None
            baseprop['packet_size'] = str(minsize)

        ipv4 = self._matrix_group_streams(baseprop, 'ipv4', groups)
        ipv6 = self._matrix_group_streams(baseprop, 'ipv6', groups)

        if ipv4 == 0 and ipv6 == 0:
            views[(source, dest)] = -1
            return

        if optdict['split'] == "ipv4":
            split = "IPV4"
        elif optdict['split'] == "ipv6":
            split = "IPV6"
        else:
            split = "FAMILY"

        cachelabel = "_".join([self.collection_name, viewstyle, source, dest,
                str(baseprop['port']), baseprop['packet_size'], split])

        viewid = cache.search_matrix_view(cachelabel)
        if viewid is not None:
            views[(source, dest)] = viewid
            return

        cellgroup = self.create_group_from_list([source, dest, \
                baseprop['port'], baseprop['packet_size'], split])

        if cellgroup is None:
            log("Failed to create group for %s matrix cell" % \
                    (self.collection_name))
            return None

        viewid = viewmanager.add_groups_to_view(viewstyle,
                self.collection_name, 0, [cellgroup])
        if viewid is None:
            views[(source, dest)] = -1
            cache.store_matrix_view(cachelabel, -1, 300)
        else:
            views[(source, dest)] = viewid
            cache.store_matrix_view(cachelabel, viewid, 0)

# vim: set smartindent shiftwidth=4 tabstop=4 softtabstop=4 expandtab :

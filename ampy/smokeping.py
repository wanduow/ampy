#!/usr/bin/env python

import sys, string

class SmokepingParser(object):
    """ Parser for the rrd-smokeping collection. """

    def __init__(self):
        """ Initialises the parser """

        # Maps (source, host) to the corresponding stream id
        self.streams = {}

        # Maps (source) to a set of hosts that it runs smokeping tests to
        self.sources = {}

        # Maps (host) to a set of sources that run smokeping tests to it
        self.destinations = {}

    def add_stream(self, s):
        """ Updates the internal maps based on a new stream 

            Parameters:
              s -- the new stream, as returned by NNTSC
        """
        if s['host'] in self.sources:
            self.sources[s['host']][s['source']] = 1
        else:
            self.sources[s['host']] = {s['source']:1}

        if s['source'] in self.destinations:
            self.destinations[s['source']][s['host']] = 1
        else:
            self.destinations[s['source']] = {s['host']:1}

        self.streams[(s['source'], s['host'])] = s['stream_id']

    def get_stream_id(self, params):
        """ Finds the stream ID that matches the given (source, host)
            combination.

            If params does not contain an entry for 'source' or 'host', then
            -1 will be returned.

            Parameters:
                params -- a dictionary containing the parameters describing the
                          stream to search for

            Returns:
                the id number of the matching stream, or -1 if no matching
                stream can be found
        """
        if 'source' not in params:
            return -1
        if 'host' not in params:
            return -1
        
        key = (params['source'], params['host'])
        if key not in self.streams:
            return -1
        return self.streams[key]
       
    def request_data(self, client, colid, streams, start, end, binsize, detail):
        """ Based on the level of detail requested, forms and sends a request
            to NNTSC for aggregated data.
        """
        if detail == "minimal":
            aggcols = ["median", "loss"]
            aggfuncs = ["avg", "avg"]
        else:
            aggcols = ["uptime", "loss", "median",
                'ping1', 'ping2', 'ping3', 'ping4', 'ping5', 'ping6', 'ping7',
                'ping8', 'ping9', 'ping10', 'ping11', 'ping12', 'ping13',
                'ping14', 'ping15', 'ping16', 'ping17', 'ping18', 'ping19',
                'ping20']
            aggfuncs = ["avg"] * len(aggcols)

        group = ["stream_id"]

        return client.request_aggregate(colid, streams, start, end,
                aggcols, binsize, group, aggfuncs)
   
    def format_data(self, received, stream, streaminfo):
        """ Formats the measurements retrieved from NNTSC into a nice format
            for subsequent analysis / plotting / etc.

            In this case, this means combining the individual ping 
            measurements, e.g. ping1, ping2, ping3 etc., into a single list
            called 'pings'.
        """
        formatted = []

        for d in received:
            newdict = {}
            pings = [None] * 20
            export_pings = False
            for k, v in d.items():

                if "ping" in k:
                    index = int(k.split("ping")[1]) - 1
                    assert(index >= 0 and index < 20)
                    pings[index] = v
                    export_pings = True
                else:
                    newdict[k] = v

            if export_pings: 
                newdict["pings"] = pings

            formatted.append(newdict)
        return formatted

    def get_selection_options(self, params):
        """ Returns the list of names to populate a dropdown list with, given
            a current set of selected parameters.

            If no parameters are set, this will return the list of sources.

            If 'source' is set but not 'host', this will return the list of
            destinations that are tested to by that source.

            If 'host' is set but not 'source', this will return the list of
            sources that test to that host.

            If both parameters are set, a list containing the ID of the stream
            described by those parameters is returned.
        """
        if 'source' not in params and 'host' not in params:
            return self._get_sources(None)

        if 'source' not in params:
            return self._get_sources(params['host'])
  
        if 'host' not in params:
            return self._get_destinations(params['source'])

        return [self.get_stream_id(params)]

    def get_graphtab_stream(self, streaminfo):
        """ Given the description of a streams from a similar collection,
            return the stream id of the streams from this collection that are
            suitable for display on a graphtab alongside the main graph (where
            the main graph shows the stream passed into this function)
        """

        # TODO do some sort of translation between 'host', 'destination',
        # 'target' and other parameters that mean similar things but have
        # different names
        if 'source' not in streaminfo or 'host' not in streaminfo:
            return []

        params = {'source':streaminfo['source'],
                'host':streaminfo['host']} 

        stream = self.get_stream_id(params)
        if stream == -1:
            return []
        
        return [{'streamid':stream, 'title':'Latency', 
                'collection':'rrd-smokeping'}]

    def _get_sources(self, dst):
        """ Get a list of all sources that are test to a given destination.
            
            If dst is None, then returns a list of all known sources.
        """
        if dst != None:
            if dst not in self.sources:
                return []
            return self.sources[dst].keys()

        sources = {}
        for v in self.sources.values():
            for src in v.keys():
                sources[src] = 1
        return sources.keys()

    def _get_destinations(self, src):
        """ Get a list of all destinations that are tested to a given source.
            
            If src is None, then returns a list of all known destinations.
        """
        if src != None:
            if src not in self.destinations:
                return []
            return self.destinations[src].keys()

        dests = {}
        for v in self.destinations.values():
            for d in v.keys():
                dests[d] = 1
        return dests.keys()



# vim: set smartindent shiftwidth=4 tabstop=4 softtabstop=4 expandtab :

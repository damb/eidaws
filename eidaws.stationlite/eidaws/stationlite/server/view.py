# -*- coding: utf-8 -*-

import collections
import logging
import socket

from cached_property import cached_property
from flask import request, make_response, render_template
from flask_restful import Resource
from webargs.flaskparser import use_args

from eidaws.stationlite.server.parser import (
    use_fdsnws_args,
    use_fdsnws_kwargs,
    StationLiteSchema,
    StreamEpochSchema,
    ManyStreamEpochSchema,
)
from eidaws.stationlite.server.strict import with_strict_args
from eidaws.stationlite.version import __version__
from eidaws.utils.sncl import StreamEpochsHandler, StreamEpoch
from eidaws.utils.settings import (
    EIDAWS_ROUTING_PATH_QUERY,
    FDSNWS_DEFAULT_NO_CONTENT_ERROR_CODE,
)
from eidaws.utils.misc import Route

from eidaws.stationlite.engine.db_query import (
    resolve_vnetwork,
    find_streamepochs_and_routes,
)
from eidaws.stationlite.server.db import db
from eidaws.stationlite.server.http_error import FDSNHTTPError
from eidaws.stationlite.server.stream import OutputStream


class StationLiteVersionResource(Resource):
    """
    ``version`` resource implementation for eidaws-stationlite
    """

    def get(self):
        return make_response(
            __version__, {"Content-Type": "text/plain; charset=utf-8"}
        )

    post = get


class StationLiteWadlResource(Resource):
    """
    ``application.wadl`` resource implementation for eidaws-stationlite
    """

    @cached_property
    def wadl(self):
        return render_template(
            "routing.wadl",
            url=f"http://{socket.getfqdn()}{EIDAWS_ROUTING_PATH_QUERY}",
        )

    def get(self):
        return make_response(self.wadl, {"Content-Type": "application/xml"})

    post = get


class StationLiteQueryResource(Resource):
    """
    ``query`` resource implementation for eidaws-stationlite
    """

    LOGGER = "eidaws.stationlite.stationlite_resource"

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.LOGGER)

    @use_args(StationLiteSchema(), locations=("query",))
    @use_fdsnws_kwargs(
        ManyStreamEpochSchema(context={"request": request}),
        locations=("query",),
    )
    @with_strict_args(
        (StreamEpochSchema, StationLiteSchema), locations=("query",),
    )
    def get(self, args, stream_epochs):
        """
        Process an eidaws-stationlite HTTP GET request.
        """
        return self._make_response(args, stream_epochs)

    @use_fdsnws_args(StationLiteSchema(), locations=("form",))
    @use_fdsnws_kwargs(
        ManyStreamEpochSchema(context={"request": request}),
        locations=("form",),
    )
    @with_strict_args(StationLiteSchema, locations=("form",))
    def post(self, args, stream_epochs):
        """
        Process an eidaws-stationlite HTTP POST request.
        """
        return self._make_response(args, stream_epochs)

    def _make_response(self, args, stream_epochs):
        self.logger.debug(f"StationLiteSchema: {args}")
        self.logger.debug(f"StreamEpoch objects: {stream_epochs}")

        payload = self._process_request(args, stream_epochs,)

        if not payload:
            raise FDSNHTTPError.create(
                int(args.get("nodata", FDSNWS_DEFAULT_NO_CONTENT_ERROR_CODE))
            )

        return make_response(
            payload, {"Content-Type": "text/plain; charset=utf-8"}
        )

    def _process_request(self, args, stream_epochs):
        # resolve virtual network stream epochs
        vnet_stream_epochs = []
        for stream_epoch in stream_epochs:
            self.logger.debug(f"Resolving {stream_epoch!r} regarding VNET.")
            vnet_stream_epochs.extend(
                resolve_vnetwork(db.session, stream_epoch)
            )

        self.logger.debug(f"Stream epochs from VNETs: {vnet_stream_epochs!r}")

        stream_epochs.extend(vnet_stream_epochs)

        # collect results for each stream epoch
        routes = []
        for stream_epoch in stream_epochs:
            self.logger.debug(f"Processing request for {stream_epoch!r}")
            # query
            _routes = find_streamepochs_and_routes(
                db.session,
                stream_epoch,
                args["service"],
                level=args["level"],
                access=args["access"],
                method=args["method"],
                minlat=args["minlatitude"],
                maxlat=args["maxlatitude"],
                minlon=args["minlongitude"],
                maxlon=args["maxlongitude"],
            )

            # adjust stream epochs regarding time constraints
            for url, streams in _routes:
                streams.modify_with_temporal_constraints(
                    start=stream_epoch.starttime, end=stream_epoch.endtime
                )

            routes.extend(_routes)

        self.logger.debug(f"StationLite routes: {routes}")
        # merge stream epochs for each route
        merged_routes = collections.defaultdict(StreamEpochsHandler)
        for url, stream_epochs in routes:
            merged_routes[url].merge(stream_epochs)

        self.logger.debug(f"StationLite routes (merged): {merged_routes}")

        for url, stream_epochs in merged_routes.items():
            if args["level"] in ("network", "station"):
                merged_routes[url] = [
                    StreamEpoch.from_streamepochs(ses) for ses in stream_epochs
                ]
            else:
                merged_routes[url] = [
                    se for ses in stream_epochs for se in ses
                ]

        # sort response
        routes = [
            Route(url=url, stream_epochs=sorted(stream_epochs))
            for url, stream_epochs in merged_routes.items()
        ]

        # sort additionally by URL
        routes.sort()

        ostream = OutputStream.create(args["format"], routes=routes,)
        return str(ostream)

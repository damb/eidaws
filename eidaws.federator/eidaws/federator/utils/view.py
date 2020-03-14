# -*- coding: utf-8 -*-

import abc
import aiohttp
import logging

from aiohttp import web
from aiohttp_cors import CorsViewMixin
from webargs.aiohttpparser import parser

from eidaws.federator.settings import FED_BASE_ID
from eidaws.federator.utils.strict import keyword_parser
from eidaws.federator.utils.misc import make_context_logger
from eidaws.federator.utils.parser import fdsnws_parser
from eidaws.utils.schema import StreamEpochSchema, ManyStreamEpochSchema


class BaseView(web.View, CorsViewMixin, metaclass=abc.ABCMeta):

    LOGGER = FED_BASE_ID + ".view"

    def __init__(self, request, schema):
        super().__init__(request)
        self._logger = logging.getLogger(self.LOGGER)
        self.logger = make_context_logger(self._logger, self.request)

        self._schema = schema

    @abc.abstractmethod
    async def get(self):
        # strict parameter validation
        await keyword_parser.parse(
            (self._schema, StreamEpochSchema), self.request, locations=("query",),
        )

        # parse query parameters
        self.request[FED_BASE_ID + ".query_params"] = await parser.parse(
            self._schema(), self.request, locations=("query",)
        )

        stream_epochs_dict = await fdsnws_parser.parse(
            ManyStreamEpochSchema(context={"request": self.request}),
            self.request,
            locations=("query",),
        )
        self.request[FED_BASE_ID + ".stream_epochs"] = stream_epochs_dict[
            "stream_epochs"
        ]

        self.logger.debug(self.request[FED_BASE_ID + ".query_params"])
        self.logger.debug(self.request[FED_BASE_ID + ".stream_epochs"])

    @abc.abstractmethod
    async def post(self):
        # strict parameter validation
        await keyword_parser.parse(
            self._schema, self.request, locations=("form",),
        )

        # parse query parameters
        self.request[
            FED_BASE_ID + ".query_params"
        ] = await fdsnws_parser.parse(
            self._schema(), self.request, locations=("form",)
        )

        stream_epochs_dict = await fdsnws_parser.parse(
            ManyStreamEpochSchema(context={"request": self.request}),
            self.request,
            locations=("form",),
        )
        self.request[FED_BASE_ID + ".stream_epochs"] = stream_epochs_dict[
            "stream_epochs"
        ]

        self.logger.debug(self.request[FED_BASE_ID + ".query_params"])
        self.logger.debug(self.request[FED_BASE_ID + ".stream_epochs"])
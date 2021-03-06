# -*- coding: utf-8 -*-

import datetime
import errno
import json

from eidaws.federator.eidaws_wfcatalog.json.parser import WFCatalogSchema
from eidaws.federator.settings import (
    FED_BASE_ID,
    FED_WFCATALOG_JSON_SERVICE_ID,
)
from eidaws.federator.utils.process import UnsortedResponse
from eidaws.federator.utils.worker import BaseSplitAlignWorker


_JSON_ARRAY_START = b"["
_JSON_ARRAY_END = b"]"
_JSON_SEP = b","


class _WFCatalogWorker(BaseSplitAlignWorker):
    """
    A worker task implementation for ``eidaws-wfcatalog`` ``format=json``.
    The worker implements splitting and aligning facilities.

    When splitting and aligning (i.e. merging potentially occurring overlaps)
    data is downloaded sequentially. Note, that a worker assumes JSON
    objects to be shipped ordered within the array.
    """

    SERVICE_ID = FED_WFCATALOG_JSON_SERVICE_ID
    QUERY_PARAM_SERIALIZER = WFCatalogSchema

    LOGGER = ".".join([FED_BASE_ID, SERVICE_ID, "worker"])

    _CHUNK_SIZE = 8192

    async def _buffer_response(self, resp, buf, context, **kwargs):
        chunk_size = context["chunk_size"]

        last_obj = None
        last_obj_length = 0

        await buf.seek(0, 2)
        if await buf.tell():
            # deserialize the last JSON object from buffer
            # XXX(damb): Assume that chunk_size >= last_obj_length
            try:
                await buf.seek(-chunk_size, 2)
            except OSError as err:
                if err.errno == errno.EINVAL:
                    await buf.seek(0)
                else:
                    raise

            stack = []
            chunk = await buf.read()

            for i, c in enumerate(reversed(chunk), start=1):
                if c == 125:  # b'}'
                    stack.append(c)
                elif c == 123:  # b'{'
                    stack.pop()

                last_obj_length = i

                if not stack:
                    break

            last_obj = json.loads(chunk[-last_obj_length:])

        first_chunk = True
        while True:

            chunk = await resp.content.read(chunk_size)
            if not chunk:
                # chop off b']'
                await buf.truncate(await buf.tell() - 1)
                break

            if first_chunk:
                if last_obj is not None:
                    # deserialize the first JSON object from the chunk
                    try:
                        obj = json.loads(chunk[1 : last_obj_length + 1])
                    except json.JSONDecodeError:
                        obj = None

                    if obj is not None and last_obj == obj:
                        # chop off first JSON object + b','
                        chunk = chunk[last_obj_length + 1 :]

                    last_obj = None

                # chop off b'['
                chunk = chunk[1:]

                if await buf.tell():
                    await buf.write(_JSON_SEP)

                first_chunk = False

            await buf.write(chunk)

    async def _flush(self, buf, drain, context, append=True):
        await buf.seek(0)

        if append:
            await drain.drain(_JSON_SEP)

        while True:
            chunk = await buf.read(context.get("chunk_size", -1))

            if not chunk:
                break

            await drain.drain(chunk)


class WFCatalogRequestProcessor(UnsortedResponse):

    SERVICE_ID = FED_WFCATALOG_JSON_SERVICE_ID

    LOGGER = ".".join([FED_BASE_ID, SERVICE_ID, "process"])

    @property
    def content_type(self):
        return "application/json"

    async def _prepare_response(self, response):
        response.content_type = self.content_type
        response.headers["Content-Disposition"] = (
            'attachment; filename="'
            + FED_BASE_ID.replace(".", "-")
            + "-"
            + datetime.datetime.utcnow().isoformat()
            + '.json"'
        )

        await response.prepare(self.request)
        await response.write(_JSON_ARRAY_START)

    def _create_worker(self, request, session, drain, lock=None, **kwargs):
        return _WFCatalogWorker(
            self.request,
            session,
            drain,
            lock=lock,
            endtime=self._default_endtime,
            **kwargs,
        )

    async def _write_response_footer(self, response):
        await response.write(_JSON_ARRAY_END)

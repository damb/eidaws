import copy
import functools
import pytest

from eidaws.federator.fdsnws_availability.text import create_app, SERVICE_ID
from eidaws.federator.fdsnws_availability.text.app import DEFAULT_CONFIG
from eidaws.federator.fdsnws_availability.text.route import (
    FED_AVAILABILITY_TEXT_PATH_QUERY,
)
from eidaws.federator.utils.misc import get_config
from eidaws.federator.fdsnws_availability.tests.server_mixin import (
    _TestAPIMixin,
)
from eidaws.federator.utils.pytest_plugin import (
    fdsnws_dataselect_content_type,
    fdsnws_error_content_type,
    eidaws_routing_path_query,
    load_data,
    make_federated_eida,
    server_config,
    cache_config,
    tester,
)
from eidaws.federator.utils.tests.server_mixin import (
    _TestCommonServerConfig,
    _TestCORSMixin,
    _TestKeywordParserMixin,
    _TestRoutingMixin,
    _TestServerBase,
)
from eidaws.utils.settings import FDSNWS_AVAILABILITY_PATH_QUERY

# TODO(damb): Also implement for


class TestFDSNAvailabilityQueryServer(
    _TestCommonServerConfig,
    _TestCORSMixin,
    _TestKeywordParserMixin,
    _TestRoutingMixin,
    _TestAPIMixin,
    _TestServerBase,
):
    FED_PATH_RESOURCE = FED_AVAILABILITY_TEXT_PATH_QUERY
    PATH_RESOURCE = FDSNWS_AVAILABILITY_PATH_QUERY

    _DEFAULT_SERVER_CONFIG = {"pool_size": 1}

    @staticmethod
    def get_config(**kwargs):
        config_dict = copy.deepcopy(DEFAULT_CONFIG)
        config_dict.update(kwargs)

        return get_config(SERVICE_ID, defaults=config_dict)

    @classmethod
    def create_app(cls, config_dict=None):

        if config_dict is None:
            config_dict = cls.get_config(**cls._DEFAULT_SERVER_CONFIG)

        return functools.partial(create_app, config_dict)

    @pytest.mark.parametrize(
        "method,params_or_data",
        [
            ("GET", {"show": "foo"}),
            ("POST", b"show=foo\nNET STA LOC CHA 2020-01-01 2020-01-02"),
            ("GET", {"show": ""}),
            ("POST", b"show=\nNET STA LOC CHA 2020-01-01 2020-01-02"),
        ],
    )
    async def test_bad_request_query(
        self,
        make_federated_eida,
        fdsnws_error_content_type,
        method,
        params_or_data,
    ):
        client, _, _ = await make_federated_eida(self.create_app())

        method = method.lower()
        kwargs = {"params" if method == "get" else "data": params_or_data}
        resp = await getattr(client, method)(self.FED_PATH_RESOURCE, **kwargs)

        assert resp.status == 400
        assert f"Error 400: Bad request" in await resp.text()
        assert (
            "Content-Type" in resp.headers
            and resp.headers["Content-Type"] == fdsnws_error_content_type
        )


# class TestFDSNAvailabilityExtentServer(
#     _TestCommonServerConfig,
#     _TestCORSMixin,
#     _TestKeywordParserMixin,
#     _TestRoutingMixin,
#     _TestAPIMixin,
# ):
#     pass

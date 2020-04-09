# -*- coding: utf-8 -*-

import aiohttp_cors
import functools

from aiohttp import web

from eidaws.federator.utils.middleware import (
    before_request,
    exception_handling_middleware,
)
from eidaws.federator.utils.misc import (
    setup_endpoint_http_conn_pool,
    setup_routing_http_conn_pool,
    setup_redis,
    setup_response_code_stats,
    setup_cache,
)
from eidaws.federator.utils.parser import setup_parser_error_handler
from eidaws.federator.settings import (
    FED_DEFAULT_HOSTNAME,
    FED_DEFAULT_PORT,
    FED_DEFAULT_UNIX_PATH,
    FED_DEFAULT_URL_ROUTING,
    FED_DEFAULT_NETLOC_PROXY,
    FED_DEFAULT_REQUEST_METHOD,
    FED_DEFAULT_ENDPOINT_CONN_LIMIT,
    FED_DEFAULT_ENDPOINT_CONN_LIMIT_PER_HOST,
    FED_DEFAULT_TIMEOUT_CONNECT,
    FED_DEFAULT_TIMEOUT_SOCK_CONNECT,
    FED_DEFAULT_TIMEOUT_SOCK_READ,
    FED_DEFAULT_ROUTING_CONN_LIMIT,
    FED_DEFAULT_URL_REDIS,
    FED_DEFAULT_REDIS_POOL_MINSIZE,
    FED_DEFAULT_REDIS_POOL_MAXSIZE,
    FED_DEFAULT_REDIS_POOL_TIMEOUT,
    FED_DEFAULT_RETRY_BUDGET_CLIENT_THRES,
    FED_DEFAULT_RETRY_BUDGET_CLIENT_TTL,
    FED_DEFAULT_RETRY_BUDGET_WINDOW_SIZE,
    FED_DEFAULT_POOL_SIZE,
    FED_DEFAULT_CACHE_CONFIG,
    FED_DEFAULT_CLIENT_MAX_SIZE,
    FED_DEFAULT_MAX_STREAM_EPOCH_DURATION,
    FED_DEFAULT_MAX_STREAM_EPOCH_DURATION_TOTAL,
    FED_DEFAULT_STREAMING_TIMEOUT,
)
from eidaws.federator.utils.strict import setup_keywordparser_error_handler
from eidaws.federator.version import __version__
from eidaws.utils.error import Error


config_schema = {
    "type": "object",
    "properties": {
        "hostname": {"type": "string", "format": "ipv4"},
        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
        "unix_path": {
            "oneOf": [
                {"type": "null"},
                {"type": "string", "format": "uri", "pattern": r"^unix:/"},
            ]
        },
        "logging_conf": {"type": "string", "pattern": r"^(\/|~)"},
        "url_routing": {
            "type": "string",
            "format": "uri",
            "pattern": "^https?://",
        },
        "routing_connection_limit": {"type": "integer", "minimum": 1},
        "endpoint_request_method": {
            "type": "string",
            "pattern": "^(GET|POST)$",
        },
        "endpoint_connection_limit": {"type": "integer", "minimum": 1},
        "endpoint_connection_limit_per_host": {
            "type": "integer",
            "minimum": 1,
        },
        "endpoint_timeout_connect": {
            "oneOf": [{"type": "null"}, {"type": "number", "minimum": 0}]
        },
        "endpoint_timeout_sock_connect": {
            "oneOf": [{"type": "null"}, {"type": "number", "minimum": 0}]
        },
        "endpoint_timeout_sock_read": {
            "oneOf": [{"type": "null"}, {"type": "number", "minimum": 0}]
        },
        "redis_url": {
            "type": "string",
            "format": "uri",
            "pattern": "^redis://",
        },
        "redis_pool_minsize": {"type": "integer", "minimum": 1},
        "redis_pool_maxsize": {"type": "integer", "minimum": 1},
        "redis_pool_timeout": {
            "oneOf": [{"type": "number", "minimum": 1}, {"type": "null"}]
        },
        "client_retry_budget_threshold": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
        },
        "client_retry_budget_ttl": {"type": "number", "minimum": 0},
        "client_retry_budget_window_size": {"type": "integer", "minimum": 1},
        "pool_size": {
            "oneOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]
        },
        "cache_config": {
            "oneOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "properties": {
                        "cache_type": {"type": "string", "pattern": "^null$"},
                    },
                },
                {
                    "type": "object",
                    "properties": {
                        "cache_type": {"type": "string", "pattern": "^redis$"},
                        "cache_kwargs": {
                            "type": "object",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "format": "uri",
                                    "pattern": "^redis://",
                                },
                                "default_timeout": {
                                    "type": "integer",
                                    "minimum": 0,
                                },
                                "compress": {"type": "boolean"},
                                "minsize": {"type": "integer", "minimum": 1},
                                "maxsize": {"type": "integer", "maximum": 1},
                            },
                        },
                    },
                },
            ]
        },
        "client_max_size": {"type": "integer", "minimum": 0},
        "max_stream_epoch_duration": {
            "oneOf": [{"type": "null"}, {"type": "integer", "minimum": 1}]
        },
        "max_total_stream_epoch_duration": {
            "oneOf": [{"type": "null"}, {"type": "integer", "minimum": 1}]
        },
        "streaming_timeout": {
            "oneOf": [{"type": "null"}, {"type": "integer", "minimum": 1}]
        },
        "proxy_netloc": {
            "oneOf": [
                {"type": "null"},
                {
                    "type": "string",
                    "format": "uri",
                    # allow IPv4(:PORT) or FQDN(:PORT)
                    "pattern": (
                        r"^(((?:[0-9]{1,3}\.){3}[0-9]{1,3})"
                        r"|(([a-zA-Z0-9]+(-[a-zA-Z0-9]+)*\.)+[a-zA-Z]{2,}))"
                        r"(?:\:([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|"
                        r"65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?$"
                    ),
                },
            ]
        },
    },
    "additionalProperties": False,
}


def default_config():
    """
    Return a default application configuration.
    """

    default_config = {}
    default_config.setdefault("hostname", FED_DEFAULT_HOSTNAME)
    default_config.setdefault("port", FED_DEFAULT_PORT)
    default_config.setdefault("unix_path", FED_DEFAULT_UNIX_PATH)
    default_config.setdefault("url_routing", FED_DEFAULT_URL_ROUTING)
    default_config.setdefault(
        "routing_connection_limit", FED_DEFAULT_ROUTING_CONN_LIMIT
    )
    default_config.setdefault(
        "endpoint_request_method", FED_DEFAULT_REQUEST_METHOD
    )
    default_config.setdefault(
        "endpoint_connection_limit", FED_DEFAULT_ENDPOINT_CONN_LIMIT
    )
    default_config.setdefault(
        "endpoint_connection_limit_per_host",
        FED_DEFAULT_ENDPOINT_CONN_LIMIT_PER_HOST,
    )
    default_config.setdefault(
        "endpoint_timeout_connect", FED_DEFAULT_TIMEOUT_CONNECT
    )
    default_config.setdefault(
        "endpoint_timeout_sock_connect", FED_DEFAULT_TIMEOUT_SOCK_CONNECT
    )
    default_config.setdefault(
        "endpoint_timeout_sock_read", FED_DEFAULT_TIMEOUT_SOCK_READ
    )
    default_config.setdefault("redis_url", FED_DEFAULT_URL_REDIS)
    default_config.setdefault(
        "redis_pool_minsize", FED_DEFAULT_REDIS_POOL_MINSIZE
    )
    default_config.setdefault(
        "redis_pool_maxsize", FED_DEFAULT_REDIS_POOL_MAXSIZE
    )
    default_config.setdefault(
        "redis_pool_timeout", FED_DEFAULT_REDIS_POOL_TIMEOUT
    )
    default_config.setdefault(
        "client_retry_budget_threshold", FED_DEFAULT_RETRY_BUDGET_CLIENT_THRES
    )
    default_config.setdefault(
        "client_retry_budget_ttl", FED_DEFAULT_RETRY_BUDGET_CLIENT_TTL
    )
    default_config.setdefault(
        "client_retry_budget_window_size", FED_DEFAULT_RETRY_BUDGET_WINDOW_SIZE
    )
    default_config.setdefault("pool_size", FED_DEFAULT_POOL_SIZE)
    default_config.setdefault("cache_config", FED_DEFAULT_CACHE_CONFIG)
    default_config.setdefault("client_max_size", FED_DEFAULT_CLIENT_MAX_SIZE)
    default_config.setdefault(
        "max_stream_epoch_duration", FED_DEFAULT_MAX_STREAM_EPOCH_DURATION
    )
    default_config.setdefault(
        "max_total_stream_epoch_duration",
        FED_DEFAULT_MAX_STREAM_EPOCH_DURATION_TOTAL,
    )
    default_config.setdefault(
        "streaming_timeout", FED_DEFAULT_STREAMING_TIMEOUT
    )
    default_config.setdefault("proxy_netloc", FED_DEFAULT_NETLOC_PROXY)

    return default_config


def create_app(service_id, config_dict, setup_routes_callback=None, **kwargs):
    """
    Factory for application creation.
    """

    app = web.Application(
        # XXX(damb): The ordering of middlewares matters
        middlewares=[before_request, exception_handling_middleware],
        client_max_size=config_dict["config"][service_id]["client_max_size"],
    )

    if setup_routes_callback is not None:
        setup_routes_callback(app)

    on_startup = [
        functools.partial(setup_redis, service_id),
        functools.partial(setup_response_code_stats, service_id),
        functools.partial(setup_cache, service_id),
    ]
    for fn in on_startup:
        app.on_startup.append(fn)

    for k, v in config_dict.items():
        app[k] = v

    cors = aiohttp_cors.setup(
        app,
        defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=False,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["POST", "GET"],
            )
        },
    )

    for route in list(app.router.routes()):
        if not isinstance(route.resource, web.StaticResource):  # workaround
            cors.add(route)

    setup_parser_error_handler(service_version=__version__)
    setup_keywordparser_error_handler(service_version=__version__)

    setup_endpoint_http_conn_pool(service_id, app)
    setup_routing_http_conn_pool(service_id, app)

    return app


class AppError(Error):
    """Base application error ({})."""


class ConfigurationError(AppError):
    """Configuration errro: {}"""

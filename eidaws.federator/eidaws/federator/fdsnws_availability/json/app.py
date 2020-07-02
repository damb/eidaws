# -*- coding: utf-8 -*-

import sys

from eidaws.federator.fdsnws_availability.json import SERVICE_ID, create_app
from eidaws.federator.utils.app import (
    _main,
    config as default_config,
    config_schema as default_config_schema,
)


PROG = "eida-federator-availability-json"
DEFAULT_CONFIG = default_config()


def main(argv=sys.argv[1:]):
    _main(
        SERVICE_ID,
        create_app,
        prog=PROG,
        argv=argv,
        default_config=DEFAULT_CONFIG,
        config_schema=default_config_schema,
    )


if __name__ == "__main__":
    main()
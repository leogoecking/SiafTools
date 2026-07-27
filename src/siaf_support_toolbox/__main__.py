import sys

from siaf_support_toolbox.discovery.firebird_client_probe import client_probe_main
from siaf_support_toolbox.main import main

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--probe-firebird-client":
        raise SystemExit(client_probe_main(sys.argv[2:]))
    main()

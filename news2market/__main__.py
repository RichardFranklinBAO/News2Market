"""Package entrypoint: dashboard by default, or an optional research subcommand."""
import sys

if len(sys.argv)>1 and sys.argv[1]=='research':
    from .research.cli import main
    main(sys.argv[2:])
else:
    from .app import main
    main()

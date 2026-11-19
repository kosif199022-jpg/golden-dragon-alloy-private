"""Package entrypoint: preserve nested CLI exit status (notably QA gate failures)."""
import sys
from .cli import main

sys.exit(main())

#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')

    # Make debug print() output encoding-tolerant. On Windows the console/redirected
    # stdout is often cp1252, so a print() containing a non-ASCII char (e.g. an arrow
    # or emoji) raises UnicodeEncodeError mid-request and turns into a 500. Replacing
    # unencodable characters keeps those debug prints from crashing views.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(errors='replace')
        except (AttributeError, ValueError):
            pass
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

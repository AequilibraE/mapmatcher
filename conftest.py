import os
import pytest
from tempfile import gettempdir


def pytest_sessionstart(session):

    directory = str(gettempdir())

    if directory not in os.environ["PATH"]:
        os.environ["PATH"] = directory + os.pathsep + os.environ["PATH"]
    if "PROJ_LIB" not in os.environ:
        os.environ["PROJ_LIB"] = directory

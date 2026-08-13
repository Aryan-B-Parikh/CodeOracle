"""Runner for the CodeOracle test sandbox."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import policy
import stage
from stage import StageLimitError

IMAGE = "codeoracle/sandbox:latest"
LOG_LIMIT = 8000
_CHUNK = 65536

PYTHON_CMD = (
    "cd /home/codeoracle && "
    "pytest -s /sandbox/tests -p no:cacheprovider --cov /sandbox/src --cov-branch "
    "--cov-report=json:/home/codeoracle/coverage.json --cov-report=term "
    "--junitxml=/home/codeoracle/junit.xml; RC=$?; "
#!/usr/bin/env python
"""Launch the Django dev server as a fully detached daemon.

Double-forks + setsid so the runserver process reparents to PID 1 and survives
the parent shell / Claude Code session exiting. Logs to server.log.

Usage:  .venv/bin/python serve_detached.py [host:port]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADDR = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:8000"
PYTHON = os.path.join(HERE, ".venv", "bin", "python")
LOG = os.path.join(HERE, "server.log")

# First fork
if os.fork() > 0:
    sys.exit(0)
os.setsid()  # new session, detach from controlling terminal
# Second fork (prevent re-acquiring a terminal)
if os.fork() > 0:
    sys.exit(0)

os.chdir(HERE)
# Redirect stdio to the log file
with open(os.devnull, "rb", 0) as devnull:
    os.dup2(devnull.fileno(), sys.stdin.fileno())
logfd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
os.dup2(logfd, sys.stdout.fileno())
os.dup2(logfd, sys.stderr.fileno())

os.execv(PYTHON, [PYTHON, "manage.py", "runserver", ADDR, "--noreload"])

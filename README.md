# ntripstreams

[![linting](https://github.com/stenseng/ntripstreams/actions/workflows/linter.yml/badge.svg)](https://github.com/stenseng/ntripstreams/actions/workflows/linter.yml)
[![python unittest](https://github.com/stenseng/ntripstreams/actions/workflows/unittest.yml/badge.svg)](https://github.com/stenseng/ntripstreams/actions/workflows/unittest.yml)
[![pypi package](https://badge.fury.io/py/ntripstreams.svg)](https://pypi.org/project/ntripstreams)
[![code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black)

**ntripstreams** is a Python library and command line tool for transferring
GNSS and related data between GNSS instruments, NTRIP casters and users using
the NTRIP protocol. It provides simple, logical, `asyncio`-based methods to
communicate with GNSS receivers and casters, and to frame and decode RTCM 3
messages.

The intent is to provide simple and logical methods to communicate with GNSS
receivers and casters rather than high performance, highly efficient methods.

```console
$ pip install ntripstreams
```

## Quick start

List the source table of a caster:

```console
$ ntripstreams http://caster.example.net:2101
```

Stream and decode RTCM 3 from a mountpoint:

```console
$ ntripstreams http://caster.example.net:2101 -m MOUNT1 -u USER -p PASSWORD -v
```

Credentials and connection details can also be supplied through the
environment (`NTRIP_URL`, `NTRIP_MOUNTPOINT`, `NTRIP_USER`, `NTRIP_PASSWORD`,
`NTRIP_LOGFILE`); a command line value always overrules the matching
environment variable.

## Documentation

Full documentation, including installation and the API reference, is available
at <https://stenseng.github.io/ntripstreams/>.

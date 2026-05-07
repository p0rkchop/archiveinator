from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("archiveinator")
except PackageNotFoundError:
    __version__ = "unknown"

# This file makes Python treat the `flac_toolkit` directory as a package.

try:
    from ._version import version as __version__
except ImportError:
    try:
        from importlib.metadata import version, PackageNotFoundError
        __version__ = version("flac_toolkit")
    except (ImportError, PackageNotFoundError):
        __version__ = "0.0.0+unknown"

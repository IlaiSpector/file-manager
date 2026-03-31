"""Shared transport configuration values."""

ENCODING = "utf-8"
LENGTH_PREFIX_SIZE = 4
LENGTH_PREFIX_BYTEORDER = "big"

# Raw binary transfers are read in chunks to avoid one huge socket read.
SOCKET_CHUNK_SIZE = 64 * 1024

# makes JSON seperators smaller without changing their meaning. for example ', ' is replaced with ',
JSON_SEPARATORS = (",", ":")


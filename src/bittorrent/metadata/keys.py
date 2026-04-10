# Root keys

STANDARD_ROOT_KEYS: list[bytes] = [b"announce", b"info"]

OFFICIAL_ROOT_EXTRA_KEYS: list[bytes] = [b"announce-list", b"url-list", b"nodes"]

UNOFFICIAL_ROOT_EXTRA_KEYS: list[bytes] = [
    b"creation date",
    b"created by",
    b"created by.utf-8",
    b"comment",
    b"comment.utf-8",
]

SUPPORTED_ROOT_KEYS: list[bytes] = (
    STANDARD_ROOT_KEYS + OFFICIAL_ROOT_EXTRA_KEYS + UNOFFICIAL_ROOT_EXTRA_KEYS
)

# Info keys

# V1 info keys
STANDARD_V1_INFO_KEYS: list[bytes] = [
    b"name",
    b"piece length",
    b"pieces",
    b"length",
    b"files",
]

UNOFFICIAL_V1_INFO_EXTRA_KEYS: list[bytes] = [b"name.utf-8"]

SUPPORTED_V1_INFO_KEYS: list[bytes] = (
    STANDARD_V1_INFO_KEYS + UNOFFICIAL_V1_INFO_EXTRA_KEYS
)

# V2 info keys
STANDARD_V2_INFO_KEYS: list[bytes] = [b"meta version", b"file tree"]

SUPPORTED_V2_INFO_KEYS: list[bytes] = STANDARD_V2_INFO_KEYS

# Hybrid info keys
SUPPORTED_INFO_KEYS: list[bytes] = SUPPORTED_V1_INFO_KEYS + SUPPORTED_V2_INFO_KEYS

# V1 info file keys
STANDARD_V1_INFO_FILE_KEYS: list[bytes] = [b"length", b"path"]

UNOFFICIAL_V1_INFO_FILE_EXTRA_KEYS: list[bytes] = [b"path.utf-8"]

SUPPORTED_V1_INFO_FILE_KEYS: list[bytes] = (
    STANDARD_V1_INFO_FILE_KEYS + UNOFFICIAL_V1_INFO_FILE_EXTRA_KEYS
)

# V2 info file keys
STANDARD_V2_INFO_FILE_KEYS: list[bytes] = [b"length", b"pieces root"]

SUPPORTED_V2_INFO_FILE_KEYS: list[bytes] = STANDARD_V2_INFO_FILE_KEYS

# Hybrid info file keys
SUPPORTED_INFO_FILE_KEYS: list[bytes] = (
    SUPPORTED_V1_INFO_FILE_KEYS + SUPPORTED_V2_INFO_FILE_KEYS
)

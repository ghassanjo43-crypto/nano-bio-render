"""Provider-neutral object storage.

Nothing outside this package imports a provider SDK, holds a provider object or
catches a provider exception. Callers use :func:`object_store` and see opaque
keys, byte iterators, an :class:`ObjectMetadata` dataclass and two exception
types.
"""

from nanobio_studio.app.storage.factory import (
    describe_storage, object_store, reset_object_store,
    set_object_store_for_tests, storage_health, verify_configuration,
)
from nanobio_studio.app.storage.keys import (
    InvalidObjectKey, is_valid_key, new_attachment_key, parse_key,
)
from nanobio_studio.app.storage.objects import (
    ObjectMetadata, ObjectNotFound, ObjectStore, StorageError, StorageHealth,
    StorageNotConfigured,
)

__all__ = [
    "ObjectStore", "ObjectMetadata", "ObjectNotFound", "StorageError",
    "StorageHealth", "StorageNotConfigured",
    "object_store", "set_object_store_for_tests", "reset_object_store",
    "verify_configuration", "storage_health", "describe_storage",
    "new_attachment_key", "is_valid_key", "parse_key", "InvalidObjectKey",
]

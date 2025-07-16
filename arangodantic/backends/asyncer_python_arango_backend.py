from asyncio import sleep

from arangoasync import ArangoServerError
from arangoasync.collection import StandardCollection
from arangoasync.database import StandardDatabase
from shylock import ShylockException
from shylock.backends import ShylockAsyncBackend

DOCUMENT_TTL = 60 * 5  # 5min seems like a reasonable TTL
POLL_DELAY = 1 / 16  # Some balance between high polling and high delay

ERROR_ARANGO_CONFLICT = 1200
ERROR_ARANGO_UNIQUE_CONSTRAINT_VIOLATED = 1210


class ShylockAsyncerArangoDBBackend(ShylockAsyncBackend):
    def __init__(self, db: StandardDatabase, collection_name: str = "shylock"):
        self._check()
        self._db: StandardDatabase = db
        self._coll: None | StandardCollection = None
        self._collection_name: str = collection_name

    @staticmethod
    async def create(
        db: StandardDatabase, collection_name: str = "shylock"
    ) -> "ShylockAsyncerArangoDBBackend":
        """
        Create and initialize the backend
        :param db: An instance of
        aioarangodb.database.StandardDatabase connected to the desired database

        :param collection_name: The name of the collection reserved for shylock
        """
        inst = ShylockAsyncerArangoDBBackend(db, collection_name)
        await inst._init_collection()
        return inst

    async def acquire(self, name: str, block: bool = True) -> bool:
        """
        Try to acquire a lock, potentially wait until it's available
        :param name: Name of the lock
        :param block: Wait for lock
        :return: If lock was successfully acquired - always True if block is True
        """
        while True:
            try:
                await self._db.aql.execute(
                    """
                    INSERT {
                      "name": @name,
                      "expiresAt": DATE_NOW() / 1000 + @ttl
                    } IN @@collection
                    """,
                    bind_vars={
                        "name": name,
                        "ttl": DOCUMENT_TTL,
                        "@collection": self._collection_name,
                    },
                )
                return True
            except ArangoServerError as err:
                if err.error_code in {
                    ERROR_ARANGO_UNIQUE_CONSTRAINT_VIOLATED,
                    ERROR_ARANGO_CONFLICT,
                }:
                    if not block:
                        return False
                    await sleep(POLL_DELAY)
                else:
                    raise

    async def release(self, name: str):
        """
        Release a given lock
        :param name: Name of the lock
        """
        await self._db.aql.execute(
            """
            FOR l IN @@collection
                FILTER l.name == @name
                REMOVE l IN @@collection
            """,
            bind_vars={"name": name, "@collection": self._collection_name},
        )

    async def _init_collection(self):
        if await self._db.has_collection(self._collection_name):
            self._coll = self._db.collection(self._collection_name)
        else:
            self._coll = await self._db.create_collection(
                self._collection_name
            )

        await self._coll.add_index(fields=["name"], type="persistent")
        await self._coll.add_index(fields=["expiresAt"], type="ttl", options={"expireAfter": 0})

    @staticmethod
    def _check():
        if StandardDatabase is None:
            raise ShylockException(
                "No python-arango driver available. "
                "Cannot use Shylock with AsyncerArangoDB backend without it."
            )

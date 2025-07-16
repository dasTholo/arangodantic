from shylock import ShylockAioArangoDBBackend, ShylockException

# from arango.database import AsyncDatabase, StandardDatabase
# from arango.collection import StandardCollection
# from arango.exceptions import ArangoServerError
from arangoasync.database import StandardDatabase, StandardCollection
from arangoasync.exceptions import ArangoServerError

StandardDatabase = StandardDatabase
StandardCollection = StandardCollection
ArangoServerError = ArangoServerError


class ShylockArangoDBBackend(ShylockAioArangoDBBackend):
    def __init__(self, db: StandardDatabase, collection_name: str = "shylock"):
        super().__init__(db, collection_name)

    @staticmethod
    async def create(
            db: StandardDatabase, collection_name: str = "shylock"
    ) -> "ShylockArangoDBBackend":
        """
        Create and initialize the backend
        :param db: An instance of aioarangodb.database.StandardDatabase connected to the desired database
        :param collection_name: The name of the collection reserved for shylock
        """
        inst = ShylockArangoDBBackend(db, collection_name)
        await inst._init_collection()
        return inst

    @staticmethod
    def _check():
        if StandardDatabase is None:
            raise ShylockException(
                "No aioarangodb driver available. Cannot use Shylock with AioArangoDB backend without it."
            )

    async def _init_collection(self):
        """
        Ensure the collection is ready for our use
        """
        if await self._db.has_collection(self._collection_name):
            self._coll = self._db.collection(self._collection_name)
        else:
            self._coll = await self._db.create_collection(self._collection_name)

        await self._coll.add_index(fields=["name"], type="persistent")
        await self._coll.add_index(fields=["expiresAt"], type="ttl", options={"expireAfter": 0})


import random
import string
from decouple import config
from typing import Optional
from uuid import uuid4
import pydantic
import pytest
from arangoasync import ArangoClient
from arangoasync.auth import Auth

from shylock import AsyncLock as Lock

from arangodantic import DocumentModel, EdgeDefinition, EdgeModel, GraphModel, configure

HOSTS = config("HOSTS")
USERNAME = "root"
PASSWORD = config("PASSWORD")
DATABASE = "test"


def rand_str(length: int) -> str:
    """
    Generate a random string for collection names.

    :param length: The length of the random string.
    :return: The random prefix string.
    """
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))

@pytest.fixture(scope="session")
def prefix() -> str:
    return f"test-{rand_str(10)}"

@pytest.fixture
async def client():
    """Provides an ArangoClient instance and ensures it's closed after the test."""
    arango_client = ArangoClient(hosts=HOSTS)
    try:
        yield arango_client
    finally:
        await arango_client.close()


@pytest.fixture
async def db(client, prefix):
    """
    Uses the client to set up the database and configure the library.
    """
    auth = Auth(username=USERNAME, password=PASSWORD)
    try:
        sys_db = await client.db("_system", auth=auth)
        if not await sys_db.has_database(DATABASE):
            await sys_db.create_database(DATABASE)
        test_db = await client.db(DATABASE, auth=auth)
        configure(test_db, prefix=f"{prefix}-", key_gen=uuid4, lock=Lock)
        yield test_db
    finally:
        await client.close()


class Identity(DocumentModel):
    """Dummy identity Arangodantic model."""
    class ArangodanticConfig:
        collection_name: str = "identities"
    name: str = ""


class SubModel(pydantic.BaseModel):
    """Dummy plain pydantic sub-model."""

    text: str = ""


class ExtendedIdentity(Identity):
    """Dummy extended identity Arangodantic model."""

    extra: Optional[str] = None
    sub: Optional[SubModel] = None

    class ArangodanticConfig:
        collection_name = "ext_identities"

    async def before_save(
        self, new: bool, override_extra: Optional[str] = None, **kwargs
    ):
        if override_extra:
            self.extra = override_extra


class Link(EdgeModel):
    """Dummy Arangodantic edge model."""

    type: str


class Person(DocumentModel):
    """Documents describing persons."""

    name: str


class Relation(EdgeModel):
    """Edge documents describing relation between people."""

    kind: str


class SecondaryRelation(EdgeModel):
    """Edge documents describing a secondary relation between people."""

    kind: str


class RelationGraph(GraphModel):
    class ArangodanticConfig:
        edge_definitions = [
            EdgeDefinition(
                edge_collection=Relation,
                from_vertex_collections=[Person],
                to_vertex_collections=[Person],
            )
        ]


class SecondaryRelationGraph(GraphModel):
    class ArangodanticConfig:
        edge_definitions = [
            EdgeDefinition(
                edge_collection=SecondaryRelation,
                from_vertex_collections=[Person],
                to_vertex_collections=[Person],
            )
        ]


@pytest.fixture
async def identity_collection(db):
    await Identity.ensure_collection()
    yield
    await Identity.delete_collection()


@pytest.fixture
async def identity_alice(identity_collection):
    alice = Identity(name="Alice")
    await alice.save()
    yield alice


@pytest.fixture
async def identity_bob(identity_collection):
    bob = Identity(name="Bob")
    await bob.save()
    yield bob


@pytest.fixture
async def extended_identity_collection(db):
    await ExtendedIdentity.ensure_collection()
    yield
    await ExtendedIdentity.delete_collection()


@pytest.fixture
async def link_collection(db):
    await Link.ensure_collection()
    yield
    await Link.delete_collection()


@pytest.fixture
async def relation_graph(db):
    await RelationGraph.ensure_graph()
    yield
    await RelationGraph.delete_graph(ignore_missing=True, drop_collections=True)


@pytest.fixture
async def secondary_relation_graph(db):
    await SecondaryRelationGraph.ensure_graph()
    yield
    await SecondaryRelationGraph.delete_graph(
        ignore_missing=True, drop_collections=True
    )

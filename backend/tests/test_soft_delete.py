import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from backend import database, storage

# Setup in-memory DB for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    database.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_soft_delete_flow(db_session):
    # 1. Insert two properties from same source
    props_batch_1 = [
        {
            "link": "http://example.com/1",
            "title": "Prop 1",
            "source": "test_source",
            "code": "001",
            "price": "1000",
            "location": "Loc 1",
            "latitude": 6.17,
            "longitude": -75.58,
        },
        {
            "link": "http://example.com/2",
            "title": "Prop 2",
            "source": "test_source",
            "code": "002",
            "price": "2000",
            "location": "Loc 2",
            "latitude": 6.17,
            "longitude": -75.58,
        },
    ]

    storage.save_properties(db_session, props_batch_1)

    # Verify both are active
    all_props = db_session.query(database.Property).all()
    assert len(all_props) == 2
    assert all_props[0].deleted_at is None
    assert all_props[1].deleted_at is None

    # 2. Run batch 2, missing Prop 2
    props_batch_2 = [
        {
            "link": "http://example.com/1",
            "title": "Prop 1 Updated",
            "source": "test_source",
            "code": "001",
            "price": "1100",
            "location": "Loc 1",
            "latitude": 6.17,
            "longitude": -75.58,
        }
    ]

    result = storage.save_properties(db_session, props_batch_2)

    # Verify updated stats
    assert result["soft_deleted"] == 1

    # Verify Prop 2 is soft deleted
    prop2 = (
        db_session.query(database.Property)
        .filter_by(link="http://example.com/2")
        .first()
    )
    assert prop2.deleted_at is not None

    # Verify Prop 1 is still active and updated
    prop1 = (
        db_session.query(database.Property)
        .filter_by(link="http://example.com/1")
        .first()
    )
    assert prop1.deleted_at is None
    assert prop1.price == "1100"

    # 3. Process another source, should not affect test_source props
    props_batch_other = [
        {
            "link": "http://other.com/1",
            "title": "Other Prop 1",
            "source": "other_source",
            "location": "Loc Other",
        }
    ]
    storage.save_properties(db_session, props_batch_other)

    prop2_check = (
        db_session.query(database.Property)
        .filter_by(link="http://example.com/2")
        .first()
    )
    assert prop2_check.deleted_at is not None  # Should stay deleted

    # 4. Re-introduce Prop 2 (Un-delete)
    props_batch_3 = [
        {
            "link": "http://example.com/1",
            "source": "test_source",
        },
        {
            "link": "http://example.com/2",
            "title": "Prop 2 Back",
            "source": "test_source",
        },
    ]
    storage.save_properties(db_session, props_batch_3)

    prop2_back = (
        db_session.query(database.Property)
        .filter_by(link="http://example.com/2")
        .first()
    )
    assert prop2_back.deleted_at is None
    assert prop2_back.title == "Prop 2 Back"

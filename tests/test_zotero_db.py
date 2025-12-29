"""Tests for Zotero database access."""

import sqlite3

import pytest

from zotero2ai.zotero.db import ZoteroDB


@pytest.fixture
def mock_zotero_db(tmp_path):
    """Create a temporary Zotero database with some data."""
    db_path = tmp_path / "zotero.sqlite"
    conn = sqlite3.connect(str(db_path))

    # Create required tables
    conn.executescript("""
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, itemTypeID INTEGER, libraryID INTEGER, dateAdded TEXT, dateModified TEXT);
        CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
        CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
        CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, key TEXT, collectionName TEXT, parentCollectionID INTEGER, libraryID INTEGER);
        CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
        CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT);
        CREATE TABLE itemCreators (itemID INTEGER, creatorID INTEGER, creatorTypeID INTEGER, orderIndex INTEGER);
        CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER);
        CREATE TABLE deletedItems (itemID INTEGER);
        
        -- Insert metadata
        INSERT INTO itemTypes (itemTypeID, typeName) VALUES (1, 'journalArticle'), (2, 'book'), (3, 'attachment'), (4, 'note');
        INSERT INTO fields (fieldID, fieldName) VALUES (1, 'title'), (2, 'abstractNote'), (3, 'date');
        
        -- Insert collections
        INSERT INTO collections (collectionID, key, collectionName, parentCollectionID, libraryID) 
        VALUES (1, 'C1', 'Research', NULL, 1), (2, 'C2', 'Deep Learning', 1, 1);
        
        -- Insert items
        INSERT INTO items (itemID, key, itemTypeID, libraryID, dateAdded, dateModified)
        VALUES (1, 'I1', 1, 1, '2023-01-01T10:00:00Z', '2023-01-01T10:00:00Z'),
               (2, 'I2', 2, 1, '2023-02-01T10:00:00Z', '2023-02-01T10:00:00Z');
        
        -- Insert titles
        INSERT INTO itemDataValues (valueID, value) VALUES (1, 'Attention is All You Need'), (2, 'Deep Learning Book');
        INSERT INTO itemData (itemID, fieldID, valueID) VALUES (1, 1, 1), (2, 1, 2);
        
        -- Insert creators
        INSERT INTO creators (creatorID, firstName, lastName) VALUES (1, 'Ashish', 'Vaswani'), (2, 'Ian', 'Goodfellow');
        INSERT INTO itemCreators (itemID, creatorID, creatorTypeID, orderIndex) VALUES (1, 1, 1, 0), (2, 2, 1, 0);
    """)

    conn.commit()
    conn.close()
    return db_path


def test_get_collections(mock_zotero_db):
    with ZoteroDB(mock_zotero_db) as db:
        cols = db.get_collections()
        assert len(cols) == 2
        assert cols[0].name == "Research"
        assert cols[0].full_path == "Research"
        assert cols[1].name == "Deep Learning"
        assert cols[1].full_path == "Research / Deep Learning"


def test_get_item_count(mock_zotero_db):
    with ZoteroDB(mock_zotero_db) as db:
        assert db.get_item_count() == 2


def test_get_recent_items(mock_zotero_db):
    with ZoteroDB(mock_zotero_db) as db:
        items = db.get_recent_items(limit=5)
        assert len(items) == 2
        assert items[0].title == "Deep Learning Book"  # Added in Feb vs Jan
        assert items[0].creators == ["Goodfellow, Ian"]


def test_search_by_title(mock_zotero_db):
    with ZoteroDB(mock_zotero_db) as db:
        results = db.search_by_title("Attention")
        assert len(results) == 1
        assert results[0].title == "Attention is All You Need"
        assert results[0].key == "I1"

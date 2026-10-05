from db_injector.db_interactor import db_config, identify_credentials
import yaml
from sqlalchemy import create_engine

def test_identify_credentials():
    #ensure that the credentials dict contains values
    #requires the yaml file argument
    credentials_dict = identify_credentials()
    assert credentials_dict is not None
    assert credentials_dict['DB_USER'] is not None
    assert credentials_dict['DB_PASSWORD'] is not None
    assert credentials_dict['HOST'] is not None
    #assert credentials_dict['PORT'] is not None

def test_create_engine():
    #db_config() rather than identify_credentials(), which returns LOCAL_PORT and
    #no DATABASE, so the PORT lookup below used to raise KeyError
    credentials_dict = db_config()
    engine = create_engine(f'mysql+pymysql://{credentials_dict["DB_USER"]}:{credentials_dict["DB_PASSWORD"]}@{credentials_dict["HOST"]}:{credentials_dict["PORT"]}/postgres')
    assert engine is not None


# ══ APPENDED TESTS ═══════════════════════════════════════════════════════════
# No MySQL and no SSH: build_engine's URL is checked by intercepting
# create_engine, and write_table runs against in-memory SQLite.

import pandas as pd
import pytest
from db_injector import db_interactor

'''
FIXTURES
a csv to ingest
'''

@pytest.fixture
def csv_path():
    csv_path = '/Users/casita/Documents/2026 Spoilage - Sheet1.csv'
    return csv_path

def test_db_config_returns_full_key_set():
    config = db_interactor.db_config()
    assert set(config) == set(db_interactor.DB_KEYS)
    assert all(config.values())


#IDK what this is doing
def test_read_source_reads_csv(tmp_path):
    csv = tmp_path / "rows.csv"
    csv.write_text("name,amount\nada,3\ngrace,4\n")
    df = db_interactor.read_source(str(csv))
    assert list(df.columns) == ["name", "amount"]
    assert len(df) == 2

#nice to have, but who cares
def test_read_source_rejects_unknown_extension(tmp_path):
    junk = tmp_path / "rows.parquet"
    junk.write_text("")
    with pytest.raises(ValueError, match="Unsupported source file type"):
        db_interactor.read_source(str(junk))

#ensure that the path specified is reachable as provided (a location on my local)
def test_read_source(csv_path):
    table = db_interactor.read_source(csv_path)
    assert table is not None
    assert len(table) > 0
    assert len(table.columns) > 0


#don't know what kind of sql server this is hitting
def test_build_engine_uses_tunnel_port(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        db_interactor, "create_engine", lambda url, **kw: captured.update(url=url, kw=kw)
    )
    db_interactor.build_engine(port=49152)
    assert ":49152/" in captured["url"]
    assert captured["url"].startswith("mysql+pymysql://")


def test_write_table_writes_rows_and_returns_count():
    engine = create_engine("sqlite://")  # in-memory, no driver install needed
    df = pd.DataFrame({"name": ["ada", "grace"], "amount": [3, 4]})
    with engine.begin() as conn:
        rows = db_interactor.write_table(df, "people", conn)
    assert rows == 2
    with engine.connect() as conn:
        assert len(pd.read_sql("SELECT * FROM people", conn)) == 2


def test_resolve_dtypes_maps_repeated_flags_and_rejects_unknown():
    columns = ["antecedents_list", "consequents_list", "support"]
    resolved = db_interactor.resolve_dtypes(
        ["antecedents_list=JSON", "consequents_list=json", "support=FLOAT"],
        columns,
    )
    assert resolved["antecedents_list"] is db_interactor.MySQLJSON
    assert resolved["consequents_list"] is db_interactor.MySQLJSON
    assert resolved["support"] is db_interactor.Float
    with pytest.raises(ValueError, match="Unknown dtype"):
        db_interactor.resolve_dtypes(["antecedents_list=SET"], columns)
    with pytest.raises(ValueError, match="not in the source file"):
        db_interactor.resolve_dtypes(["missing=JSON"], columns)


def test_write_table_parses_json_list_text():
    engine = create_engine("sqlite://")
    df = pd.DataFrame({
        "antecedents_list": ["['Cheese', 'Produce Herbs and Spices, Fresh']"],
        "consequents_list": ['["PRODUCE"]'],
        "support": [0.2],
    })
    dtype = db_interactor.resolve_dtypes(
        ["antecedents_list=JSON", "consequents_list=JSON"],
        df.columns,
    )
    with engine.begin() as conn:
        db_interactor.write_table(df, "rules", conn, dtype=dtype)
    with engine.connect() as conn:
        stored = pd.read_sql("SELECT antecedents_list, consequents_list FROM rules", conn)
        types = dict(db_interactor.table_column_types(conn, "rules"))
    assert stored.loc[0, "antecedents_list"] == '["Cheese", "Produce Herbs and Spices, Fresh"]'
    assert stored.loc[0, "consequents_list"] == '["PRODUCE"]'
    assert types["antecedents_list"] == "JSON"
    assert types["consequents_list"] == "JSON"
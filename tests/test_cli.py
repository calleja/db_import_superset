import pytest
from db_injector.cli import build_parser, inject

def test_build_parser():
    #ensure that the credentials dict contains values
    parser = build_parser()
    args = parser.parse_args(['/here','nombre','--yaml-path','yaml'])
    assert parser is not None
    assert args.filepath == '/here'
    assert args.table_name == 'nombre'
    assert args.yaml_path == 'yaml'
    assert args.dtype is None


def test_build_parser_repeats_dtype():
    parser = build_parser()
    args = parser.parse_args([
        "ass_df.csv",
        "association_rules",
        "--dtype", "antecedents_list=JSON",
        "--dtype", "consequents_list=JSON",
    ])
    assert args.dtype == ["antecedents_list=JSON", "consequents_list=JSON"]
    

def test_create_engine():
    pass
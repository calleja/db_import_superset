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
    

def test_create_engine():
    pass
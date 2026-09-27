from scripts.export_schemas import main


def test_schema_drift():
    assert main(["--check"]) == 0

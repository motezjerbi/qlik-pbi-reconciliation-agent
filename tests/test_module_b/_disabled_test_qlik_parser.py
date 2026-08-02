import sys
from pathlib import Path
import pytest

sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
from module_b.qlik_parser import parse_qlik_script


@pytest.fixture
def temp_script(tmp_path):
    """Crée un script Qlik minimal contenant plusieurs patterns connus."""
    content = """
///$tab Variables
SET vTest = 1;

///$tab Facts
Sales:
LOAD * INLINE [A,B\\n1,2];

left join(Sales)
LOAD * INLINE [A,C\\n1,3];

Result:
LOAD *,
ApplyMap('MAP', A, 'N/A') as D
Resident Sales;
"""
    script_path = tmp_path / "test_script.qvs"
    script_path.write_text(content, encoding="utf-8")
    return str(script_path)


def test_detecte_left_join(temp_script):
    patterns = parse_qlik_script(temp_script)
    pattern_names = [p["pattern"] for p in patterns]
    assert "left_join" in pattern_names


def test_detecte_applymap(temp_script):
    patterns = parse_qlik_script(temp_script)
    pattern_names = [p["pattern"] for p in patterns]
    assert "mapping_applymap" in pattern_names


def test_ignore_reglages_regionaux(tmp_path):
    """Les réglages régionaux du bloc Main ne doivent jamais être détectés comme patterns."""
    content = """
///$tab Main
SET ThousandSep=',';
SET DateFormat='M/D/YYYY';

///$tab Variables
SET vRealVariable = 1;
"""
    script_path = tmp_path / "main_only.qvs"
    script_path.write_text(content, encoding="utf-8")

    patterns = parse_qlik_script(str(script_path))
    expressions = [p["expression_source"] for p in patterns]

    assert not any("ThousandSep" in e for e in expressions)
    assert not any("DateFormat" in e for e in expressions)


def test_script_sans_pattern_retourne_liste_vide(tmp_path):
    content = "///$tab Facts\nSales:\nLOAD * INLINE [A\\n1];"
    script_path = tmp_path / "empty.qvs"
    script_path.write_text(content, encoding="utf-8")

    patterns = parse_qlik_script(str(script_path))
    assert patterns == []
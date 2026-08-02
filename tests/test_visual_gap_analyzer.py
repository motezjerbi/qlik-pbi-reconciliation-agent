# tests/test_visual_gap_analyzer.py
"""
Tests de non-régression pour visual_gap_analyzer.py.

Inclut le cas concret découvert avec l'utilisateur : la colonne PBI malformée
'ChannelID;ChannelName' (probable cause du visuel "Sales by channel" cassé).

Lancer : pytest tests/test_visual_gap_analyzer.py -v
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from module_a.visual_gap_analyzer import (
    detect_dimension_gaps,
    detect_visual_count_gaps,
    detect_malformed_columns,
)


class TestDimensionGaps:
    def test_dimension_master_sans_colonne_pbi_est_signalee(self):
        qlik = {"dimensions": [{"name": "Région", "field": "Region"}], "visuals": []}
        pbi = {"columns": [{"table": "Sales", "name": "Autre Colonne Sans Rapport"}]}
        findings = detect_dimension_gaps(qlik, pbi)
        assert len(findings) == 1
        assert "Région" in findings[0]["libelle"]

    def test_dimension_avec_colonne_correspondante_non_signalee(self):
        qlik = {"dimensions": [{"name": "Région", "field": "Region"}], "visuals": []}
        pbi = {"columns": [{"table": "Sales", "name": "Region"}]}
        findings = detect_dimension_gaps(qlik, pbi)
        assert findings == []

    def test_dimension_ad_hoc_dans_un_visuel_est_verifiee(self):
        """Cas 'Channel' : jamais promu en dimension master, seulement utilisé
        dans un visuel — doit quand même être vérifié."""
        qlik = {
            "dimensions": [],
            "visuals": [{"name": "Sales by channel", "sheet": "S1", "dimensions": ["Channel"]}],
        }
        pbi = {"columns": [{"table": "Sales", "name": "Autre Colonne"}]}
        findings = detect_dimension_gaps(qlik, pbi)
        assert len(findings) == 1
        assert "Channel" in findings[0]["libelle"]


class TestVisualCountGaps:
    def test_page_introuvable_signalee(self):
        qlik = {"visuals": [{"sheet": "Feuille Rare", "name": "V1"}]}
        pbi = {"visuals": [{"page": "Page Totalement Differente", "name": "V2"}]}
        findings = detect_visual_count_gaps(qlik, pbi)
        assert any("introuvable" in f["libelle"] for f in findings)

    def test_meme_nombre_de_visuels_non_signale(self):
        qlik = {"visuals": [{"sheet": "Executive Overview", "name": "V1"}]}
        pbi = {"visuals": [{"page": "Executive Overview", "name": "V2"}]}
        findings = detect_visual_count_gaps(qlik, pbi)
        assert findings == []

    def test_moins_de_visuels_cote_pbi_signale(self):
        qlik = {"visuals": [
            {"sheet": "Executive Overview", "name": "V1"},
            {"sheet": "Executive Overview", "name": "V2"},
            {"sheet": "Executive Overview", "name": "V3"},
        ]}
        pbi = {"visuals": [{"page": "Executive Overview", "name": "V1"}]}
        findings = detect_visual_count_gaps(qlik, pbi)
        assert any("manquants" in f["libelle"] for f in findings)


class TestColonnesMalformees:
    def test_detecte_colonne_avec_point_virgule(self):
        pbi = {"columns": [{"table": "SalesChannels", "name": "ChannelID;ChannelName"}]}
        findings = detect_malformed_columns(pbi)
        assert len(findings) == 1
        assert "ChannelID;ChannelName" in findings[0]["libelle"]
        assert findings[0]["criticite"] == "MAJEUR"

    def test_colonne_normale_non_signalee(self):
        pbi = {"columns": [{"table": "Sales", "name": "Customer ID"}]}
        findings = detect_malformed_columns(pbi)
        assert findings == []

    def test_rownumber_technique_ignoree(self):
        """Les colonnes techniques internes (RowNumber-<guid>) ne doivent pas
        être signalées même si leur nom est long/inhabituel."""
        pbi = {"columns": [{"table": "Sales", "name": "RowNumber-ABC123;DEF456"}]}
        findings = detect_malformed_columns(pbi)
        assert findings == []
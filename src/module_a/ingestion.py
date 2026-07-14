import pandas as pd
from pathlib import Path

def load_export(filepath: str) -> pd.DataFrame:
    """Charge un export CSV ou Excel (Qlik ou Power BI) dans un DataFrame."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    if path.suffix.lower() in [".xlsx", ".xls"]:
        return pd.read_excel(path)
    else:
        return pd.read_csv(path)

if __name__ == "__main__":
    qlik_df = load_export("data/samples/case_01_test/qlik/data_export.csv")
    pbi_df = load_export("data/samples/case_01_test/powerbi/data_export.csv")

    print("--- Export Qlik ---")
    print(qlik_df)
    print("\n--- Export Power BI ---")
    print(pbi_df)
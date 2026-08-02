import re
import pandas as pd
from io import StringIO
from pathlib import Path

def extract_qlik_inline_table(qvs_path: str, table_name: str = "Sales") -> pd.DataFrame:
    """Extrait une table INLINE du script Qlik sans exporter depuis Qlik Sense."""
    content = Path(qvs_path).read_text(encoding="utf-8")
    
    # Pattern pour trouver : Sales: LOAD ... INLINE [ ... ] ;
    table_pattern = rf"{table_name}\s*:\s*LOAD.*?INLINE\s*\[(.*?)\]\s*;"
    match = re.search(table_pattern, content, re.IGNORECASE | re.DOTALL)
    
    if not match:
        raise ValueError(f"Table INLINE '{table_name}' introuvable dans {qvs_path}")
    
    raw_csv = match.group(1).strip()
    df = pd.read_csv(StringIO(raw_csv))
    
    # Transformations du script Qlik (Year, Month)
    if "Date" in df.columns:
        dates = pd.to_datetime(df["Date"], errors="coerce")
        df["OrderDate"] = dates
        df["Year"] = dates.dt.year
        df["Month"] = dates.dt.month
        df = df.drop(columns=["Date"])
    
    return df
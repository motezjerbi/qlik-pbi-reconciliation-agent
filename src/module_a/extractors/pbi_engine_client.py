"""
Client Engine (ADOMD.NET) pour Power BI Desktop - Module A
Équivalent du qlik_engine_client.py, mais pour le moteur Analysis Services
que Power BI Desktop lance en local quand un .pbix est ouvert.
"""
import sys
import os

ADOMD_DIR = r"C:\Program Files\Microsoft.NET\ADOMD.NET\110"
sys.path.append(ADOMD_DIR)
os.environ["PATH"] = ADOMD_DIR + os.pathsep + os.environ["PATH"]

from pathlib import Path
from typing import Dict, List
import psutil
from pyadomd import Pyadomd  # doit venir après les 3 lignes ci-dessus


def find_pbi_port() -> int:
    """Trouve le port local du moteur Power BI (msmdsrv.exe) via psutil."""
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] and proc.info["name"].lower() == "msmdsrv.exe":
            pid = proc.pid
            for conn in psutil.Process(pid).connections(kind="tcp"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr.ip == "127.0.0.1":
                    return conn.laddr.port
    raise RuntimeError(
        "msmdsrv.exe introuvable — vérifie que Power BI Desktop "
        "est ouvert avec le .pbix chargé."
    )


def _run_dax(conn, query: str) -> List[Dict]:
    with conn.cursor().execute(query) as cur:
        cols = [c.name for c in cur.description]
        rows = cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]


def extract_app_structure(pbix_path: str) -> Dict:
    """Extraction complète pour le Module A, via connexion live au moteur."""
    result = {
        "tables": [], "measures": [], "dimensions": [], "kpis": [], "columns": [],
        "power_query": [], "roles": [], "relationships": [],
        "metadata": {"source": "adomd_engine", "file": Path(pbix_path).name},
    }

    port = find_pbi_port()
    conn_str = f"Provider=MSOLAP;Data Source=localhost:{port};"

    with Pyadomd(conn_str) as conn:
        print(f"🔌 Connecté au moteur Power BI (port {port})")

        tables = _run_dax(conn, "SELECT [ID], [Name] FROM $SYSTEM.TMSCHEMA_TABLES")
        table_id_to_name = {}
        for t in tables:
            name = t.get("Name")
            if name and not name.startswith("LocalDateTable"):
                result["tables"].append({"name": name})
                table_id_to_name[t.get("ID")] = name
        print(f"  📊 Tables : {len(result['tables'])}")

        # --- Colonnes (pour comparer les dimensions Qlik aux colonnes PBI) ---
        column_id_to_name = {}
        try:
            columns = _run_dax(
                conn,
                "SELECT [ID], [TableID], [ExplicitName] FROM $SYSTEM.TMSCHEMA_COLUMNS"
            )
            for c in columns:
                col_name = c.get("ExplicitName")
                table_name = table_id_to_name.get(c.get("TableID"), "")
                if col_name and table_name:
                    result["columns"].append({"table": table_name, "name": col_name})
                    column_id_to_name[c.get("ID")] = f"{table_name}[{col_name}]"
            print(f"  📐 Colonnes : {len(result['columns'])}")
        except Exception as e:
            print(f"  ⚠️ Colonnes non récupérées : {e}")

        # --- Relations entre tables ---
        try:
            rels = _run_dax(
                conn,
                "SELECT [FromTableID], [FromColumnID], [ToTableID], [ToColumnID], "
                "[IsActive], [CrossFilteringBehavior] FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS"
            )
            for r in rels:
                from_table = table_id_to_name.get(r.get("FromTableID"), "")
                to_table = table_id_to_name.get(r.get("ToTableID"), "")
                if from_table and to_table:
                    result["relationships"].append({
                        "from_table": from_table,
                        "from_column": column_id_to_name.get(r.get("FromColumnID"), ""),
                        "to_table": to_table,
                        "to_column": column_id_to_name.get(r.get("ToColumnID"), ""),
                        "is_active": bool(r.get("IsActive")),
                        "cross_filter": r.get("CrossFilteringBehavior"),
                    })
            print(f"  🔗 Relations : {len(result.get('relationships', []))}")
        except Exception as e:
            print(f"  ⚠️ Relations non récupérées : {e}")

        # --- Power Query (code M) — table_id_to_name déjà construit ci-dessus ---
        try:
            partitions = _run_dax(
                conn,
                "SELECT [TableID], [QueryDefinition] FROM $SYSTEM.TMSCHEMA_PARTITIONS"
            )
            for p in partitions:
                m_code = (p.get("QueryDefinition") or "").strip()
                table_name = table_id_to_name.get(p.get("TableID"), "")
                if m_code and table_name:
                    result["power_query"].append({"table": table_name, "m_code": m_code})
            print(f"  🔧 Requêtes Power Query : {len(result['power_query'])}")
        except Exception as e:
            print(f"  ⚠️ Power Query non récupéré : {e}")

        # --- Rôles de sécurité (RLS) — pour vérifier Section Access ---
        try:
            roles_raw = _run_dax(conn, "SELECT [ID], [Name] FROM $SYSTEM.TMSCHEMA_ROLES")
            role_id_to_name = {r.get("ID"): r.get("Name") for r in roles_raw if r.get("Name")}

            roles_with_filter = set()
            try:
                perms = _run_dax(
                    conn,
                    "SELECT [RoleID], [TableID], [FilterExpression] FROM $SYSTEM.TMSCHEMA_TABLE_PERMISSIONS"
                )
                for p in perms:
                    role_name = role_id_to_name.get(p.get("RoleID"), "")
                    table_name = table_id_to_name.get(p.get("TableID"), "")
                    filt = (p.get("FilterExpression") or "").strip()
                    if role_name and filt:
                        roles_with_filter.add(role_name)
                        result["roles"].append({
                            "role": role_name, "table": table_name, "filter_expression": filt
                        })
            except Exception:
                pass  # certaines versions du moteur n'exposent pas TMSCHEMA_TABLE_PERMISSIONS

            # Rôles déclarés mais sans filtre associé (role vide, sécurité incomplète)
            for rname in role_id_to_name.values():
                if rname not in roles_with_filter:
                    result["roles"].append({"role": rname, "table": "", "filter_expression": ""})

            print(f"  🔒 Rôles de sécurité (RLS) : {len(role_id_to_name)}")
        except Exception as e:
            print(f"  ⚠️ Rôles RLS non récupérés : {e}")

        measures = _run_dax(
            conn, "SELECT [Name], [Expression] FROM $SYSTEM.TMSCHEMA_MEASURES"
        )
        for m in measures:
            name = m.get("Name")
            expr = m.get("Expression")
            if not name:
                continue
            result["measures"].append({"name": name, "dax": expr})

            error_msg = None
            try:
                value_rows = _run_dax(conn, f'EVALUATE ROW("v", [{name}])')
                value = list(value_rows[0].values())[0] if value_rows else None
            except Exception as e:
                value = None
                # Première ligne seulement : le reste est une stack trace .NET, pas utile
                # au consultant et inutilisable telle quelle comme "cause probable".
                error_msg = str(e).split("\n")[0].strip()
                print(f"  ⚠️ Impossible d'évaluer {name}: {error_msg}")

            result["kpis"].append({
                "name": name,
                "value": value,
                "expression": expr,
                "error": error_msg,
            })
            if error_msg is None:
                print(f"  ✅ KPI : {name} = {value}")

    print(f"\n✅ Extraction terminée : {len(result['tables'])} tables, "
          f"{len(result['measures'])} mesures, {len(result['kpis'])} KPIs")
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage : python pbi_engine_client.py <chemin_fichier.pbix>")
        sys.exit(1)
    result = extract_app_structure(sys.argv[1])
"""
Taxonomie des patterns Qlik Sense
Référentiel central pour tous les types de patterns détectables
"""

TAXONOMY_PATTERNS = {
    # === ANALYSE ===
    "set_analysis": {
        "pattern": r"(?i)(set_analysis|set analysis|\{[<{].*?[>}]\})",
        "category": "ANALYSIS",
        "complexity": 3,
        "description": "Set analysis dans Qlik (ex: {<Year={2025}>})",
        "dax_equivalent": "CALCULATE avec FILTER",
        "priority": "HAUTE",
        "examples": [
            "{<Year={$(vCurrentYear)}>}",
            "{<Year={$(vMaxYear)},Month={$(vMaxMonth)}>}"
        ]
    },
    
    # === VARIABLES ===
    "variable_dollar_expansion": {
        "pattern": r"(?i)\$\([^)]+\)",
        "category": "VARIABLE",
        "complexity": 2,
        "description": "Expansion de variable Qlik (ex: $(vCurrentYear))",
        "dax_equivalent": "VAR ... = ...",
        "priority": "HAUTE",
        "examples": [
            "$(vTableName)",
            "$(=$(vCurrentYear))",
            "$(vMaxYear)"
        ]
    },
    "variable_declaration": {
        "pattern": r"(?i)^\s*SET\s+([A-Za-z_]\w*)\s*=",
        "category": "VARIABLE",
        "complexity": 1,
        "description": "Déclaration de variable Qlik (SET vName = value)",
        "dax_equivalent": "VAR variable_name = value",
        "priority": "HAUTE",
        "examples": [
            "SET vCurrentYear = Year(Today())",
            "SET vTableName = 'Sales'"
        ]
    },
    
    # === MAPPINGS ===
    "mapping_applymap": {
        "pattern": r"(?i)ApplyMap\s*\([^)]+\)",
        "category": "MAPPING",
        "complexity": 3,
        "description": "ApplyMap pour mapping de données",
        "dax_equivalent": "LOOKUPVALUE",
        "priority": "HAUTE",
        "examples": [
            "ApplyMap('MAP_PRODUCT_GROUP', ProductID, 'N/A')"
        ]
    },
    "mapping_load": {
        "pattern": r"(?i)Mapping\s+LOAD",
        "category": "MAPPING",
        "complexity": 3,
        "description": "Mapping LOAD pour tables de correspondance",
        "dax_equivalent": "Table de correspondance DAX",
        "priority": "MOYENNE",
        "examples": [
            "Mapping LOAD ProductID, ProductGroup FROM ..."
        ]
    },
    
    # === SUBROUTINES ===
    "subroutine_definition": {
        "pattern": r"(?i)^\s*SUB\s+([A-Za-z_]\w*)\s*\([^)]*\)",
        "category": "SUBROUTINE",
        "complexity": 4,
        "description": "Définition de subroutine Qlik",
        "dax_equivalent": "Custom function / Power Query M",
        "priority": "MOYENNE",
        "examples": [
            "SUB LoadFile(FileName, TableName)"
        ]
    },
    "subroutine_call": {
        "pattern": r"(?i)^\s*CALL\s+([A-Za-z_]\w*)\s*\([^)]*\)",
        "category": "SUBROUTINE",
        "complexity": 2,
        "description": "Appel de subroutine Qlik",
        "dax_equivalent": "Function call / Power Query",
        "priority": "MOYENNE",
        "examples": [
            "CALL LoadFile('Channels', 'SalesChannels')"
        ]
    },
    
    # === GROUP BY ===
    "resident_group_by": {
        "pattern": r"(?i)Resident\s+(\w+)\s+Group By",
        "category": "GROUP_BY",
        "complexity": 3,
        "description": "Group By sur table Resident",
        "dax_equivalent": "GROUPBY + SUMMARIZE",
        "priority": "MOYENNE",
        "examples": [
            "Resident Sales Group By CustomerID"
        ]
    },
    
    # === JOINS ===
    "left_join": {
        "pattern": r"(?i)^\s*left join\s*",
        "category": "JOIN",
        "complexity": 3,
        "description": "Left Join dans le script Qlik",
        "dax_equivalent": "NATURALLEFTOUTERJOIN",
        "priority": "MOYENNE",
        "examples": [
            "left join(Sales) LOAD ..."
        ]
    },
    
    # === LOAD STATEMENTS ===
    "load_inline": {
        "pattern": r"(?i)LOAD\s+\*\s+INLINE\s*\[",
        "category": "LOAD",
        "complexity": 2,
        "description": "Table INLINE dans le script Qlik",
        "dax_equivalent": "Données intégrées dans Power Query",
        "priority": "HAUTE",
        "examples": [
            "LOAD * INLINE [OrderID, Product]"
        ]
    },
    "load_from_file": {
        "pattern": r"(?i)LOAD\s+.*?\s+FROM\s+['\"][^'\"]+['\"]",
        "category": "LOAD",
        "complexity": 2,
        "description": "LOAD depuis fichier source",
        "dax_equivalent": "Power Query Source",
        "priority": "HAUTE",
        "examples": [
            "LOAD SalesAmount FROM 'sales_data.xlsx'"
        ]
    }
}

# Mapping de priorité
PRIORITY_MAP = {
    "HAUTE": 3,
    "MOYENNE": 2,
    "BASSE": 1
}

# Mapping de complexité
COMPLEXITY_MAP = {
    1: "FACILE",
    2: "MOYENNE",
    3: "COMPLEXE",
    4: "TRES_COMPLEXE"
}

def get_pattern_info(pattern_name: str) -> dict:
    """Récupère les informations d'un pattern."""
    return TAXONOMY_PATTERNS.get(pattern_name, {})

def get_patterns_by_category(category: str) -> list:
    """Récupère tous les patterns d'une catégorie."""
    return [
        (name, info) for name, info in TAXONOMY_PATTERNS.items()
        if info.get("category") == category
    ]

def get_priority_score(priority: str) -> int:
    """Récupère le score de priorité."""
    return PRIORITY_MAP.get(priority, 1)
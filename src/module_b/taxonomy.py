TAXONOMY_PATTERNS = {
    "set_analysis": r"\{<.*?>\}",
    "aggr": r"Aggr\s*\(",
    "section_access": r"Section\s+Access",
    "generic_load": r"Generic\s+Load",
    "variable_dollar_expansion": r"\$\(.*?\)",
    "variable_declaration": r"(?:LET|SET)\s+\w+\s*=",
    "mapping_applymap": r"ApplyMap\s*\(",
    "mapping_load": r"Mapping\s*\n?\s*LOAD",
    "subroutine_definition": r"SUB\s+\w+\s*\(",
    "subroutine_call": r"CALL\s+\w+\s*\(",
    "resident_group_by": r"Resident\s+\w+\s*\n?\s*Group\s+By",
    "left_join": r"[Ll]eft\s+[Jj]oin\s*\(",
}
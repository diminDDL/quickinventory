test_str1 = "16V 47uF X5R ±10% 1210  Multilayer Ceramic Capacitors MLCC - SMD/SMT ROHS"
test_str2 = "125mW Thick Film Resistors 150V ±100ppm/℃ ±5% -55℃~+155℃ 1.8kΩ 0805 Chip Resistor - Surface Mount ROHS"
test_str3 = "47uF 6.3V ±20% CASE-A-3216 Tantalum Capacitors ROHS"
test_str4 = "16V 2.2uF X5R ±10% 0805 Multilayer Ceramic Capacitors MLCC - SMD/SMT ROHS "
test_str5 = " 	1uH ±20% 3.3mΩ 28A SMD,10x11.5x4mm Power Inductors ROHS "
test_str6 = "3A 22uH ±20% 130mΩ SMD,7.1x6.6x3mm Power Inductors ROHS "
test_str7 = "3 A 22 uH ± 20 % 130 mΩ SMD,7.1x6.6x3mm Power Inductors ROHS "

test_str8 = "125kW 33µA Special Character type one"
test_str9 = "33μV Special Character type one"

def __is_number_str(s):
    """Check if a string represents a valid number (handles decimals and commas)."""
    s_clean = s.replace(',', '')  # Remove commas from numbers
    if s_clean == '':
        return False
    if s_clean.count('.') > 1:  # More than one decimal point is invalid
        return False
    # Check if string is digits after removing one decimal point
    return s_clean.replace('.', '', 1).isdigit()

def parseComponent(str):
    """
    Parses electronic component descriptions to extract key specifications.
    Handles spaces between values and units, and extracts tolerance percentages.
    
    Approach:
    1. Preprocess string to merge separated value-unit pairs
    2. Define unit categories and combine for quick lookup
    3. Process tokens to extract param information
    4. Return dictionary with found specifications
    
    Steps:
    - Tokenize and merge value-unit pairs
    - Check each token against unit lists (longest units first)
    - Extract tolerance by cleaning % values
    - Return any found specifications
    """

    # Normalize micro characters to 'u'
    str = str.replace(chr(181), "u").replace(chr(956), "u")

    # Unit definitions for different component types
    cap_end = ["f", "mf", "uf", "μf", "nf", "pf"]
    res_end = ["k", "m", "g", "r", "kω", "mω", "gω", "ω", "kohm", "mohm", "gohm", "ohm", "kohms", "mohms", "gohms", "ohms"]
    ind_end = ["mh", "uh", "μh", "nh", "ph"]
    volt_end = ["v", "mv", "uv", "vv"]
    amp_end = ["a", "ma", "ua"]
    power_end = ["kw", "w", "mw", "uw", "vw"]
    tolerance_end = ["%"]
    
    # Create combined set of all units for token merging
    all_units = set(cap_end + res_end + ind_end + volt_end + amp_end + power_end + tolerance_end)
    
    # Preprocessing: Merge separated value-unit pairs
    tokens = str.strip().replace("±", "").split()
    new_tokens = []
    i = 0
    while i < len(tokens):
        # Handle value-unit pairs separated by spaces
        if i < len(tokens) - 1 and __is_number_str(tokens[i]) and tokens[i+1].lower() in all_units:
            new_tokens.append(tokens[i] + tokens[i+1])  # Merge value + unit
            i += 2  # Skip next token since merged
        else:
            new_tokens.append(tokens[i])
            i += 1

    # Initialize found values
    cap_value = res_value = ind_value = volt_value = amp_value = power_value = tolerance_value = ""

    # Sort units by length (longest first) for accurate matching
    unit_lists = {
        "cap": sorted(cap_end, key=len, reverse=True),
        "res": sorted(res_end, key=len, reverse=True),
        "ind": sorted(ind_end, key=len, reverse=True),
        "volt": sorted(volt_end, key=len, reverse=True),
        "amp": sorted(amp_end, key=len, reverse=True),
        "power": sorted(power_end, key=len, reverse=True),
        "tol": sorted(tolerance_end, key=len, reverse=True)
    }

    # Process each token to identify component specifications
    for token in new_tokens:
        # Capacitance extraction
        for unit in unit_lists["cap"]:
            if token.lower().endswith(unit):
                base = token[:-len(unit)]
                if __is_number_str(base):
                    cap_value = token
                    break  # Stop checking other capacitance units
        
        # Resistance extraction
        for unit in unit_lists["res"]:
            if token.lower().endswith(unit):
                base = token[:-len(unit)]
                if __is_number_str(base):
                    res_value = token
                    break
        
        # Inductance extraction
        for unit in unit_lists["ind"]:
            if token.lower().endswith(unit):
                base = token[:-len(unit)]
                if __is_number_str(base):
                    ind_value = token
                    break
        
        # Voltage extraction
        for unit in unit_lists["volt"]:
            if token.lower().endswith(unit):
                base = token[:-len(unit)]
                if __is_number_str(base):
                    volt_value = token
                    break
        
        # Current extraction
        for unit in unit_lists["amp"]:
            if token.lower().endswith(unit):
                base = token[:-len(unit)]
                if __is_number_str(base):
                    amp_value = token
                    break
        
        # Power extraction
        for unit in unit_lists["power"]:
            if token.lower().endswith(unit):
                base = token[:-len(unit)]
                if __is_number_str(base):
                    power_value = token
                    break

        for unit in unit_lists["tol"]:
            if token.lower().endswith(unit):
                base = token[:-len(unit)]
                if __is_number_str(base):
                    tolerance_value = token.replace("±", "")
                    break
        

    # Build result dictionary with found values
    ret = {}
    if cap_value: ret["cap_value"] = cap_value
    if res_value: ret["res_value"] = res_value
    if ind_value: ret["ind_value"] = ind_value
    if volt_value: ret["volt_value"] = volt_value
    if power_value: ret["power_value"] = power_value
    if amp_value: ret["amp_value"] = amp_value
    if tolerance_value: ret["tolerance"] = tolerance_value
    return ret

print(test_str1)
print(parseComponent(test_str1))
print()
print(test_str2)
print(parseComponent(test_str2))
print()
print(test_str3)
print(parseComponent(test_str3))
print()
print(test_str4)
print(parseComponent(test_str4))
print()
print(test_str5)
print(parseComponent(test_str5))
print()
print(test_str6)
print(parseComponent(test_str6))
print(test_str7)
print(parseComponent(test_str7))
print(test_str8)
print(parseComponent(test_str8))
print(test_str9)
print(parseComponent(test_str9))
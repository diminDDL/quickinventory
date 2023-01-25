test_str1 = "16V 47uF X5R ±10% 1210  Multilayer Ceramic Capacitors MLCC - SMD/SMT ROHS"
test_str2 = "125mW Thick Film Resistors 150V ±100ppm/℃ ±5% -55℃~+155℃ 1.8kΩ 0805 Chip Resistor - Surface Mount ROHS"
test_str3 = "47uF 6.3V ±20% CASE-A-3216 Tantalum Capacitors ROHS"
test_str4 = "16V 2.2uF X5R ±10% 0805 Multilayer Ceramic Capacitors MLCC - SMD/SMT ROHS "
test_str5 = " 	1uH ±20% 3.3mΩ 28A SMD,10x11.5x4mm Power Inductors ROHS "
test_str6 = "3A 22uH ±20% 130mΩ SMD,7.1x6.6x3mm Power Inductors ROHS "

def parseComponent(str):
    # parses the string and returns the following
    # component value
    # component package
    # voltage/power rating
    cap_end = ["f", "mf", "uf", "μF", "nf", "pf"]
    cap_value = ""
    res_end = ["k", "m", "g", "r", "kω", "mω", "gω", "ω", "kohm", "mohm", "gohm", "ohm", "kohms", "mohms", "gohms", "ohms"]
    res_value = ""
    ind_end = ["mh", "uh", "μh", "nh", "ph"]
    ind_value = ""
    volt_end = ["v", "mv", "uv", "vv"]
    volt_value = ""
    amp_end = ["a", "ma", "ua"]
    amp_value = ""
    power_end = ["w", "mw", "uw", "vw"]
    power_value = ""
    split = str.strip().split(" ")
    for i in split:
        for j in cap_end:
            if j in i.lower() and i.lower().strip(j).replace(".", "").replace(",", "").isdigit():
                cap_value = i
        for j in res_end:
            if j in i.lower() and i.lower().strip(j).replace(".", "").replace(",", "").isdigit():
                res_value = i
        for j in ind_end:
            if j in i.lower() and i.lower().strip(j).replace(".", "").replace(",", "").isdigit():
                ind_value = i
        for j in volt_end:
            if j in i.lower() and i.lower().strip(j).replace(".", "").replace(",", "").isdigit():
                volt_value = i
        for j in power_end:
            if j in i.lower() and i.lower().strip(j).replace(".", "").replace(",", "").isdigit():
                power_value = i
        for j in amp_end:
            if j in i.lower() and i.lower().strip(j).replace(".", "").replace(",", "").isdigit():
                amp_value = i
    
    # construct a return dict, if something is empty, don't add it
    ret = {}
    if cap_value != "":
        ret["cap_value"] = cap_value
    if res_value != "":
        ret["res_value"] = res_value
    if ind_value != "":
        ret["ind_value"] = ind_value
    if volt_value != "":
        ret["volt_value"] = volt_value
    if power_value != "":
        ret["power_value"] = power_value
    if amp_value != "":
        ret["amp_value"] = amp_value
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
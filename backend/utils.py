import readline
from difflib import get_close_matches

class utils():
    def __init__(self):
        pass

    def parseComponent(self, str):
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
    
    def input_with_prefill(self, prompt, text):
        def hook():
            readline.insert_text(text)
            readline.redisplay()
        readline.set_pre_input_hook(hook)
        result = input(prompt)
        readline.set_pre_input_hook()
        return result
    
    def findPartTemplate(self, template, templates):
        try:
            partTemplate = get_close_matches(template, [i.name for i in templates], n=1, cutoff=0.5)[0]
            # now get the part object that has the same name as the template
            partTemplate = list(filter(lambda x: x.name == partTemplate, templates))[0]
        except IndexError:
            partTemplate = None
        return partTemplate
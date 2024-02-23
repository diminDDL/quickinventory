import readline
import cv2
import re
import html
import backend.lcsc
from pyzbar import pyzbar
from anytree import Node, RenderTree, search
from difflib import get_close_matches

class Tools():
    def __init__(self):
        self.lcsc = backend.lcsc.LCSC(utils=self)
        self.CLEANR = re.compile('<.*?>')
        self.CLEAN_NUMERIC = re.compile('[^0-9.,]')

    def cleanhtml(self, raw_html) -> str:
        cleantext = str(html.unescape(re.sub(self.CLEANR, '', raw_html)))
        return cleantext

    def cleanNumeric(self, raw_text) -> str:
        cleantext = re.sub(self.CLEAN_NUMERIC, '', raw_text)
        return cleantext

    def drawTree(self, tree_root: Node, typ: list) -> list:
        tree_ids = []
        i = 0
        size = len(list(RenderTree(tree_root)))
        padding = len(str(size))
        for pre, fill, node in RenderTree(tree_root):
            tree_ids.append([[i], [node.name]])
            padded = str(i).rjust(padding)
            name = ""
            for j in typ:
                if str(node.name) == str(j.pk):
                    name = j.name
                    break
                else:
                    name = node.name
            print(f"{padded}) {pre}{name}")
            i += 1
        return tree_ids

    def parseComponent(self, str) -> list:
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
    
    def input_with_prefill(self, prompt, text) -> str:
        def hook():
            readline.insert_text(text)
            readline.redisplay()
        readline.set_pre_input_hook(hook)
        result = input(prompt)
        readline.set_pre_input_hook()
        return result
    
    def findPartTemplate(self, template, templates):
        try:
            partTemplate = get_close_matches(template, [i.name for i in templates], n=1, cutoff=0.85)[0]
            # now get the part object that has the same name as the template
            partTemplate = list(filter(lambda x: x.name == partTemplate, templates))[0]
        except IndexError:
            partTemplate = None
        return partTemplate
    
    def read_barcodes(self, frame):
        # returns the frame and the name of the company and the part number
        # for example, ["LCSC", "C123456789"] or ["Digikey", "123-456-ABC"] and so on
        part = ["", None]
        barcodes = pyzbar.decode(frame)
        for barcode in barcodes:
            x, y , w, h = barcode.rect
            barcode_info = barcode.data.decode('utf-8')
            cv2.rectangle(frame, (x, y),(x+w, y+h), (0, 255, 0), 2)
    
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, barcode_info, (x + 6, y - 6), font, 2.0, (255, 255, 255), 1)        #3
            if barcode_info.startswith('{') and barcode_info.endswith('}'):
                # print(f"Recognized QR code: {barcode_info}")
                part = self.lcsc.decodeCode(barcode_info)
                print(f"Extracted part number: {part}")
        return frame, part
import os
import readline
import cv2
import re
import html
import backend.lcsc
from pyzbar import pyzbar
from inventree.api import InvenTreeAPI
from inventree.part import PartCategory
from inventree.stock import StockLocation
from anytree import Node, RenderTree, search
from difflib import get_close_matches

class Tools():
    def __init__(self):
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

    # kept for backwards compability with component templates
    def parseComponent(self, str) -> dict:
        # parses the string and returns the following
        # component value
        # voltage/power rating
        cap_end = ["f", "mf", "uf", "μF", "nf", "pf"]
        cap_value = ""
        res_end = ["k", "m", "g", "r", "kω", "mω", "gω", "ω", "kohm", "mohm", "gohm", "ohm", "kohms", "mohms", "gohms", "ohms"]
        res_value = ""
        ind_end = ["mh", "uh", "μh", "nh", "ph"]
        ind_value = ""
        volt_end = ["v", "kv", "mv", "uv", "vv"]
        volt_value = ""
        amp_end = ["a", "ma", "ua"]
        amp_value = ""
        power_end = ["w", "mw", "uw", "vw"]
        power_value = ""
        percent_end = ["%"]
        percent_value = ""
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
            for j in percent_end:
                if j in i.lower() and i.lower().strip(j).replace(".", "").replace(",", "").replace("±", "").isdigit():
                    percent_value = i.replace("±", "")
        
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
        if percent_value != "":
            ret["percent_value"] = percent_value
        return ret
    
    # kept for backwards compability with component templates
    def splitUnits(self, str: str):
        # Splits given string into value (with SI scalar) and a unit
        scalars = ["G", "M", "k", "m", "u", "μ", "n", "p"]
    
        # Iterate through all scalars to split the string accordingly
        for scalar in scalars:
            divided_str = str.split(scalar)

            if len(divided_str) == 2:  # For typical values e.g. 15uF, 27kohm
                value = divided_str[0] + scalar
                unit = divided_str[1]
                break
            elif len(divided_str) > 2:  # Unexpected format, handle error
                print("Invalid input format! The string contains more than one scalar.")
                return None, None
        else:  # This is for values like 15R or 5F, where no scalar is found
            if "ohm" in str.lower():
                value = str[:-3]
                unit = "ohm"
            if "r" in str.lower():
                value = str[:-1]
                unit = "ohm"
            if len(str) > 1:
                value = str[:-1]  # All characters except the last
                unit = str[-1:]  # Last character
            else:
                print("Invalid input format! The string is too short to have a value and unit.")
                return None, None

        # Clean up extra spaces from value and unit
        value = value.replace(" ", "")
        unit = unit.replace(" ", "")

        return value, unit
    
    def inputWithPrefill(self, prompt, text) -> str:
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
        barcode_info = None
        barcodes = pyzbar.decode(frame)
        for barcode in barcodes:
            x, y , w, h = barcode.rect
            barcode_info = barcode.data.decode('utf-8')
            cv2.rectangle(frame, (x, y),(x+w, y+h), (0, 255, 0), 2)
    
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, barcode_info, (x + 6, y - 6), font, 2.0, (255, 255, 255), 1)
        return frame, barcode_info
    
    def createCategoryTree(self, api: InvenTreeAPI) -> tuple[PartCategory, Node]:
        categories = PartCategory.list(api)
        # iterate over all categories and create a hierarchical tree
        print("Creating category tree...")
        category_tree_root = Node("root")
        for i in categories:
            parent = i.getParentCategory()
            if parent == None:
                Node(i.pk, parent=category_tree_root)
            else:
                # find the parent category in the tree
                res = search.findall(category_tree_root, filter_=lambda node: str(node.name) == str(parent.pk), maxcount=1)[0]
                Node(i.pk, parent=res)
        
        return categories, category_tree_root

    def createLocationTree(self, api: InvenTreeAPI) -> tuple[StockLocation, Node]:
        locations = StockLocation.list(api)
        print("Creating location tree...")
        location_tree_root = Node("root")
        for i in locations:
            parent = i.getParentLocation()
            if parent == None:
                Node(i.pk, parent=location_tree_root)
            else:
                # find the parent category in the tree
                res = search.findall(location_tree_root, filter_=lambda node: str(node.name) == str(parent.pk), maxcount=1)[0]
                Node(i.pk, parent=res)

        return locations, location_tree_root
        
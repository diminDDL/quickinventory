import readline
import cv2
import re
import html

from pylibdmtx import pylibdmtx
from enum import Enum, auto
from inventree.part import PartCategory, Part
from pyzbar import pyzbar
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
    
    def __is_number_str(self, s):
        """Check if a string represents a valid number (handles decimals and commas)."""
        s_clean = s.replace(',', '')  # Remove commas from numbers
        if s_clean == '':
            return False
        if s_clean.count('.') > 1:  # More than one decimal point is invalid
            return False
        # Check if string is digits after removing one decimal point
        return s_clean.replace('.', '', 1).isdigit()

    # kept for backwards compability with component templates
    def parseComponent(self, str):
        """
        Parses electronic component descriptions to extract key specifications.
        Handles spaces between values and units, and extracts tolerance percentages.
        
        Approach:
        1. Preprocess string to merge separated value-unit pairs
        2. Define unit categories and combine for quick lookup
        3. Process tokens to extract param information
        4. Return dictionary with found specifications
        """
        # Normalize micro characters to 'u' and remove fillers
        str = str.replace(chr(181), "u").replace(chr(956), "u").replace(";", "")

        # Unit definitions for different component types
        cap_end = ["f", "mf", "uf", "μf", "nf", "pf"]
        res_end = ["k", "m", "g", "r", "kω", "mω", "gω", "ω", "kohm", "mohm", "gohm", "ohm", "kohms", "mohms", "gohms", "ohms"]
        ind_end = ["mh", "uh", "μh", "nh", "ph"]
        volt_end = ["v", "mv", "uv", "vv", "kv"]
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
            if i < len(tokens) - 1 and self.__is_number_str(tokens[i]) and tokens[i+1].lower() in all_units:
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
                    if self.__is_number_str(base):
                        cap_value = token
                        break  # Stop checking other capacitance units
            
            # Resistance extraction
            for unit in unit_lists["res"]:
                if token.lower().endswith(unit):
                    base = token[:-len(unit)]
                    if self.__is_number_str(base):
                        res_value = token
                        break
            
            # Inductance extraction
            for unit in unit_lists["ind"]:
                if token.lower().endswith(unit):
                    base = token[:-len(unit)]
                    if self.__is_number_str(base):
                        ind_value = token
                        break
            
            # Voltage extraction
            for unit in unit_lists["volt"]:
                if token.lower().endswith(unit):
                    base = token[:-len(unit)]
                    if self.__is_number_str(base):
                        volt_value = token
                        break
            
            # Current extraction
            for unit in unit_lists["amp"]:
                if token.lower().endswith(unit):
                    base = token[:-len(unit)]
                    if self.__is_number_str(base):
                        amp_value = token
                        break
            
            # Power extraction
            for unit in unit_lists["power"]:
                if token.lower().endswith(unit):
                    base = token[:-len(unit)]
                    if self.__is_number_str(base):
                        power_value = token
                        break

            for unit in unit_lists["tol"]:
                if token.lower().endswith(unit):
                    base = token[:-len(unit)]
                    if self.__is_number_str(base):
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
    
    def splitUnits(self, str):
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
    
    def input_with_prefill(self, prompt, text) -> str:
        def hook():
            readline.insert_text(text)
            readline.redisplay()
        readline.set_pre_input_hook(hook)
        result = input(prompt)
        readline.set_pre_input_hook()
        return result
    
    def find_part_template(self, template: str, templates: list[PartCategory]) -> PartCategory | None:
        try:
            partTemplate = get_close_matches(template, [i.name for i in templates], n=1, cutoff=0.85)[0]
            # now get the part object that has the same name as the template
            partTemplate = list(filter(lambda x: x.name == partTemplate, templates))[0]
        except IndexError:
            partTemplate = None
        return partTemplate

    def find_part(self, partNumber: str, parts: list[Part], partName: str = None) -> int | None:
        for part in parts:
            # print(f"Checking part: {part.name} with keywords: {part.keywords}")
            # First we try to find the exact match of partNumber in the keywords of the parts
            if partNumber.lower() in (part.keywords or "").lower():
                return part.pk
        
        # If no exact match is found, we try to find a close match of the part name
        if partName:
            close_matches = get_close_matches(partName, [part.name for part in parts], n=1, cutoff=0.85)
            if close_matches:
                return next((part.pk for part in parts if part.name == close_matches[0]), None)
            
        # If no match is found, return None
        return None

    def read_barcodes(self, frame):
        font = cv2.FONT_HERSHEY_DUPLEX
        barcode_infos = []

        dm_barcodes = pylibdmtx.decode(frame, timeout=10)
        for dm_barcode in dm_barcodes:
            barcode_data = dm_barcode.data.decode('utf-8')
            barcode_infos.append(barcode_data)
            x, y, w, h = dm_barcode.rect
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, barcode_data, (x + 6, y - 6), font, 2.0, (255, 255, 255), 1)

        standard_barcodes = pyzbar.decode(frame)
        for barcode in standard_barcodes:
            if barcode.type != 'DATAMATRIX':
                barcode_data = barcode.data.decode('utf-8')
                barcode_infos.append(barcode_data)
                x, y, w, h = barcode.rect
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame, barcode_data, (x + 6, y - 6), font, 2.0, (255, 255, 255), 1)

        return frame, barcode_infos
    
class DuplicateChoice(Enum):
    ADD_STOCK = auto()
    SKIP = auto()
    CREATE_NEW = auto()

from __future__ import annotations
from typing import TYPE_CHECKING

import re
import json
from parsel import Selector
from backend.base import NORMALIZED_PARAM_NAMES, baseSupplier, PartData, Parameter

if TYPE_CHECKING:
    from backend.utilities import Tools

from requests_html import HTMLSession

class LCSC(baseSupplier):
    """Supplier implementation for LCSC Electronics (https://www.lcsc.com/)"""

    def __init__(self, utils: Tools, config):
        self.LCSC_NUM = re.compile(r'pc:(C\d*)')
        self.utils = utils
        self.headers = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 uacq'}
        self.session = HTMLSession()

    def parseCode(self, code: str) -> str:
        """
        Extract LCSC part number from scanned barcode
        Args:
            code: Raw barcode string from scanner
        Returns:
            Extracted part number or None if invalid
        """
        try:
            LCSCPartNumber = re.search(self.LCSC_NUM, code)
            LCSCPartNumber = str(LCSCPartNumber.group(1)).strip()
            
            if LCSCPartNumber == "":
                print("Invalid barcode!")
                return None

            return LCSCPartNumber
        except:
            return None
    
    def query(self, partNumber) -> PartData:
        # queries the LCSC API for the part number and returns the data
        query = "https://www.lcsc.com/search?q=" + partNumber
        response = self.session.get(query, headers=self.headers)
        try:
            if response.status_code != 200:
                return None
            
            # Reder the website to get full specification table
            response.html.render()
            sel = Selector(response._html.html)

            try:
                parameters = []
                specification_table_path = "(//div[contains(@class, 'v-data-table__wrapper')]//table)"
                table = sel.xpath(specification_table_path)
                
                if not table:
                    raise Exception()
                    #raise Exception(f"Product specifications table not found! xpath={specification_table_path}")

                # Scrape parameters from the specification table 
                rows = table[0].xpath(".//tbody/tr")
                for r in rows:
                    cells = r.xpath("./td")
                    if len(cells) >= 2:
                        key = r.xpath("string(./td[1])").get().strip()
                        val = r.xpath("string(./td[2])").get().strip()
                        if key.lower().replace(" ", "") in NORMALIZED_PARAM_NAMES.keys() and val != "-":
                            parameters.append(Parameter(
                                name = key, value_str = val
                            ))

                # gets the content of script tag containing full info
                data = json.loads(sel.xpath("/html/head/script[12]/text()").get())

                return PartData(
                    name = data["name"],
                    supplier_pn = partNumber,
                    manufacturer_pn= data["mpn"],
                    description = data["description"],
                    remote_image = data["image"],
                    link = response.url,
                    unit_price = float(data["offers"]["price"]),
                    parameters=parameters,
                    keywords= f"{partNumber}, {data["mpn"]}",
                    minimum_stock = None,
                    part_count = None,
                    note = None 
                )    

            except Exception as e:
                print(e)
                print("No data found")
                return None

        except Exception as e:
            print(e)
            print("Invalid part number!")
            return None
        
    def _mapParameters(self, supplier_params) -> list[Parameter]:
        pass
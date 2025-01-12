from __future__ import annotations
from typing import TYPE_CHECKING

import re
import json
import requests
from typing import Type
from parsel import Selector
if TYPE_CHECKING:
    from backend.utilities import Tools

class LCSC():
    def __init__(self, utils: Type[Tools]):
        self.LCSC_NUM = re.compile('pc:(C\d*)')
        self.utils = utils

    def decodeCode(self, text):
        # decodes the raw text from the barcode and returns the LCSC part number for example "C123456789"
        LCSCPartNumber = re.search(self.LCSC_NUM, text)
        LCSCPartNumber = str(LCSCPartNumber.group(1)).strip()
        store = "LCSC" if LCSCPartNumber != "" else ""
        return [store, LCSCPartNumber]
    
    def query(self, partNumber):
        headers = {
            'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 uacq'
        }
        # queries the LCSC API for the part number and returns the data
        query = "https://www.lcsc.com/search?q=" + partNumber
        response = requests.get(query, headers=headers)
        #print(response.text)
        fields = {}
        package = ""
        try:
            if response.status_code == 200:
                #print("Query successful!")
                sel = Selector(response.text)

                try:
                # gets the content of script tag containing full info
                    data = json.loads(sel.xpath("/html/head/script[4]/text()").get())

                    fields["name"] = data["name"]
                    fields["description"]  = data["sku"]
                    fields["template_description"] = data["category"].split("/")[1]
                    fields["remote_image"] = data["image"]
                    fields["link"] = response.url
                    fields["unit_price"] = data["offers"]["price"]
                    package = re.sub(' +', ' ', self.utils.cleanhtml(sel.xpath("/html/body/div/div/div/div[1]/main/div/div/div/div/div[1]/div[1]/div[2]/table/tbody/tr[4]/td[2]/div/span").get()).strip())

                    if fields["unit_price"] == "0.00":
                        print("Part is discontinued!")

                except Exception as e:
                    print(e)
                    print("No data found")


        except Exception as e:
            print(e)
            print("Invalid part number!")
        
        return [fields, package]
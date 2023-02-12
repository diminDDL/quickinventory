from __future__ import annotations
from typing import TYPE_CHECKING

import re
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
        # queries the LCSC API for the part number and returns the data
        query = "https://www.lcsc.com/search?q=" + partNumber
        response = requests.get(query)
        fields = {}
        package = ""
        try:
            if response.status_code == 200:
                # print("Query successful!")
                sel = Selector(response.text)
                fields["name"] = re.sub(' +', ' ', self.utils.cleanhtml(sel.xpath("/html/body/div/div/div/div/main/div/div/div[2]/div/div/div[1]/div[1]/div[2]/table/tbody/tr[2]/td[2]").get()).strip())
                try:
                    fields["description"] = re.sub(' +', ' ', self.utils.cleanhtml(sel.xpath("/html/body/div/div/div/div/main/div/div/div[2]/div/div/div[1]/div[1]/div[2]/table/tbody/tr[8]/td[2]").get()).strip())
                except:
                    fields["description"] = re.sub(' +', ' ', self.utils.cleanhtml(sel.xpath("/html/body/div/div/div/div[1]/main/div/div/div[2]/div/div/div[1]/div[1]/div[2]/table/tbody/tr[7]/td[2]").get()).strip())
                fields["template_description"] = re.sub(' +', ' ', self.utils.cleanhtml(sel.xpath("/html/body/div/div/div/div/main/div/div/div[1]/ul/li[7]/a").get()).strip())
                package = re.sub(' +', ' ', self.utils.cleanhtml(sel.xpath("/html/body/div/div/div/div[1]/main/div/div/div[2]/div/div/div[1]/div[1]/div[2]/table/tbody/tr[4]/td[2]").get()).strip())
                fields["link"] = response.url
                # check if part is discontinued beofore getting the price
                try:
                    fields["unit_price"] = re.sub(' +', ' ', self.utils.cleanNumeric(self.utils.cleanhtml(sel.xpath("/html/body/div/div/div/div[1]/main/div/div/div[2]/div/div/div[2]/div[1]/div[4]/table/tbody/tr[1]/td[2]/span").get())).strip())
                except:
                    print("Part is discontinued!")
                    fields["unit_price"] = "0"
        except Exception as e:
            # print(e)
            print("Invalid part number!")
        
        return [fields, package]
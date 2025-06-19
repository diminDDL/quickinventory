import base64
import hashlib
import hmac
import re
import sys

import click
import urllib

import requests
from backend.file import fileHandler
from backend.utilities import Tools
from backend.base import Parameter, PartData, baseSupplier

class TME(baseSupplier):
    def __init__(self,  utils: Tools, config):
        # self.TME_NUM = re.compile(r'^.*\bQTY:\S+.*\bPN:\S+.*\bMFR:\S+.*\bMPN:\S+.*$') # full QR code data (?)
        self.TME_NUM = re.compile(r'\bPN:(\S+)') # Part Number

        fs = fileHandler(config)
        data = fs.readCredentials()
        self.secret = data["tme"]["app-secret"]
        self.token = data["tme"]["client-token"]

        if self.token == "" or self.secret == "":
            click.secho("No client token or application secret key found in config.yml file!", bold=True, fg="red")
            sys.exit(0)

    def parseCode(self, code: str) -> str:
        # Attempt simple regex match
        try:
            TMEPartNumber = re.search(self.TME_NUM, code)
            TMEPartNumber = str(TMEPartNumber.group(1)).strip()
            
            if TMEPartNumber == "":
                print("Invalid barcode!")
                return None
            
            return TMEPartNumber
        # If regex fails, try API lookup for detailed product data
        except:
            details = self.__getProductDetails(code)
            if details != None:
                products = details["Data"]["ProductList"]
                if len(products) > 1: # This shouldn't happen, but the API doc allows it
                    code = self.__resolveMultipleProducts(products)
                return code
            return None

    def query(self, part_number) -> PartData:
        details = self.__getProductDetails(part_number)
        price = self.__getProductPrice(part_number)
        params = self.__getProductParams(part_number)

        # Abort if any API call failed
        if None in [details, price, params]:
            click.secho(f"No data found!")
            return None

        product_details = details["Data"]["ProductList"][0]
        product_prices = price["Data"]["ProductList"][0]["PriceList"]

        return PartData(
            name = product_details["OriginalSymbol"],
            supplier_pn = product_details["Symbol"],
            manufacturer_pn = product_details["OriginalSymbol"],
            description = product_details["Description"],
            remote_image = f"https:{product_details["Photo"]}",
            link = f"https:{product_details["ProductInformationPage"]}",
            unit_price = (min(product_prices, key=lambda item: item["Amount"], default=None) or {"PriceValue": 0})["PriceValue"],
            parameters = self._mapParameters(params["Data"]["ProductList"][0]["ParameterList"]),
            keywords= f"{product_details["Symbol"]}, {product_details["OriginalSymbol"]}",
            minimum_stock = None,
            part_count = None,
            note = None 
        )

    def __getProductDetails(self, part_number):
        # Call the TME GetProducts endpoint
        response = self.__makeRequest("GetProducts", part_number)

        if response.status_code == 200:
            return response.json()
        else:
            return None

    def __getProductParams(self, part_number):
        # Call the TME GetParameters endpoint
        response = self.__makeRequest("GetParameters", part_number)

        if response.status_code == 200:
            return response.json()
        else:
            return None
        
    def __getProductPrice(self, part_number):
        # Call the TME GetPrices endpoint
        response = self.__makeRequest("GetPrices", part_number)

        if response.status_code == 200:
            return response.json()
        else:
            return None
        
    def __makeRequest(self, url_dir, part_number):
        """
        Compose and send a signed POST request to the TME API.
        """
        url = f'https://api.tme.eu/Products/{url_dir}.json'
        data = {
            'Token': self.token,
            'Country': 'GB',
            'Language': 'EN', 
            'SymbolList[0]': f'{part_number}',
            'Currency': 'USD'
            #'GrossPrices': 'true' - Gross prices are available for anonymous request only
        }

        # Append the OAuth-style signature
        data['ApiSignature'] = self.__getSignature(url, data)

        response = requests.post(url, data=data)
        return response
    

    def __getSignature(self, url: str, req_data: str):
        """
        Generate HMAC-SHA1 signature for TME API authentication.
        Uses base64-encoded HMAC of the OAuth base string.
        """
        base_string = f'POST&{urllib.parse.quote(url, safe="")}&{urllib.parse.quote(urllib.parse.urlencode(sorted(req_data.items())), safe="")}'
        key = self.secret.encode('utf-8')
        message = base_string.encode('utf-8')
        signature = hmac.new(key, message, hashlib.sha1).digest()
        api_signature = base64.b64encode(signature).decode('utf-8')
        return api_signature

    def _mapParameters(self, supplier_params) -> list[Parameter]:
        # Create easily searchable map containing TME parameters
        param_map = { p["ParameterId"]: p for p in supplier_params }

        # Create map of parameters defined in VALID_PART_PARAMETERS and TME parameter IDs.
        # TME might not be consistent with usage of their IDs so there is a list of possible IDs.
        id_map = {
            "Resistance": [38],
            "Power Rating": [3409, 36, 589, 564],
            "Capacitance": [118],
            "Inductance": [566],
            "Voltage Rating": [243, 45, 120],
            "Forward Voltage": [226],
            "Drain to Source Voltage": [262],
            "Collector to Emitter Voltage": [261],
            "Current Rating": [234, 370, 268, 266, 1101],
            "Reverse Leackage Current": [245],
            "Saturation Current": [577],
            "ESR": [2260],
            "Tolerance": [39],
            "Package": [35, 2931],
            "Temperature Coefficient": [116]
        }
        params = []

        # Check if there are any DigiKey parameters with matching ids 
        # and add them to our standardized parameter list
        for param_name, possible_ids in id_map.items():
            for tme_id in possible_ids:
                # Try to fetch the dict for this DigiKey ID; if found, param_dict is truthy
                if (param_dict := param_map.get(tme_id)):
                    if param_dict["ParameterValue"] != "" and param_dict["ParameterValue"] != "-":
                        params.append(Parameter(
                            name=param_name,
                            value_str=param_dict["ParameterValue"]
                        ))
                        break   # stop checking other IDs for this param_name
        
        return params
        

    def __resolveMultipleProducts(self, products):
        """
        Prompt the user to disambiguate when multiple products match a code.
        """
        click.secho("Given part number resulted in multiple products found!", fg="bright_yellow")
        for idx, product in enumerate(products):
            click.echo(f"{idx}. {product["Symbol"]}")
        choice = click.prompt(
                f"Select correct part number (0-{len(products) - 1})",
                type=click.IntRange(0, len(products) - 1),
                show_choices=False
        )
        return products[choice]["Symbol"]    
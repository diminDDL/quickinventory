import re
import sys
import click
import requests

from backend.base import Parameter, PartData, baseSupplier
from backend.file import fileHandler
from backend.utilities import Tools


class DigiKey(baseSupplier):
    def __init__(self,  utils: Tools, config):
        self.barcode_2d_re = re.compile(r"^\[\)\>") # TODO better regex (ECC 200 - EIGP 114.2018)

        fs = fileHandler(config)
        data = fs.readCredentials()
        self.client_id = data["digikey"]["client-id"]
        self.client_secret = data["digikey"]["client-secret"]
        self.token = None

        if self.client_id == "" or self.client_secret == "":
            click.secho("No client ID or client secret key found in config.yml file!", bold=True, fg="red")
            sys.exit(0)

        self.__requestBearerToken()

    def parseCode(self, code: str) -> str:
        if re.match(self.barcode_2d_re, code):
            return code

        return None

    def query(self, code) -> PartData:
        if re.match(self.barcode_2d_re, code):
            response = self.__query2dcode(code)
        else:
            response = self.__getProductDetails(code)

        if response is None:
            click.secho(f"No data found!")
            return None
        
        parameters = self._mapParameters(response["Product"]["Parameters"])

        return PartData(
            supplier_pn = response["Product"]["ProductVariations"][0]["DigiKeyProductNumber"],
            manufacturer_pn = response["Product"]["ManufacturerProductNumber"],
            name = response["Product"]["ManufacturerProductNumber"],
            description = response["Product"]["Description"]["ProductDescription"],
            parameters = parameters,
            template_description = response["Product"]["Category"]["Name"],
            remote_image = response["Product"]["PhotoUrl"],
            link = response["Product"]["ProductUrl"],
            unit_price = response["Product"]["UnitPrice"],
            # Backwards compatibility with component templates 
            package = next((param["ValueText"] for param in response["Product"]["Parameters"] if param["ParameterId"] == 16), "")
        )

    def __query2dcode(self, code: str):
        # https://forum.digikey.com/t/digikey-product-labels-decoding-digikey-barcodes/41097
        code_segments = code.split("\x1d")
        manufacturer_part_number = next(seg.replace("1P", "") for seg in code_segments if seg.startswith("1P"))
        supplier_part_number = next(seg.replace("30P", "") for seg in code_segments if seg.startswith("30P"))

        return self.__getProductDetails(supplier_part_number)

    def __getProductDetails(self, part_number):
        while True:
            product_details_url = f'https://api.digikey.com/products/v4/search/{part_number}/productdetails'
            headers = {
                'Authorization': f'Bearer {self.token}',
                'X-DIGIKEY-Client-Id': self.client_id,
                'X-DIGIKEY-Locale-Site': 'US',
                'X-DIGIKEY-Locale-Language': 'en',
                'X-DIGIKEY-Locale-Currency': 'USD'
            }
            response = requests.get(product_details_url, headers=headers)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401 and 'detail' in response.json():
                if 'The Bearer token is invalid' in response.json()['detail']:
                    self.__requestBearerToken()
                    continue
                else:
                    click.secho(f"DigiKey API Web request error! {response.json()['detail']}", bold=True, color="red")
            else:
                break
        return None
    
    def __requestBearerToken(self):
        token_url = 'https://api.digikey.com/v1/oauth2/token'
        data = {'grant_type': 'client_credentials', 'client_id': self.client_id, 'client_secret': self.client_secret}
        response = requests.post(token_url, data=data)

        if response.status_code == 200:
            self.token = response.json()['access_token']
        else:
            print("Failed to get access token:", response.text)
            self.token = None

    def _mapParameters(self, supplier_params) -> list[Parameter]:
        # Create easily searchable map containing digikey parameters
        param_map = { p["ParameterId"]: p for p in supplier_params }

        # Create map of parameters defined in VALID_PART_PARAMETERS and DigiKey parameter IDs.
        # Digikey might not be consistent with usage of their IDs so there is a list of possible IDs.
        id_map = {
            "Resistance": [2085],
            "Power Rating": [2, 2109],
            "Capacitance": [2049],
            "Inductance": [2087],
            "Voltage Rating": [14, 2079],
            "Forward Voltage": [2261],
            "Drain to Source Voltage": [2068],
            "Collector to Emitter Voltage": [2103],
            "Current Rating": [2101, 2088, 914],
            "Reverse Leackage Current": [2269],
            "Saturation Current": [1219],
            "ESR": [724],
            "Tolerance": [3],
            "Package": [16],
            "Temperature Coefficient": [17]
        }
        params = []

        # Check if there are any DigiKey parameters with matching ids 
        # and add them to our standardized parameter list
        for param_name, possible_ids in id_map.items():
            for digi_id in possible_ids:
                # Try to fetch the dict for this DigiKey ID; if found, param_dict is truthy
                if (param_dict := param_map.get(digi_id)):
                    if param_dict["ValueText"] != "" and param_dict["ValueText"] != "-":
                        params.append(Parameter(
                            name=param_name,
                            value_str=param_dict["ValueText"]
                        ))
                        break   # stop checking other IDs for this param_name
        
        
        return params
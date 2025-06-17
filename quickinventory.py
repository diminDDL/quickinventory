import os
import sys
import traceback
import click
import cv2
import requests
from getpass import getpass
from inventree.api import InvenTreeAPI
from inventree.part import PartCategory, Part
from inventree.stock import StockLocation
from backend.base import PartData, baseSupplier
from backend.file import fileHandler
from backend.utilities import Tools
from backend.utilities import DuplicateChoice as PartDupChoice

import backend.suppliers.lcsc
import backend.suppliers.digikey
import backend.suppliers.tme

from backend.ui_utilities import *

debug = False  # Set to True for debugging output

utils = Tools()

suppliers = {
    "LCSC": backend.suppliers.lcsc.LCSC,          # QR code
    "DigiKey": backend.suppliers.digikey.DigiKey, # Data Matrix ECC 200
    "TME": backend.suppliers.tme.TME              # QR code
}

def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")

def get_new_token(server_url: str) -> str:
    username = input("Enter username: ")
    password = getpass("Enter password: ")
    response = requests.get(f"{server_url}/api/user/token/", auth=(username, password))
    if response.status_code == 200:
        return response.json()['token']
    else:
        print("Failed to retrieve token.")
        sys.exit(1)

def initialize_inventree_api(config: str) -> 'InvenTreeAPI':
    fs = fileHandler(config)
    data = fs.readCredentials()
    server_url = "http://" + data["server"]["ip"]
    token = data["server"]["token"]
    api = InvenTreeAPI(server_url, token=token)

    # Check if the API is working
    try:
        PartCategory.list(api)
    except Exception as e:
        print(f"Failed to connect to the InvenTree server: {e}")
        new_token = get_new_token(server_url)
        fs.updateToken(new_token)
        token = new_token
        api = InvenTreeAPI(server_url, token=token)
    return api

def get_part_data(cam, utils: Tools, supplier: baseSupplier) -> PartData:
    while True:
        if cam == None:
            code = click.prompt("Enter supplier part number")
        else:
            code = run_scanner(utils, supplier, cam)

        if code is None:
            raise(KeyboardInterrupt)
        
        print("Querying supplier...")
        part_data = supplier.query(code)

        if part_data is None:
            continue

        print(f"Parsed {part_data.link}")
        return part_data

def run_scanner(utils: backend.utilities.Tools, supplier: baseSupplier, adress: str) -> Part:
    code = None

    camera = cv2.VideoCapture(adress)
    if not camera.isOpened():
        click.secho("Could not open the camera!", bold=True, fg="red")
        sys.exit(0)

    print("Press ESC to exit the camera.")
    while True:
        ret, frame_raw = camera.read()

        if frame_raw is None:
            click.secho("Camera connection error!", bold=True, fg="red")
            sys.exit(0)

        frame, results = utils.read_barcodes(frame_raw.copy())
        cv2.imshow('Barcode/QR code reader', frame)
        
        if cv2.waitKey(1) & 0xFF == 27:
            break

        if results == []:
            continue

        for result in results:
            code = supplier.parseCode(result)
            if code != None:
                break

        if code != None:
                break

    cv2.destroyAllWindows()
    camera.release()
    return code

def main():
    print("Starting QuickInventory...")
    config = "config.toml"
    api = initialize_inventree_api(config)
    utils = Tools()
    
    category_tree_root = build_category_tree(api)
    location_tree_root = build_location_tree(api)

    use_parameters = click.confirm( "Would you like to use part parameters instead of templates?", default=True, show_default=True)
    clear_screen()

    supplier = select_supplier(suppliers, utils, config)
    clear_screen()

    cam = select_input_option(utils)
    clear_screen()

    try:
        while True:
            # TODO: change this to support different suppliers
            # TODO: clear screens more aggressively
            # TODO: add ability to type category and auto complete for it
            # TODO: find_part() could use Part.list(api, name_regex=) method

            # FIXME:
            # If a part exists but there are no stock items it will crash
            # Check if part exists before creating template maybe?
            # If saying no to an existing template something weird happens it just continues to part creation
            # LCSC seems to add manufacturers to the part name, which is not always desired
            # Before creating part we need a confirmation step where we could edit all the bits
            # If template is empty skip searching for it and assume the user doesn't want one

            # Get part data
            part_data = get_part_data(cam, utils, supplier)

            part_categories = PartCategory.list(api)
            part_locations = StockLocation.list(api)
            part_list = Part.list(api)

            category_pk = select_from_tree(utils, category_tree_root, part_categories, tree_type="category")
            clear_screen()
            location_pk = select_from_tree(utils, location_tree_root, part_locations, tree_type="location")
            clear_screen()

            variant_of = None
            
            if use_parameters:
                part_data = validate_parameters(api, part_data)
            else:
                variant_of = handle_template_creation(api, utils, part_data, category_pk, location_pk, part_categories, part_locations)
            
            clear_screen()

            #part_data.interactive_edit(utils)

            choice, existing_part_pk = handle_existing_part(utils, part_data.supplier_pn, part_list, part_data.name)
            match choice:
                case PartDupChoice.ADD_STOCK:
                    print("Adding stock to existing part...")
                    handle_adding_stock(api, existing_part_pk)
                    clear_screen()
                    continue
                case PartDupChoice.SKIP:
                    print("Skipping part...")
                    clear_screen()
                    continue
                case PartDupChoice.CREATE_NEW:
                    print("Creating new part...")
            
            part_count = handle_part_quantity()
            minimal_stock = handle_minimal_stock()
            unit_price = handle_parts_price(part_count, part_data.unit_price)
            if unit_price > 0.0:
                part_data.unit_price = unit_price

            create_part(api, category_pk, location_pk, part_data, variant_of, part_count, minimal_stock)
            # Add more functionality as needed
    except KeyboardInterrupt:
        print("Shutdown requested...exiting")
    except Exception:
        traceback.print_exc(file=sys.stdout)
    finally:
        sys.exit(0)

if __name__ == "__main__":
    main()
import os
import sys
import traceback
import click
import cv2
import requests
import signal
import threading
from getpass import getpass
from backend.utilities import Tools
from backend.file import fileHandler
from inventree.api import InvenTreeAPI
from inventree.part import PartCategory, Part
from inventree.stock import StockLocation
from backend.base import PartData, baseSupplier
from backend.utilities import DuplicateChoice as PartDupChoice

from backend.suppliers.lcsc import LCSC
from backend.suppliers.digikey import DigiKey
from backend.suppliers.tme import TME

from backend.ui_utilities import *
from backend.tree_utilities import *

debug = True  # Set to True for debugging output

suppliers = {
    "LCSC": LCSC,           # QR code
    "DigiKey": DigiKey,     # Data Matrix ECC 200
    "TME": TME              # QR code
}

STOP_EVENT = threading.Event()

def _sigint_handler(signum, frame):
    STOP_EVENT.set()
    # Raise so normal Python code breaks out immediately when possible
    raise KeyboardInterrupt

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
    except KeyboardInterrupt:
        raise
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

def run_scanner(utils: Tools, supplier: baseSupplier, adress: str) -> Part:
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

    use_parameters = click.confirm("Would you like to use part parameters?", default=True)
    use_template = click.confirm("Would you like to use part templates?", default=False)
    clear_screen()

    supplier = select_supplier(suppliers, utils, config)
    clear_screen()

    cam = select_input_option(utils)
    clear_screen()

    try:
        while True:
            # TODO: LCSC parameter mapping isn't implemented
            # TODO: add ability to type category and auto complete for it
            # TODO: find_part() could use Part.list(api, name_regex=) method
            # TODO: move to click library instead of While loops everywhere

            # FIXME:
            # handle_template_creation wih get_close_matches mixes up parts and there is no way to confirm besides ID
            # If a part exists but there are no stock items it will crash
            # Check if part exists before creating template maybe?
            # If saying no to an existing template something weird happens it just continues to part creation
            # LCSC seems to add manufacturers to the part name, which is not always desired
            # Integrate part templates with base PartData class and editing menu
            # If template is empty skip searching for it and assume the user doesn't want one

            clear_screen()
            part_data = get_part_data(cam, utils, supplier)

            part_categories = PartCategory.list(api)
            part_locations = StockLocation.list(api)
            part_list = Part.list(api)

            category_pk = select_from_tree(utils, category_tree_root, part_categories, tree_type="category")
            part_data.category_pk = category_pk
            clear_screen()
            location_pk = select_from_tree(utils, location_tree_root, part_locations, tree_type="location")
            part_data.location_pk = location_pk
            clear_screen()

            template_pk = None

            if use_parameters:
                handle_parameters(api)
            
            if use_template:
                template_data = handle_template_creation(api, utils, part_data, category_pk, location_pk)
                template_data.pretty_print(part_categories, part_locations)
                if click.confirm("Would you like to change any of the part template values?", default=False):
                    template_data.interactive_edit(utils, category_tree_root, part_categories, category_tree_root, part_locations)

                part_data.part_pk = template_data.create(api)
  
            clear_screen()

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
            
            part_data.part_count = handle_part_quantity()
            part_data.minimum_stock = handle_minimal_stock()
            unit_price = handle_parts_price(part_data.part_count, part_data.unit_price)
            if unit_price > 0.0:
                part_data.unit_price = unit_price

            part_data.pretty_print(part_categories, part_locations)
            if click.confirm( "Would you like to change any of the values?", default=False):
                part_data.interactive_edit(utils, category_tree_root, part_categories, category_tree_root, part_locations)

            part_data.create(api, template_pk)

            # Add more functionality as needed
    except (KeyboardInterrupt, click.Abort):
        print("Shutdown requested...exiting")
    except Exception:
        traceback.print_exc(file=sys.stdout)
    finally:
        return

if __name__ == "__main__":
    signal.signal(signal.SIGINT, _sigint_handler)
    main()
import os
import sys
import traceback
import cv2
import requests
from getpass import getpass
from anytree import Node, RenderTree, search
from inventree.api import InvenTreeAPI
from inventree.part import PartCategory, Part
from inventree.stock import StockLocation, StockItem
from backend.file import fileHandler
from backend.utilities import Tools
from backend.lcsc import LCSC
from backend.utilities import Tools


utils = Tools()

def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def get_new_token(server_url):
    username = input("Enter username: ")
    password = getpass("Enter password: ")
    response = requests.get(f"{server_url}/api/user/token/", auth=(username, password))
    if response.status_code == 200:
        return response.json()['token']
    else:
        print("Failed to retrieve token.")
        sys.exit(1)

def initialize_api() -> 'InvenTreeAPI':
    fs = fileHandler("config.toml")
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

def build_category_tree(api: InvenTreeAPI) -> Node:
    categories = PartCategory.list(api)
    category_tree_root = Node("root")
    for i in categories:
        parent = i.getParentCategory()
        parent_node = search.findall(category_tree_root, filter_=lambda node: str(node.name) == str(parent.pk), maxcount=1) if parent else [category_tree_root]
        Node(i.pk, parent=parent_node[0])
    return category_tree_root

def build_location_tree(api: InvenTreeAPI) -> Node:
    locations = StockLocation.list(api)
    location_tree_root = Node("root")
    for i in locations:
        parent = i.getParentLocation()
        parent_node = search.findall(location_tree_root, filter_=lambda node: str(node.name) == str(parent.pk), maxcount=1) if parent else [location_tree_root]
        Node(i.pk, parent=parent_node[0])
    return location_tree_root

def query_lcsc_part(lcsc: LCSC, cam: str) -> tuple:
    while True:  # Adding a loop to allow retrying
        if cam == "y":
            camera = cv2.VideoCapture(0)
            print("Starting camera... Press ESC to exit the camera.")
            lcscPart = ""
            while True:
                ret, frame = camera.read()
                if not ret:
                    print("Failed to capture image, exiting camera mode.")
                    break  # Exiting the camera loop on failure to capture image
                frame, part = lcsc.utils.read_barcodes(frame)
                cv2.imshow('Barcode/QR code reader', frame)
                if cv2.waitKey(1) & 0xFF == 27 or part != ["", None]:  # ESC pressed or part found
                    lcscPart = part[1] if part != ["", None] else ""
                    break
            cv2.destroyAllWindows()
            camera.release()
            if not lcscPart or not lcscPart.startswith("C"):  # Validate part format if necessary
                print("Invalid part captured, please enter the LCSC part number manually:")
                lcscPart = input("Please enter the LCSC part number: ")
        else:
            lcscPart = input("Please enter the LCSC part number: ")

        try:
            fields, package = lcsc.query(lcscPart)
            print(f"Part queried: {fields['link']}")
            return fields, package  # Successfully retrieved part data
        except Exception as e:
            print(f"Error querying LCSC part: {e}. Please try again.")
            # Optionally, prompt the user to try again or exit
            try_again = input("Do you want to try another part number? (y/n): ").lower()
            if try_again != 'y':
                raise  # Reraises the last exception, can be handled by the caller if needed

def select_from_tree(tree_root: Node, items: tuple, tree_type="category") -> int:
    
    tree_ids = utils.drawTree(tree_root, items)
    while True:
        try:
            print(f"Please select the {tree_type} for the new part:")
            selected_id = tree_ids[int(input())][1][0]  # User selects by index
            item_pk = [item.pk for item in items if str(item.pk) == str(selected_id)][0]
            item_name = [item.name for item in items if item.pk == item_pk][0]
            print(f"Selected {tree_type}: {item_name} (pk: {item_pk})")
            return item_pk
        except (ValueError, IndexError):
            # clear_screen()
            print(f"Invalid selection. Please enter a number corresponding to a {tree_type}.")

def create_part(api: InvenTreeAPI, category_pk: int, location_pk: int, fields: tuple) -> None:
    # Simplified version, assuming 'fields' contains all necessary info
    args = {
        'name': fields["name"],
        'description': fields["description"],
        'link': fields["link"],
        'category': category_pk,
        'default_location': location_pk,
        'component': True,
        'is_template': False
    }
    contains_remote_image = fields["remote_image"] != ""
    if contains_remote_image:
        args['remote_image'] = fields["remote_image"]

    # Additional logic for setting template, minimum stock, etc., as needed
    part = Part.create(api, args)
    print(f"Part created: {part.name} (pk: {part.pk})")

def handle_template_creation(api: InvenTreeAPI, category_pk: int, location_pk: int, fields: tuple, package: str, part_categories = None, part_locations = None) -> int:
    # First we generate a name for the template
    info = utils.parseComponent(fields["description"])

    # construct template using: <value> <package> <voltage rating (for capacitors)>/<power rating (for resistors)>/<curent>
    # in one line we check if this is a resistor or a capacitor, we check it depending on if res_value or cap_value keys are present in the info
    if "res_value" in info and "ind_value" not in info:
        template = info["res_value"] + " " + package + " " + (info["power_value"] if "power_value" in info else "")
    elif "cap_value" in info:
        template = info["cap_value"] + " " + package + " " + (info["volt_value"] if "volt_value" in info else "")
    elif "ind_value" in info:
        template = info["ind_value"] + " " + package + " " + (info["amp_value"] if "amp_value" in info else "")
    else:
        template = ""
    
    template = template.strip()

    # Present the user with the template we created and ask for confirmation/editing
    print("Part name: " + fields["name"])
    print("Part link: " + fields["link"])
    print("Confirm/enter the template: ")
    template = utils.input_with_prefill(text=template, prompt="")
    
    
    # Get a list of existing templates
    templates = Part.list(api, is_template=True)
    existing_template = utils.findPartTemplate(template, templates)

    # clear_screen()

    if existing_template:
        print(f"Existing template found: {existing_template.name}. The name you entered: {template}.\nUse this template? (y/n): ")
        use_existing = input().lower() == 'y'
    else:
        print("No existing template found. Create a new one? (y/n): ")
        use_existing = not (input().lower() == 'y')

    if use_existing:
        template_pk = existing_template.pk
    else:
        # Gather additional information for template creation here
        template_args = {
            'name': template,
            'description': fields["template_description"],
            'category': category_pk,
            'default_location': location_pk,
            'component': True,
            'is_template': True
        }
        print("Would you like to provide additional information? (y/n)")
        additional_info = input().lower() == 'y'
        if additional_info:
            print("Please enter the image link (enter to skip):")
            inp = input()
            if inp != "":
                template_args['remote_image'] = inp
            print("Please enter the minimum stock value (enter to skip):")
            inp = input()
            if inp != "":                    
                template_args['minimum_stock'] = int(inp)
            print("Please enter the note (enter to skip):")
            inp = input()
            if inp != "":
                template_args['note'] = inp
            print("Please enter the link (enter to skip):")
            inp = input()
            if inp != "":
                template_args['link'] = inp
            
        print("Template information:") 
        for key, value in template_args.items():
            if key == "category" and part_categories:
                value = [elem for elem in part_categories if elem.pk == value][0].name
            elif key == "default_location" and part_locations:
                value = [elem for elem in part_locations if elem.pk == value][0].name
            print(f"{key}: {value}")
        print("Confirm template information? (y/n)")
        # TODO, handle "n" properly
        # can be done by making a function purely for editing a field in the template_args dict
        # and asking the user if they want to edit a field
        if input() == "y":
            template = Part.create(api, template_args)
            template_pk = template.pk
    return template_pk


def main():
    print("Starting QuickInventory...")
    api = initialize_api()
    utils = Tools()
    lcsc = LCSC(utils=utils)
    
    category_tree_root = build_category_tree(api)
    location_tree_root = build_location_tree(api)
    
    cam = input("Would you like to use a camera? (y/n): ").lower()
    
    try:
        while True:
            # Get the LCSC part number
            fields, package = query_lcsc_part(lcsc, cam)


            part_categories = PartCategory.list(api)
            part_locations = StockLocation.list(api)
            category_pk = select_from_tree(category_tree_root, part_categories, tree_type="category")
            location_pk = select_from_tree(location_tree_root, part_locations, tree_type="location")
            template = handle_template_creation(api, category_pk, location_pk, fields, package, part_categories, part_locations)
            
            create_part(api, category_pk, location_pk, fields)
            # Add more functionality as needed
    except KeyboardInterrupt:
        print("Shutdown requested...exiting")
    except Exception:
        traceback.print_exc(file=sys.stdout)
    finally:
        sys.exit(0)

if __name__ == "__main__":
    main()

# TODO
# when after creating the part after selecting location and creating part it doesn't proceed
# it just starts over
    
# test part number: C456924
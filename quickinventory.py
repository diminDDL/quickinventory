import os
import click
import cv2
import sys, traceback
from inventree.api import InvenTreeAPI
from inventree.part import Part

import backend.digikey
import backend.lcsc
import backend.utilities
from backend.base import CLR
from backend.file import fileHandler
from backend.base import baseSupplier
from backend.ui_utilities import *

suppliers = {
    "LCSC": backend.lcsc.LCSC,         # QR codes
    "DigiKey": backend.digikey.DigiKey # Data Matrix ECC 200
}

def connectToInventree(config: str):
    """
    Read credentials from a config file and establish a connection
    to the InvenTree server.
    """
    fs = fileHandler(config)
    data = fs.readCredentials()
    server_url = "http://" + data["server"]["ip"]
    token = data["server"]["token"]

    print("Connecting to InvenTree...")
    return InvenTreeAPI(server_url, token=token)

def run_scanner(utils: backend.utilities.Tools, supplier: baseSupplier, adress: str) -> Part:
    code = None

    camera = cv2.VideoCapture(adress)
    if not camera.isOpened():
        print("Error: Could not open camera.")

    print("Press ESC to exit the camera.")
    while True:
        ret, frame_raw = camera.read()
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
    try:
        utils = backend.utilities.Tools()
        os.system(CLR)

        config = "config.toml"
        api = connectToInventree(config)

        categories, category_tree_root = utils.createCategoryTree(api)
        locations, location_tree_root = utils.createLocationTree(api)

        # Ask for supplier
        supplier_names = list(suppliers.keys())

        click.secho("Please select the supplier:", bold=True)
        for i, name in enumerate(supplier_names, 1):
            click.echo(f"{i}. {name}")

        choice = click.prompt(
            f"Enter your choice (1-{len(supplier_names)})",
            type=click.IntRange(1, len(supplier_names)),
            show_choices=False
        )

        supplier = suppliers[supplier_names[choice - 1]](utils, config)
        os.system(CLR)

        # Here the templates were used instead of the part parameters, which were introduced later. 
        # For backward compatibility, they have been left here.
        # You can choose which method you prefer.
        use_parameters = click.confirm(
            "Use part parameters instead of templates?",
            default=True,
            show_default=True,
        )

        # Ask if user want to use camera
        cam_adr = chooseInputOption(utils)
        os.system(CLR)

        # Main program loop
        while True:

            if cam_adr == None:
                code = click.prompt("Enter supplier part number")
            else:
                code = run_scanner(utils, supplier, cam_adr)

            if code is None:
                raise(KeyboardInterrupt)
            
            print("Querying supplier...")
            part_data = supplier.query(code)

            if part_data is None:
                continue

            print(f"Parsed {part_data.link}")

            # Check if scanned part is already in the system
            similar_parts = Part.list(api, name_regex=part_data.name)
            if similar_parts:
                existing_part = None
                for part in similar_parts:
                    if part.full_name == part_data.name:
                        print(f"Part with the same name ({part_data.name}) already exists!")
                        existing_part = part
                        break
                    elif (part_data.supplier_pn in part.keywords) or part_data.manufacturer_pn == part.ipn:
                        print(f"Part with the same part number ({part_data.supplier_pn}) already exists!")
                        existing_part = part
                        break
                
                if existing_part:
                    if click.confirm("Do you want to add new stock?", default=True):
                        location_pk = selectFromTree(
                            utils,
                            location_tree_root, 
                            locations, 
                            "Please select the location for the new part:"
                        )
                        addStock(api, existing_part, part_data, location_pk)
                    os.system(CLR)
                    continue


            # Category selection
            category_pk = selectFromTree(
                utils,
                category_tree_root, 
                categories, 
                "Please select the category for the new part:"
            )
            category_name = next((c.name for c in categories if c.pk == category_pk), None)
            os.system(CLR)

            # Location selection
            location_pk = selectFromTree(
                utils,
                location_tree_root, 
                locations, 
                "Please select the location for the new part:"
            )
            location_name = next((l.name for l in locations if l.pk == location_pk), None)
            os.system(CLR)

            print("Selected category: " + category_name + " (pk: " + str(category_pk) + ")")
            print("Selected location: " + location_name + " (pk: " + str(location_pk) + ")")

            # Backwards compatibility with part templates
            if not use_parameters:
                part_template = genTemplate(utils, part_data, api, categories, category_pk, locations, location_pk)

            # Show part parameters and allow editing
            if use_parameters:
                part_data = validateParameters(api, part_data)
                os.system(CLR)

            print("Creating new part...")
            print("Link to part: " + part_data.link)
            args = {
                'name': part_data.name,
                'description': part_data.description,
                'link': part_data.link,
                'remote_image': part_data.remote_image,
                'category': category_pk,
                'default_location': location_pk,
                'keywords' : f"{part_data.supplier_pn}, {part_data.manufacturer_pn}",
                'component': True,
                'is_template': False
            }

            if click.confirm("Would you like to set the MPN as Internal Part Number?", default=True):
                args["IPN"] = part_data.manufacturer_pn

            if(not use_parameters):
                if not part_template == None:
                    args['variant_of'] = part_template.pk

            if click.confirm("Would you like to provide additional information?", default=False):
                print("Please enter the image link (enter to skip):")
                inp = input()
                if inp != "":
                    args['remote_image'] = inp
                print("Please enter the minimum stock value (enter to skip):")
                inp = input()
                if inp != "":                    
                    args['minimum_stock'] = int(inp)
                print("Please enter the note (enter to skip):")
                inp = input()
                if inp != "":
                    args['note'] = inp
                print("Please enter alternative link (enter to skip):")
                inp = input()
                if inp != "":
                    args['link'] = inp
            os.system(CLR)

            parts = Part.list(api)
            part = None
            print("Part information:")
            for key, value in args.items():
                if key == "category":
                    value = [elem for elem in categories if elem.pk == value][0].name
                elif key == "default_location":
                    value = [elem for elem in locations if elem.pk == value][0].name
                elif key == "variant_of":
                    value = [elem for elem in parts if elem.pk == value][0].name
                print(f"{key}: {value}")

            # Create the part 
            if click.confirm("Confirm part information?", default=True):
                part = Part.create(api, args)
                print("Part created!")

                if(use_parameters): 
                    addParameters(api, part, part_data)

                print("Now let's add the part to the stock...")
                addStock(api, part, part_data, location_pk)
            
            os.system(CLR)

    except KeyboardInterrupt:
        print ("Shutdown requested...exiting")
    except Exception:
        traceback.print_exc(file=sys.stdout)
    sys.exit(0)

if __name__ == "__main__":
    main()
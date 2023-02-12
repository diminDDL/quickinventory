# run this script and you can use the following workflow:
# 1. authenticate with your inventree token
# 2. scan an lcsc qr code
# 3. the script will automatically check if the part category exists in inventree
# 4. if the part category does not exist, it will be created
# 5. the script will use data from LCSC directly to create a part in inventree
# 6. the script will automatically add the part to the correct category
# 7. you will be asked for confirmation to upload the part
# 8. repeat

import os
import sys, traceback
import requests
import re
import backend.utilities
import html
import backend.lcsc
from difflib import get_close_matches
from anytree import Node, RenderTree, search
from inventree.api import InvenTreeAPI
from inventree.part import PartCategory
from inventree.part import Part
from inventree.stock import StockLocation, StockItem
from backend.file import fileHandler
from parsel import Selector

def main():
    # figure out what os we are running on
    clr = "cls" if os.name == "nt" else "clear"

    print("Would you like to use a camera? (y/n)")
    cam = input().lower()
    if cam == "y":
        print("Starting camera...")
        import cv2
    try:
        os.system(clr)
        
        fs = fileHandler("config.toml")
        data = fs.readCredentials()
        server_url = "http://" + data["server"]["ip"]
        token = data["server"]["token"]
        utils = backend.utilities.Tools()
        lcsc = backend.lcsc.LCSC(utils=utils)

        print("Connecting to InvenTree...")
        api = InvenTreeAPI(server_url, token=token)

        categories = PartCategory.list(api)
        # iterate over all categories and create a hierarchical tree
        print("Creating category tree...")
        category_tree_root = Node("root")
        for i in categories:
            if i.getParentCategory() == None:
                Node(i.name, parent=category_tree_root)
            else:
                # find the parent category in the tree
                res = search.findall(category_tree_root, filter_=lambda node: node.name in str(i.getParentCategory().name), maxcount=1)[0]
                Node(i.name, parent=res)

        locations = StockLocation.list(api)
        print("Creating location tree...")
        location_tree_root = Node("root")
        for i in locations:
            if i.getParentLocation() == None:
                Node(i.name, parent=location_tree_root)
            else:
                # find the parent category in the tree
                res = search.findall(location_tree_root, filter_=lambda node: node.name in str(i.getParentLocation().name), maxcount=1)[0]
                Node(i.name, parent=res)


        while True:
            os.system(clr)
            while True:
                lcscPart = ""
                part = ""
                if cam == "y":
                    camera = cv2.VideoCapture(0)
                    ret, frame = camera.read()
                    print("Press ESC to exit the camera.")
                    while ret:
                        ret, frame = camera.read()
                        frame, part = utils.read_barcodes(frame)
                        cv2.imshow('Barcode/QR code reader', frame)
                        if cv2.waitKey(1) & 0xFF == 27 or part != ["", None]:
                            part = part[1]
                            cv2.destroyAllWindows()
                            if not part.startswith("C"):
                                part = input("Please enter the LCSC part number: ")
                            break
                    cv2.destroyAllWindows()
                    camera.release()
                    lcscPart = part
                else:
                    lcscPart = input("Please enter the LCSC part number: ")
                
                print("Querying LCSC...")
                fields, package = lcsc.query(lcscPart)
                print("Parased:" + fields["link"])
                break

           # os.system(clr)
            while True:
                try:
                    category_ids = utils.drawTree(category_tree_root)
                    print("Please select the category for the new part:")
                    category_id = int(input())
                    category_name = category_ids[category_id][1][0]
                    break
                except (ValueError, IndexError):
                    os.system(clr)
                    print("Please enter a valid number!")

            os.system(clr)

            while True:
                try:
                    location_tree_ids = utils.drawTree(location_tree_root)
                    print("Please select the location for the new part:")
                    location_id = int(input())
                    location_name = location_tree_ids[location_id][1][0]
                    break
                except(ValueError, IndexError):
                    os.system(clr)
                    print("Please enter a valid number!")

            os.system(clr)

            print("Selected category: " + category_name)
            print("Selected location: " + location_name)


            # print the fields
            # print("Part name: " + fields["name"])
            # print("Part description: " + fields["description"])
            # print("Part link: " + fields["link"])
            # print("Part package: " + package)

            # construct template using: <value> <package> <voltage rating (for capacitors)>/<power rating (for resistors)>/<curent>
            # in one line we check if this is a resistor or a capacitor, we check it depending on if res_value or cap_value keys are present in the infoDict

            infoDict = utils.parseComponent(fields["description"])
            #print("Part info: " + str(infoDict))

            if "res_value" in infoDict and "ind_value" not in infoDict:
                template = infoDict["res_value"] + " " + package + " " + (infoDict["power_value"] if "power_value" in infoDict else "")
            elif "cap_value" in infoDict:
                template = infoDict["cap_value"] + " " + package + " " + (infoDict["volt_value"] if "volt_value" in infoDict else "")
            elif "ind_value" in infoDict:
                template = infoDict["ind_value"] + " " + package + " " + (infoDict["amp_value"] if "amp_value" in infoDict else "")
            else:
                template = ""

            template = template.strip()

            print("Part name: " + fields["name"])
            print("Part link: " + fields["link"])
            print("Confirm/enter the template: ")
            template = utils.input_with_prefill(text=template, prompt="")

            parts = Part.list(api)
            # filter all the parts that have .is_template = True
            templates = list(filter(lambda x: x.is_template, parts))
            # find templates with close names to the template we want to create
            partTemplate = utils.findPartTemplate(template, templates)

            os.system(clr)

            newTemplate = False

            if not partTemplate:
                print("No existing template found, would you like to create one? (y/n)")
                if input() == "y":
                    newTemplate = True
            else:
                print(f"Found existing template called:\n{partTemplate.name}\nThe current template is:\n{template}.\nUse the existing tempalte to create the new part?\ny - use existing to create the part / n - create new template")
                if input() == "y":
                    newTemplate = False
                else:
                    newTemplate = True

            templateObj = None
            if newTemplate:
                print("Creating new template...")
                category = list(filter(lambda x: x.name == category_name, categories))[0]
                location = list(filter(lambda x: x.name == location_name, locations))[0]
                args = {
                    'name': template,
                    'description': fields["template_description"],
                    'category': category.pk,
                    'default_location': location.pk,
                    'component': True,
                    'is_template': True
                }
                print("Would you like to provide additional information? (y/n)")
                if input() == "y":
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
                    print("Please enter the link (enter to skip):")
                    inp = input()
                    if inp != "":
                        args['link'] = inp
                os.system(clr)
                # print the dict in a nice format
                print("Template information:")  
                for key, value in args.items():
                    if key == "category":
                        value = [elem for elem in categories if elem.pk == value][0].name
                    elif key == "default_location":
                        value = [elem for elem in locations if elem.pk == value][0].name
                    print(f"{key}: {value}")
                print("Confirm template information? (y/n)")
                if input() == "y":
                    templateObj = Part.create(api, args)
                    print("Template created!")

            os.system(clr)
            print("Creating new part...")
            print("Link to part: " + fields["link"])
            category = list(filter(lambda x: x.name == category_name, categories))[0]
            location = list(filter(lambda x: x.name == location_name, locations))[0]
            variant_of = partTemplate if not newTemplate else templateObj
            args = {
                'name': fields["name"],
                'description': fields["description"],
                'link': fields["link"],
                'category': category.pk,
                'default_location': location.pk,
                'keywords' : lcscPart,
                'component': True,
                'is_template': False
            }
            if not variant_of == None:
                args['variant_of'] = variant_of.pk

            print("Would you like to provide additional information? (y/n)")
            if input() == "y":
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
            os.system(clr)

            parts = Part.list(api)
            print("Part information:")
            for key, value in args.items():
                if key == "category":
                    value = [elem for elem in categories if elem.pk == value][0].name
                elif key == "default_location":
                    value = [elem for elem in locations if elem.pk == value][0].name
                elif key == "variant_of":
                    value = [elem for elem in parts if elem.pk == value][0].name
                print(f"{key}: {value}")
            print("Confirm part information? (y/n)")
            if input() == "y":
                part = Part.create(api, args)
                print("Part created!")

            os.system(clr)


            print("Now let's add the part to the stock...")
            print("Please enter the quantity:")
            quantity = int(input())
            print("Please enter the price for whole order (pre populated by parsed value):")
            price = float(utils.input_with_prefill(text=str(round(float(fields["unit_price"])*quantity, 6)), prompt=""))

            stock = StockItem.create(api, {
                'part': part.pk,
                'location': location.pk,
                'quantity': quantity,
                'purchase_price': round(float(price/quantity), 6)
            })

            print("Part added to stock!")
    except KeyboardInterrupt:
        print ("Shutdown requested...exiting")
    except Exception:
        traceback.print_exc(file=sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()

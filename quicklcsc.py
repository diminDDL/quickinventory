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
from anytree import Node, RenderTree, search
from inventree.api import InvenTreeAPI
from inventree.part import PartCategory
from inventree.part import Part
from inventree.stock import StockLocation
from backend.file import fileHandler
import backend.utils
from parsel import Selector


CLEANR = re.compile('<.*?>') 
def cleanhtml(raw_html):
  cleantext = re.sub(CLEANR, '', raw_html)
  return cleantext

def main():
    try:
        # figure out what os we are running on
        if os.name == "nt":
            clr = "cls"
        else:
            clr = "clear"

        os.system(clr)

        def drawTree(tree_root):
            tree_ids = []
            i = 0
            for pre, fill, node in RenderTree(tree_root):
                tree_ids.append([[i], [node.name]])
                print(f"{i}) {pre}{node.name}")
                i += 1
            return tree_ids

        fs = fileHandler("config.toml")
        data = fs.readCredentials()
        server_url = "http://" + data["server"]["ip"]
        token = data["server"]["token"]

        utils = backend.utils.utils()

        print("Connecting to InvenTree...")
        api = InvenTreeAPI(server_url, token=token)

        parts = Part.list(api)
        categories = PartCategory.list(api)
        locations = StockLocation.list(api)
        #print(len(parts))
        #print(len(categories))
        # print(categories[2].name)
        # print(categories[2].getParentCategory())
        # print(categories[0].getChildCategories())

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

        while True:
            try:
                category_ids = drawTree(category_tree_root)
                print("Please select the category for the new part:")
                category_id = int(input())
                category_name = category_ids[category_id][1][0]
                break
            except (ValueError, IndexError):
                os.system(clr)
                print("Please enter a valid number!")

        os.system(clr)

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
            try:
                location_tree_ids = drawTree(location_tree_root)
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
        
        while True:
            lcscPart = input("Please enter the LCSC part number: ")
            query = "https://www.lcsc.com/search?q=" + lcscPart
            print("Querying LCSC...")
            response = requests.get(query)
            fields = {}
            package = ""
            # fields["category"] = ""
            # fields["name"] = ""           p
            # fields["description"] = ""    p
            # fields["link"] = ""           p
            # fields["location"] = ""
            # fields["supplier"] = ""       
            # fields["variant"] = ""
            try:
                if response.status_code == 200:
                    print("Query successful!")
                    print("Parsing data...")
                    sel = Selector(response.text)
                    fields["name"] = cleanhtml(sel.xpath("/html/body/div/div/div/div/main/div/div/div[2]/div/div/div[1]/div[1]/div[2]/table/tbody/tr[2]/td[2]").get()).strip()
                    fields["description"] = cleanhtml(sel.xpath("/html/body/div/div/div/div/main/div/div/div[2]/div/div/div[1]/div[1]/div[2]/table/tbody/tr[8]/td[2]").get()).strip()
                    package = cleanhtml(sel.xpath("/html/body/div/div/div/div[1]/main/div/div/div[2]/div/div/div[1]/div[1]/div[2]/table/tbody/tr[4]/td[2]").get()).strip()
                    fields["link"] = response.url

                break
            except TypeError:
                print("Invalid part number!")
        
        # print the fields
        print("Part name: " + fields["name"])
        print("Part description: " + fields["description"])
        print("Part link: " + fields["link"])
        print("Part package: " + package)
        infoDict = utils.parseComponent(fields["description"])
        print("Part info: " + str(infoDict))

        # construct template using: <value> <package> <voltage rating (for capacitors)>/<power rating (for resistors)>/<curent>
        # in one line we check if this is a resistor or a capacitor, we check it depending on if res_value or cap_value keys are present in the infoDict

        if "res_value" in infoDict and "ind_value" not in infoDict:
            template = infoDict["res_value"] + " " + package + " " + infoDict["power_value"]
        elif "cap_value" in infoDict:
            template = infoDict["cap_value"] + " " + package + " " + infoDict["volt_value"]
        elif "ind_value" in infoDict:
            template = infoDict["ind_value"] + " " + package + " " + infoDict["amp_value"]
        else:
            template = ""
        
        print("Confirm/enter the template: ")
        template = utils.input_with_prefill(text=template, prompt="")

        print(f"template: {template}")

        #items = StockItem.list(api, location=1, part=1)
        # for i in parts:
        #     print(i.name)
        #     print(i.category)
        #     print(i.description)
        #print(items)
    except KeyboardInterrupt:
        print ("Shutdown requested...exiting")
    except Exception:
        traceback.print_exc(file=sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()

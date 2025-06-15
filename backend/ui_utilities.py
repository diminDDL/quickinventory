import os
import click
from backend.utilities import Tools
from inventree.api import InvenTreeAPI
from inventree.part import Part
from backend.base import VALID_PART_PARAMETERS, CLR, PartData
from inventree.stock import StockItem
from inventree.part import Parameter, ParameterTemplate

# Bunch of stuff moved from the main program loop

def chooseInputOption(utils: Tools) -> str: 
    use_cam = click.confirm("Do you want to use a camera?", default=True)

    if not use_cam: return None

    # Ask for camera type
    cam_type = click.prompt(
        "Select camera type",
        type=click.Choice(["system", "ip"], case_sensitive=False),
        default="system"
    )

    if cam_type == "system":
        # Ask which system camera index to use
        adress = click.prompt("Enter system camera index (e.g. 0 for /dev/video0)", type=int, default=0)
    else:
        # Ask for the URL
        print("Enter camera URL/IP: ")
        adress = utils.inputWithPrefill(text="http://192.168.100.157:8080/video", prompt="")

    return adress

def validateParameters(api: InvenTreeAPI, part_data: PartData):
    existing_templates = {template["name"] for template in ParameterTemplate.list(api)}

    if any(template not in existing_templates for template in VALID_PART_PARAMETERS):
        print("Adding missing parameter templates...")

    # Create missing templates
    for key in VALID_PART_PARAMETERS.keys():
        if key not in existing_templates:
            tmp = {"name": key, "units": "" if VALID_PART_PARAMETERS[key] is None else VALID_PART_PARAMETERS[key]}
            ParameterTemplate.create(api, tmp)


    print("The following parameters were found:")
    click.secho(f"{'Parameter':<25} {'Value':>20} {'Unit':>11}", bold=True)
    for param in part_data.parameters:
        unit = param.value[1] if param.value[1] else "-"
        print(f"{param.name:<{25}} {param.value[0]:>{20}} {unit:>{10}}")

    if click.confirm("\nWould you like to edit the parameters?", default=False):
        part_data.edit_parameters()
    
    return part_data

def genTemplate(utils: Tools, part_data: PartData, api: InvenTreeAPI, categories, category_pk, locations, location_pk):
    infoDict = utils.parseComponent(part_data.description)
    #print("Part info: " + str(infoDict))

    if "res_value" in infoDict and "ind_value" not in infoDict:
        template = infoDict["res_value"] + " " + part_data.package + " " + (infoDict["power_value"] if "power_value" in infoDict else "")
    elif "cap_value" in infoDict:
        template = infoDict["cap_value"] + " " + part_data.package + " " + (infoDict["volt_value"] if "volt_value" in infoDict else "")
    elif "ind_value" in infoDict:
        template = infoDict["ind_value"] + " " + part_data.package + " " + (infoDict["amp_value"] if "amp_value" in infoDict else "")
    else:
        template = ""

    template = template.strip()

    print("Part name: " + part_data.name)
    print("Part link: " + part_data.link)
    print("Confirm/enter the template: ")
    template = utils.inputWithPrefill(text=template, prompt="")

    parts = Part.list(api)
    # filter all the parts that have .is_template = True
    templates = list(filter(lambda x: x.is_template, parts))
    # find templates with close names to the template we want to create
    partTemplate = utils.findPartTemplate(template, templates)

    os.system(CLR)

    newTemplate = False

    if not partTemplate:
        if click.confirm("No existing template found, would you like to create one?", default=True):
            newTemplate = True
    else:
        if click.confirm(f"Found existing template called:\n{partTemplate.name}\nThe current template is:\n{template}\nUse the existing tempalte to create the new part?\ny - use existing to create the part / n - create new template"):
            newTemplate = False
        else:
            newTemplate = True

    templateObj = None
    if newTemplate:
        print("Creating new template...")
        args = {
            'name': template,
            'description': part_data.template_description,
            'category': category_pk,
            'default_location': location_pk,
            'component': True,
            'is_template': True
        }
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
            print("Please enter the link (enter to skip):")
            inp = input()
            if inp != "":
                args['link'] = inp
        os.system(CLR)
        # print the dict in a nice format
        print("Template information:")  
        for key, value in args.items():
            if key == "category":
                value = [elem for elem in categories if elem.pk == value][0].name
            elif key == "default_location":
                value = [elem for elem in locations if elem.pk == value][0].name
            print(f"{key}: {value}")
        if click.confirm("Confirm template information?", default=True):
            templateObj = Part.create(api, args)
            print("Template created!")
    os.system(CLR)

    if templateObj != None:
        return partTemplate
    
    return templateObj


def selectFromTree(utils, tree_root, items, prompt_text):
    """Helper function to select from a tree structure"""
    # Get the list of items from drawTree
    item_list = utils.drawTree(tree_root, items)
    
    # Display the tree
    click.secho(prompt_text, bold=True)
    
    # Prompt for selection
    choice = click.prompt(
        f"Enter your choice (1-{len(item_list)-1})",
        type=click.IntRange(1, len(item_list)-1)
    )
    
    # Return the selected item's primary key
    selected_item = item_list[choice]
    return selected_item[1][0]  # Assuming same structure as original


def addParameters(api: InvenTreeAPI, part: Part, part_data: PartData):
    print("Adding parameters...")
    for template in ParameterTemplate.list(api):
        for param in part_data.parameters:
            if param.name != template["name"]:
                continue
            Parameter.create(api, {'part':part.pk, 'template': template.pk, 'data': param.value[0]})
            break

def addStock(api: InvenTreeAPI, part: Part, part_data: PartData, location_pk):
    quantity = click.prompt(
        "Please enter the quantity",
        type=click.IntRange(min=0),
        default=1
    )

    # Calculate and display suggested price
    suggested_total = round(float(part_data.unit_price) * quantity, 6)

    # Get total price with validation
    total_price = click.prompt(
        "Please enter the total price for the order",
        type=click.FloatRange(min=0.00000001),
        default=suggested_total
    )

    # Calculate unit price
    unit_price = round(total_price / quantity, 6)

    # Create stock item
    stock = StockItem.create(api, {
        'part': part.pk,
        'location': location_pk,
        'quantity': quantity,
        'purchase_price': unit_price
    })

    print("Part added to stock!")
import click
from anytree import Node, search
from inventree.api import InvenTreeAPI
from inventree.part import PartCategory, Part, ParameterTemplate, Parameter
from inventree.stock import StockLocation
from backend.base import VALID_PART_PARAMETERS, PartData
from backend.utilities import Tools
from backend.utilities import DuplicateChoice as PartDupChoice

def validate_parameters(api: InvenTreeAPI, part_data: PartData):
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

def add_parameters(api: InvenTreeAPI, part: Part, part_data: PartData):
    print("Adding parameters...")
    for template in ParameterTemplate.list(api):
        for param in part_data.parameters:
            if param.name != template["name"]:
                continue
            Parameter.create(api, {'part':part.pk, 'template': template.pk, 'data': param.value[0]})
            break

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

def select_from_tree(utils: Tools, tree_root: Node, items: tuple, tree_type="category") -> int:
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

def create_part(api: InvenTreeAPI, category_pk: int, location_pk: int, part_data: PartData, variant_of = None, part_count: int = 0, minimal_stock: int = 0) -> None:
    args = {
        'name': part_data.name,
        'description': part_data.description,
        'link': part_data.link,
        'category': category_pk,
        'default_location': location_pk,
        'keywords' : part_data.keywords,
        'component': True,
        'is_template': False
    }
    
    if part_data.remote_image != "":
        args['remote_image'] = part_data.remote_image

    if variant_of:
        args['variant_of'] = variant_of

    if part_count > 0:
        args['initial_stock'] = {'quantity': part_count, 'location': location_pk}

    if minimal_stock > 0:
        args['minimum_stock'] = minimal_stock

    if click.confirm("Would you like to set the MPN as Internal Part Number?", default=True):
        args["IPN"] = part_data.manufacturer_pn

    # Additional logic for setting template, minimum stock, etc., as needed
    part = Part.create(api, args)
    add_parameters(api, part, part_data)
    print(f"Part created: {part.name} (pk: {part.pk})")

def handle_template_creation(api: InvenTreeAPI, utils: Tools, part_data: PartData, category_pk: int, location_pk: int, part_categories = None, part_locations = None) -> int | None:
    # First we generate a name for the template
    info = utils.parseComponent(part_data.description)

    # construct template using: <value> <package> <voltage rating (for capacitors)>/<power rating (for resistors)>/<curent>
    # in one line we check if this is a resistor or a capacitor, we check it depending on if res_value or cap_value keys are present in the info
    if "res_value" in info and "ind_value" not in info:
        template = info["res_value"] + " " + part_data.package + " " + (info["power_value"] if "power_value" in info else "")
    elif "cap_value" in info:
        template = info["cap_value"] + " " + part_data.package + " " + (info["volt_value"] if "volt_value" in info else "")
    elif "ind_value" in info:
        template = info["ind_value"] + " " + part_data.package + " " + (info["amp_value"] if "amp_value" in info else "")
    else:
        template = ""
    
    template = template.strip()

    # Present the user with the template we created and ask for confirmation/editing
    print("Part name: " + part_data.name)
    print("Part link: " + part_data.link)
    print("Confirm/enter the template: ")
    template = utils.input_with_prefill(text=template, prompt="")
    
    
    # Get a list of existing templates
    templates = Part.list(api, is_template=True)
    # find if an existing template exists
    existing_template = utils.find_part_template(template, templates)

    # clear_screen()
    use_existing = False
    create_new = False
    if existing_template:
        print(f"Existing template found: {existing_template.name}. The name you entered: {template}.\nUse this template? (y/n): ")
        use_existing = input().lower() == 'y'
    else:
        print("No existing template found. Create a new one? (y/n): ")
        create_new = input().lower() == 'y'

    if use_existing:
        template_pk = existing_template.pk
    elif create_new:
        while True:
            # Gather additional information for template creation here
            template_args = {
                'name': template,
                'description': part_data.template_description,
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

            if input() == "y":
                template = Part.create(api, template_args)
                template_pk = template.pk
                break
    else:
        return None
    return template_pk

def handle_part_quantity() -> int:
    return click.prompt(
        f"Enter the quantity of the part",
        type=click.IntRange(min=0),
        default=1,
        show_default=True
    )

def handle_minimal_stock() -> int:
    return click.prompt(
        f"Enter the minimal stock for the part (default is 0)",
        type=click.IntRange(min=0),
        default=0,
        show_default=False
    )

def handle_existing_part(utils: Tools, part_number: str, parts: list[Part], part_name: str = None) -> tuple[PartDupChoice, int]:
    existing_pk = utils.find_part(part_number, parts, part_name)
    
    if existing_pk is None:
        return PartDupChoice.CREATE_NEW, None

    click.echo(f"Part {part_name or '<unnamed>'} ({part_number}) exists with pk={existing_pk}.")
    click.echo("1) Add stock\r\n2) Create new\r\n3) Skip")

    choice = click.prompt(
        "Select an option",
        type=click.Choice(["1", "2", "3"], case_sensitive=False),
        show_choices=False
    )

    return {
        "1": (PartDupChoice.ADD_STOCK, existing_pk),
        "2": (PartDupChoice.CREATE_NEW, None),
        "3": (PartDupChoice.SKIP,     None),
    }[choice]

def handle_adding_stock(api: InvenTreeAPI, part_pk: int):
    part = Part(api, pk=part_pk)
    stock_item = part.getStockItems()[0]
    current_stock = int(part.in_stock if part else 0)
    if part:
        print(f"Adding stock to part: {part.name}, current stock: {current_stock}")
        stock_quantity = int(input("Enter the quantity to add: "))
        stock_item.addStock(stock_quantity)
        part.reload()
        print(f"New stock count: {int(part.in_stock if part else 0)}")
    else:
        print("Part not found.")

def handle_parts_price(part_count: int, unit_price: str = None) -> float:
    # Calculate suggested total if unit price is available
    suggested_total = round(part_count * float(unit_price), 2) if unit_price else None
    
    # Get total price with validation
    total_price = click.prompt(
        f"Enter total price for {part_count} parts",
        type=click.FloatRange(min=0),
        default=suggested_total,
        show_default=suggested_total is not None
    )
    
    return total_price / part_count

def select_supplier(suppliers, utils, config):
    supplier_names = list(suppliers.keys())

    click.secho("Please select the supplier:", bold=True)
    for i, name in enumerate(supplier_names, 1):
        click.echo(f"{i}. {name}")

    choice = click.prompt(
        f"Enter your choice (1-{len(supplier_names)})",
        type=click.IntRange(1, len(supplier_names)),
        show_choices=False
    )

    return suppliers[supplier_names[choice - 1]](utils, config)

def select_input_option(utils: Tools) -> str: 
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
        adress = utils.input_with_prefill(text="http://192.168.100.157:8080/video", prompt="")

    return adress
import click
from inventree.api import InvenTreeAPI
from inventree.part import Part, ParameterTemplate, Parameter
from backend.base import VALID_PART_PARAMETERS, PartData
from backend.utilities import Tools
from backend.utilities import DuplicateChoice as PartDupChoice

def handle_parameters(api: InvenTreeAPI):
    existing_templates = {template["name"] for template in ParameterTemplate.list(api)}

    if any(template not in existing_templates for template in VALID_PART_PARAMETERS):
        print("Adding missing parameter templates...")

    # Create missing templates
    for key in VALID_PART_PARAMETERS.keys():
        if key not in existing_templates:
            tmp = {"name": key, "units": "" if VALID_PART_PARAMETERS[key] is None else VALID_PART_PARAMETERS[key]}
            ParameterTemplate.create(api, tmp)
    
def handle_template_creation(api: InvenTreeAPI, utils: Tools, part_data: PartData, category_pk: int, location_pk: int) -> PartData:
    # First we generate a name for the template
    info = utils.parseComponent(part_data.description)
    template_data = {}

    package = next((param.value[0] for param in part_data.parameters if param.name == "Package"), "")

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
    print("Part name: " + part_data.name)
    print("Part link: " + part_data.link)
    print("Confirm/enter the template: ")
    template_data["name"] = utils.input_with_prefill(text=template, prompt="")
    
    
    # Get a list of existing templates
    templates = Part.list(api, is_template=True)
    # find if an existing template exists
    existing_template = utils.find_part_template(template_data["name"], templates)

    # clear_screen()
    use_existing = False
    create_new = False
    if existing_template:
        print(f"Existing template found: {existing_template.name}. The name you entered: {template_data["name"]}.\nUse this template? (y/n): ")
        use_existing = input().lower() == 'y'
    else:
        print("No existing template found. Create a new one? (y/n): ")
        create_new = input().lower() == 'y'

    if use_existing:
        template_data["part_pk"] = existing_template.pk
    elif create_new:
        # Gather additional information for template creation here
        template_data["description"] = part_data.description
        template_data["category_pk"] = category_pk
        template_data["location_pk"] = location_pk

        print("Would you like to provide additional information? (y/n)")
        additional_info = input().lower() == 'y'
        if additional_info:
            print("Please enter the image link (enter to skip):")
            inp = input()
            if inp != "":
                template_data['remote_image'] = inp
            print("Please enter the minimum stock value (enter to skip):")
            inp = input()
            if inp != "":                    
                template_data['minimum_stock'] = int(inp)
            print("Please enter the note (enter to skip):")
            inp = input()
            if inp != "":
                template_data['note'] = inp
            print("Please enter the link (enter to skip):")
            inp = input()
            if inp != "":
                template_data['link'] = inp

    return PartData(
        name = template_data["name"] if "name" in template_data else None,
        supplier_pn = None,
        manufacturer_pn = None,
        description = template_data["description"] if "description" in template_data else None,
        remote_image = template_data["remote_image"] if "remote_image" in template_data else None,
        link = template_data["link"] if "link" in template_data else None,
        unit_price = None,
        minimum_stock = template_data["minimum_stock"] if "minimum_stock" in template_data else None,
        note = template_data["note"] if "note" in template_data else None,
        parameters = None,
        keywords = None,
        category_pk = category_pk,
        location_pk = location_pk,
        part_pk = template_data["part_pk"] if "part_pk" in template_data else None,
        is_template = True
    )

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
import os
import click
from dataclasses import dataclass
from abc import ABC, abstractmethod

from anytree import Node
from inventree.api import InvenTreeAPI
from inventree.part import Parameter as InvParameter
from inventree.part import Part, PartCategory, ParameterTemplate
from inventree.stock import StockLocation

from backend.utilities import Tools
from backend.tree_utilities import select_from_tree

# Define valid part parameters
VALID_PART_PARAMETERS = {
    "Resistance": "ohm",                
    "Power Rating": "W",                
    "Capacitance": "F",
    "Inductance": "H",
    "Voltage Rating": "V",
    "Forward Voltage": "V",             
    "Drain to Source Voltage": "V",
    "Collector to Emitter Voltage": "V",
    "Current Rating": "A",              
    "Reverse Leakage Current": "A",    
    "Saturation Current": "A",          
    "ESR": "ohm",                       
    "Tolerance": "%",
    "Package": None,
    "Temperature Coefficient": None
}

# Create a normalized version of parameter names for case-insensitive matching
NORMALIZED_PARAM_NAMES = {name.lower().replace(" ", ""): name 
                          for name in VALID_PART_PARAMETERS}

CLR = "cls" if os.name == "nt" else "clear"

@dataclass
class Parameter:
    name: str                       # The name of the parameter
    value_str: str = None           # The original string representation of the parameter value as scraped from the supplier
    value: tuple[str, str] = None   # Parsed representation of the value as a (numeric_value, unit) tuple

    def __post_init__(self):
        utils = Tools()

        # Normalize the input name for case-insensitive matching
        normalized_name = self.name.lower().replace(" ", "")

        # Validate the parameter name and get standarized format
        if normalized_name in NORMALIZED_PARAM_NAMES.keys():
            self.name = NORMALIZED_PARAM_NAMES[normalized_name]
        else:
            raise Exception(f"Invalid parameter ({self.name})!")
        
        if self.value and self.value_str is None:
            self.value_str = f"{self.value[0]}{self.value[1]}"
        
        # Convert string value to tuple (e.g. 15nF -> (15n, F))
        if self.value is None:
            # Handle parameters without units
            if VALID_PART_PARAMETERS[self.name] is None:
                self.value = (self.value_str, "")
                return

            # Should be rewritten but it's re-using functions kept for backwards compatibility with component templates
            ret = utils.parseComponent(self.value_str)

            if len(ret) == 0:
                raise Exception(f"Parsing component value failed! Failed string: {self.value_str}")

            values = list(ret.values())

            if len(values) > 1:
                click.echo( "Multiple possible parameter values were found for " + click.style(self.name, bold=True, fg="yellow"))
                for idx, valstr in enumerate(values):
                    click.secho(f"{idx}. {valstr}", bold=False)
                
                choice = click.prompt(
                    f"Select correct [value][unit] option (0-{len(values)-1})",
                    type=click.IntRange(0, len(values)-1),
                    show_choices=False
                )
                selected = values[choice]
            else:
                # only one choice, pick it
                selected = values[0]

            val, unit = utils.splitUnits(selected)

            if (val, unit) != None:
                self.value = (val, unit)

@dataclass
class PartData:
    name: str                       # Display name of the part
    supplier_pn: str                # Supplier's part number
    manufacturer_pn: str            # Manufacturer's part number
    description: str                # Detailed description of the part
    remote_image: str               # URL to the part's main image
    link: str                       # URL to the part's product page
    unit_price: float               # Price per single unit
    minimum_stock: int              # Minimum quantity to maintain in stock
    part_count: int                 # Quantity to initially stock or add
    note: str                       # Any additional note or comment about the part
    parameters: list[Parameter]     # List of technical parameters
    keywords: str = ""              # Comma-separated keywords for search
    category_pk: int = None         # Category ID to classify the part 
    location_pk: int = None         # Storage location ID
    part_pk: int = None             # Existing part template key
    is_template: bool = False       # Flag marking this data as a template

    def create(self, api, template_pk = None):
        """
        Create a new part or template in the InvenTree system.
        Returns the primary key of the new or existing part.
        """
        args = {}

        # If creating a template part
        if self.is_template:
            # If already existing template was assigned return it's pk
            if self.part_pk: return self.part_pk
            
            args['name'] = self.name
            args['description'] = self.description
            args['category'] = self.category_pk
            args['default_location'] = self.location_pk
            args['component'] = True
            args['is_template'] = True

            if self.remote_image: args['remote_image'] = self.remote_image
            if self.minimum_stock: args['minimum_stock'] = self.minimum_stock
            if self.note: args['note'] = self.note
            if self.link: args['link'] = self.link

        # Creating a regular part (possibly a variant)
        else:
            args['name'] = self.name
            args['description'] = self.description
            args['link'] = self.link
            args['category'] = self.category_pk
            args['default_location'] = self.location_pk
            args['keywords'] = self.keywords
            args['component'] = True
            args['is_template'] = False

            if self.part_count > 0: args['initial_stock'] = {'quantity': self.part_count, 'location': self.location_pk}

            if self.remote_image: args['remote_image'] = self.remote_image
            if self.part_pk: args['variant_of'] = template_pk
            if self.minimum_stock: args['minimum_stock'] = self.minimum_stock
            if self.note: args['note'] = self.note

            if click.confirm("Would you like to set the MPN as Internal Part Number?", default=True):
                args["IPN"] = self.manufacturer_pn
            
        print("Creating new part...")
        part = Part.create(api, args)
        if self.parameters: self.add_parameters(api, part)
        print(f"Part created: {part.name} (pk: {part.pk})")
        return part.pk

    def add_parameters(self, api: InvenTreeAPI, part: Part):
        """
        Iterate through all available parameter templates and add matching
        parameters to the newly created part.
        """
        print("Adding parameters...")
        for template in ParameterTemplate.list(api):
            for param in self.parameters:
                if param.name != template["name"]:
                    continue
                InvParameter.create(api, {'part':part.pk, 'template': template.pk, 'data': param.value[0]})
                break

    
    def interactive_edit(self, utils: Tools, 
                        category_tree_root: Node, categories: list[PartCategory],
                        location_tree_root: Node, locations: list[StockLocation]):
        """Interactive editor for all part data fields with improved UX"""
        # Create a copy of the original data for cancel option
        original_data = {attr: getattr(self, attr) for attr in vars(self)}
        
        # Define all editable fields with their metadata
        field_definitions = [
            ("Name", "name", str),
            ("Supplier Part Number", "supplier_pn", str),
            ("Manufacturer Part Number", "manufacturer_pn", str),
            ("Description", "description", str),
            ("Image URL", "remote_image", str),
            ("Product URL", "link", str),
            ("Unit Price", "unit_price", float),
            ("Minimum Stock", "minimum_stock", int),
             ("Part Count", "part_count", int),
            ("Note", "note", str),
            ("Keywords", "keywords", str),
            ("Parameters", "parameters", None),  # Special handling
            ("Category", "category_pk", None),   # Special handling
            ("Location", "location_pk", None),   # Special handling
        ]
        
        if self.is_template and self.part_pk:
            click.secho("You can't edit existing part template!", fg='bright_yellow', bold=True)
            return

        # Exclude fields for templates
        if self.is_template:
            excluded_fields = ["supplier_pn", "manufacturer_pn", "unit_price", "parameters", "keywords"]
            field_definitions = [field for field in field_definitions if field[1] not in excluded_fields]

        while True:
            os.system(CLR)
            self.pretty_print(categories, locations)
            
            click.secho("\nEDITING MENU", fg='bright_yellow', bold=True)
            click.echo("="*60)
            
            # Display menu items dynamically
            for idx, (display_name, _, _) in enumerate(field_definitions, 1):
                # Skip None values for category/location
                if (display_name == "Category" and self.category_pk is None) or \
                   (display_name == "Location" and self.location_pk is None):
                    continue
                click.echo(f"{idx:>2}. {display_name}")
            
            click.echo("-"*60)
            click.echo(" s. Save and continue")
            click.echo(" r. Reset all changes")
            click.echo(" q. Quit without saving")
            click.echo("="*60)
            
            choice = click.prompt("Select field to edit", type=str).lower()
            
            # Action handling
            if choice == 's':
                return True
            elif choice == 'q':
                if click.confirm("Discard all changes?"):
                    for attr, value in original_data.items():
                        setattr(self, attr, value)
                    return False
            elif choice == 'r':
                if click.confirm("Reset all changes to original values?"):
                    for attr, value in original_data.items():
                        setattr(self, attr, value)
                    click.secho("✓ All changes reset", fg='green')
                    click.pause()
            
            # Field editing
            elif choice.isdigit():
                idx = int(choice) - 1
                
                if idx < 0 or idx >= len(field_definitions):
                    click.secho("Invalid selection!", fg='red')
                    click.pause()
                    continue
                    
                display_name, attr_name, field_type = field_definitions[idx]
                
                # Special handling for parameters
                if attr_name == "parameters":
                    self.edit_parameters()
                    continue
                    
                # Special handling for category/location
                if attr_name in ["category_pk", "location_pk"]:
                    tree_type = "category" if attr_name == "category_pk" else "location"
                    tree_root = category_tree_root if tree_type == "category" else location_tree_root
                    items = categories if tree_type == "category" else locations
                    new_value = select_from_tree(utils, tree_root, items, tree_type)
                    setattr(self, attr_name, new_value)
                    continue
                
                # Get current value and prompt
                current_value = getattr(self, attr_name)
                prompt = f"Enter new {display_name}"
                
                # Handle None values
                if current_value is None:
                    if field_type == str:
                        current_value = ""
                    elif field_type in [int, float]:
                        current_value = 0
                
                # Get new value with prefill
                new_value = utils.input_with_prefill(f"{prompt}: ", str(current_value))
                
                # Convert and validate
                try:
                    if field_type == float:
                        new_value = float(new_value)
                    elif field_type == int:
                        new_value = int(new_value)
                    # Strings don't need conversion
                except ValueError:
                    click.secho(f"Invalid input! Must be a {field_type.__name__}.", fg='red')
                    click.pause()
                    continue
                
                # Set new value
                setattr(self, attr_name, new_value)
                click.secho(f"✓ Updated {display_name}", fg='green')
                click.pause()
            
            else:
                click.secho("Invalid selection!", fg='red')
                click.pause()

    def pretty_print(self, categories: list[PartCategory] = None, 
                     locations: list[StockLocation] = None):
        """Display all part information in a clean, formatted layout"""

        if self.is_template and self.part_pk:
            return
        
        os.system(CLR)
        click.secho("\n" + "="*60, fg='bright_cyan')
        click.secho("PART SUMMARY", fg='bright_cyan', bold=True)
        click.secho("="*60, fg='bright_cyan')
        
        # Basic information section
        click.secho("\nBasic Information:", fg='bright_yellow', bold=True)
        click.echo(f"{'Name:':<20} {click.style(self.name, fg='bright_cyan')}")
        if not self.is_template:
            click.echo(f"{'Supplier PN:':<20} {self.supplier_pn}")
            click.echo(f"{'Manufacturer PN:':<20} {self.manufacturer_pn}")
            click.echo(f"{'Unit Price:':<20} {self.unit_price:.6f}")
            click.echo(f"{'Part Count:':<20} {self.part_count}")
        click.echo(f"{'Min Stock:':<20} {self.minimum_stock}")
        
        # Additional details
        click.secho("\nDetails:", fg='bright_yellow', bold=True)
        if not self.is_template:
            click.echo(f"{'Keywords:':<20} {click.style(self.keywords, fg='magenta')}")
        click.echo(f"{'Note:':<20} {self.note[:100] + '...' if self.note and len(self.note) > 100 else self.note or 'Not set'}")
        
        # Description section
        click.secho("\nDescription:", fg='bright_yellow', bold=True)
        desc = self.description[:200] + '...' if self.description and len(self.description) > 200 else self.description or 'Not set'
        click.echo(desc)
        
        # URLs section
        click.secho("\nURLs:", fg='bright_yellow', bold=True)
        click.echo(f"{'Image:':<10} {click.style(self.remote_image, fg='bright_blue', underline=True) if self.remote_image else 'Not set'}")
        click.echo(f"{'Product:':<10} {click.style(self.link, fg='bright_blue', underline=True) if self.link else 'Not set'}")
        
        # Parameters section
        if not self.is_template and self.parameters:
            click.secho("\nParameters:", fg='bright_yellow', bold=True)
            self.__display_parameters_table()
        
        # Category and location - show names if available
        click.secho("\nInventory:", fg='bright_yellow', bold=True)
        category_name = "Not set"
        if self.category_pk and categories:
            for cat in categories:
                if cat.pk == self.category_pk:
                    category_name = cat.name
                    break
        location_name = "Not set"
        if self.location_pk and locations:
            for loc in locations:
                if loc.pk == self.location_pk:
                    location_name = loc.name
                    break
        click.echo(f"{'Category:':<12} {click.style(category_name, fg='green')}")
        click.echo(f"{'Location:':<12} {click.style(location_name, fg='green')}")
        
        # Template status
        if self.is_template:
            click.secho("\nTemplate Status:", fg='bright_yellow', bold=True)
            status = f"Existing Template: {self.part_pk}" if self.part_pk else "New Template"
            color = 'bright_green' if self.part_pk else 'bright_yellow'
            click.echo(f"{'Status:':<15} {click.style(status, fg=color)}")
        
        click.secho("\n" + "="*80, fg='bright_cyan')


    def edit_parameters(self):
        """Interactive parameter editing"""
        # Store original parameters in case of reset
        original_parameters = self.parameters.copy()
        
        while True:
            os.system(CLR)
            click.secho(f"\nEditing Parameters for {self.supplier_pn}", fg='bright_cyan', bold=True)
            self.__display_parameters_table()
            
            action = click.prompt(
                "\nChoose an action:\n"
                "  [number] - Edit parameter\n"
                "  d[number] - Delete parameter\n"
                "  a - Add new parameter\n"
                "  r - Reset all parameters\n"
                "  s - Save and finish\n"
                "  q - Quit without saving\n"
                "> ",
                type=str,
                default='s'
            ).strip().lower()

            if action == 's':
                return  # Save and exit
            elif action == 'q':
                if click.confirm("Discard all changes?"):
                    return
            elif action == 'a':
                self.__add_parameter()
            elif action == 'r':
                if click.confirm("Reset all parameters to original values?"):
                    self.parameters = original_parameters.copy()
                    click.secho("✓ All parameters reset", fg='green')
                    click.pause()
            elif action.startswith('d') and action[1:].isdigit():
                self.__delete_parameter(int(action[1:]))
            elif action.isdigit():
                self.__edit_parameter(int(action))
            else:
                click.secho("Invalid selection!", fg='red')
                click.pause()

    def __display_parameters_table(self):
        """Display parameters in a properly aligned table"""
        
        click.echo("-" * 59)

        if not self.parameters:
            click.secho("\nNo parameters defined", fg='yellow')
            return

        # Header with fixed widths
        click.echo(f"{'ID':<4} {'Parameter':<21} {'Value':>20} {'Unit':>11}")
        click.echo("-" * 59)

        # Display each parameter with proper alignment
        for idx, param in enumerate(self.parameters, 1):
            value, unit = param.value
            unit_display = unit if unit else "-"
            
            # Format ID with color
            id_display = click.style(str(idx), fg='bright_cyan')
            
            # Format value with color and right alignment
            value_display = click.style(f"{value:>20}", fg='bright_yellow')
            
            # Print the row
            click.echo(f"{id_display:<4} {param.name:<25}{value_display} {unit_display:>10}")

        click.echo("-" * 59)

    def __edit_parameter(self, param_id: int):
        """Edit a specific parameter"""
        if param_id < 1 or param_id > len(self.parameters):
            click.secho("Invalid parameter ID!", fg='red')
            click.pause()
            return
        
        param = self.parameters[param_id - 1]
        current_value, unit = param.value
        
        os.system(CLR)  # Clear screen
        click.secho(f"Editing: {param.name}", fg='bright_cyan', bold=True)
        click.echo(f"Current value: {click.style(current_value, fg='bright_yellow')} {unit if unit else ''}")
        
        new_value = click.prompt(
            "\nEnter new value",
            default=current_value
        )
        
        param.value = (new_value, unit)
        click.secho(f"\n✓ Updated {param.name} to {new_value} {unit}", fg='green')
        click.pause()

    def __delete_parameter(self, param_id: int):
        """Delete a specific parameter"""
        if param_id < 1 or param_id > len(self.parameters):
            click.secho("Invalid parameter ID!", fg='red')
            click.pause()
            return
        
        param = self.parameters[param_id - 1]
        os.system(CLR)  # Clear screen
        click.secho(f"Delete Parameter: {param.name}", fg='bright_red', bold=True)
        click.echo(f"Current value: {param.value[0]} {param.value[1]}")
        
        if click.confirm("\nAre you sure you want to delete this parameter?"):
            del self.parameters[param_id - 1]
            click.secho(f"\n✓ Deleted {param.name}", fg='bright_red')
        click.pause()

    def __add_parameter(self):
        """Add a new parameter from valid list"""
        # Get available parameters not already added
        existing = {p.name for p in self.parameters}
        available = [
            name for name in VALID_PART_PARAMETERS.keys() 
            if name not in existing
        ]
        
        if not available:
            os.system(CLR)  # Clear screen
            click.secho("\nAll valid parameters already added!", fg='yellow')
            click.pause()
            return
        
        os.system(CLR)  # Clear screen
        click.secho("Add New Parameter", fg='bright_green', bold=True)
        
        # Display available parameters
        click.secho("\nAvailable Parameters:", fg='bright_cyan')
        for idx, name in enumerate(available, 1):
            unit = VALID_PART_PARAMETERS[name] or "unitless"
            click.echo(f"{idx}: {name} ({unit})")
        
        # Select parameter to add
        choice = click.prompt(
            "\nSelect parameter to add (number) or 0 to cancel",
            type=int,
            default=0
        )
        
        if choice == 0:
            return
        
        try:
            name = available[choice - 1]
            unit = VALID_PART_PARAMETERS[name] or ""
            value = click.prompt(f"\nEnter value for {name}")
            self.parameters.append(Parameter(name, value=(value, unit)))
            click.secho(f"\n✓ Added {name}: {value} {unit}", fg='green')
            click.pause()
        except (IndexError, TypeError):
            click.secho("Invalid selection!", fg='red')
            click.pause()

class baseSupplier(ABC):
    """Abstract base class for supplier integrations"""

    @abstractmethod
    def __init__(self,  utils: Tools, config):
        pass
    
    @abstractmethod
    def parseCode(self, code: str) -> str:
        """
        Barcode parsing interface (implement in concrete classes)
        Args:
            code: Raw barcode input
        Returns:
            Supplier-specific part number
        """
        pass

    @abstractmethod
    def query(self, partNumber) -> PartData:
        """
        Part data retrieval interface (implement in concrete classes)
        Args:
            partNumber: Valid part number for the supplier
        Returns:
            Structured part data
        """
        pass

    @abstractmethod
    def _mapParameters(self, supplier_params) -> list[Parameter]:
        """
            Maps list of supplier parameters to list of standardized
            Parameter objects consistent with VALID_PART_PARAMETERS. 
        """
        pass
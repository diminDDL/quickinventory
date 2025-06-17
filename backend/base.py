import os
import click
from dataclasses import dataclass
from abc import ABC, abstractmethod

from backend.utilities import Tools

# Define valid part parameters
# TODO maybe some mapping? For example Digikey and LCSC might have a slightly different
# (or just ugly) names for the same parameters. Ig it could be done on supplier class level.
VALID_PART_PARAMETERS = {
    "Resistance": "ohm",                # TODO LCSC Mapping (Thermistors have @25*C or sth)
    "Power Rating": "W",                # TODO LCSC Mapping (Transistors)
    "Capacitance": "F",
    "Inductance": "H",
    "Voltage Rating": "V",
    "Forward Voltage": "V",             # TODO LCSC Mapping
    "Drain to Source Voltage": "V",
    "Collector to Emitter Voltage": "V",# TODO LCSC Mapping
    "Current Rating": "A",              # TODO LCSC Mapping (Transistors)
    "Reverse Leackage Current": "A",    # TODO LCSC Mapping
    "Saturation Current": "A",          # TODO LCSC Mapping
    "ESR": "ohm",                       # TODO LCSC Mapping
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
    supplier_pn: str             # Supplier's part number
    manufacturer_pn: str         # Manufacturer's part number
    name: str                    # Display name of the part
    description: str             # Detailed description of the part
    parameters: list[Parameter]  # List of technical parameters
    template_description: str    # Description for part templates
    remote_image: str            # URL to the part's main image
    link: str                    # URL to the part's product page
    unit_price: float            # Price per single unit
    package: str                 # Physical package type
    keywords: str = ""           # Comma-separated keywords for search
    
    def interactive_edit(self, utils: Tools):
        """Interactive editor for all part data fields"""
        # Create a copy of the original data for cancel option
        original_data = {
            'supplier_pn': self.supplier_pn,
            'manufacturer_pn': self.manufacturer_pn,
            'name': self.name,
            'description': self.description,
            'template_description': self.template_description,
            'remote_image': self.remote_image,
            'link': self.link,
            'unit_price': self.unit_price,
            'package': self.package,
            'keywords': self.keywords,
            'parameters': self.parameters.copy()
        }
        
        while True:
            os.system(CLR)
            self.pretty_print()
            
            click.secho("\nEDITING MENU", fg='bright_yellow', bold=True)
            click.echo("="*60)
            click.echo(" 1. Supplier Part Number")
            click.echo(" 2. Manufacturer Part Number")
            click.echo(" 3. Name")
            click.echo(" 4. Main Description")
            click.echo(" 5. Template Description")
            click.echo(" 6. Image URL")
            click.echo(" 7. Product URL")
            click.echo(" 8. Unit Price")
            click.echo(" 9. Package")
            click.echo("10. Keywords")
            click.echo("11. Parameters")
            click.echo("-"*60)
            click.echo(" s. Save and continue")
            click.echo(" r. Reset all changes")
            click.echo(" q. Quit without saving")
            click.echo("="*60)
            
            choice = click.prompt("Select field to edit", type=str).lower()
            
            if choice == 's':
                return True  # Save changes
            elif choice == 'q':
                if click.confirm("Discard all changes?"):
                    # Restore original data
                    for key, value in original_data.items():
                        setattr(self, key, value)
                    return False
            elif choice == 'r':
                if click.confirm("Reset all changes to original values?"):
                    for key, value in original_data.items():
                        setattr(self, key, value)
                    click.secho("✓ All changes reset", fg='green')
                    click.pause()
            elif choice == '11':
                self.edit_parameters()
            elif choice in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']:
                field_map = {
                    '1': ('supplier_pn', "Enter new Supplier Part Number"),
                    '2': ('manufacturer_pn', "Enter new Manufacturer Part Number"),
                    '3': ('name', "Enter new Part Name"),
                    '4': ('description', "Enter new Main Description"),
                    '5': ('template_description', "Enter new Template Description"),
                    '6': ('remote_image', "Enter new Image URL"),
                    '7': ('link', "Enter new Product URL"),
                    '8': ('unit_price', "Enter new Unit Price"),
                    '9': ('package', "Enter new Package"),
                    '10': ('keywords', "Enter new Keywords"),
                }
                
                field_name, prompt = field_map[choice]
                current_value = str(getattr(self, field_name))
                
                # Use prefill input
                new_value = utils.input_with_prefill(f"{prompt}: ", current_value)
                
                # Convert numeric fields
                if field_name == 'unit_price':
                    try:
                        new_value = float(new_value)
                    except ValueError:
                        click.secho("Invalid price! Must be a number.", fg='red')
                        click.pause()
                        continue
                
                setattr(self, field_name, new_value)
            else:
                click.secho("Invalid selection!", fg='red')
                click.pause()

    def pretty_print(self):
        """Display all part information in a clean, formatted layout"""
        os.system(CLR)
        click.secho("\n" + "="*60, fg='bright_cyan')
        click.secho("PART SUMMARY", fg='bright_cyan', bold=True)
        click.secho("="*60, fg='bright_cyan')
        
        # Basic information section
        click.secho("\nBasic Information:", fg='bright_yellow', bold=True)
        click.echo(f"{'Supplier PN:':<20} {click.style(self.supplier_pn, fg='bright_cyan')}")
        click.echo(f"{'Manufacturer PN:':<20} {self.manufacturer_pn}")
        click.echo(f"{'Name:':<20} {self.name}")
        click.echo(f"{'Package:':<20} {self.package}")
        click.echo(f"{'Unit Price:':<20} {self.unit_price:.6f}")
        click.echo(f"{'Keywords:':<20} {click.style(self.keywords, fg='magenta')}")
        
        # Description section
        click.secho("\nDescriptions:", fg='bright_yellow', bold=True)
        click.echo(f"{'Main:':<20} {self.description[:100] + '...' if len(self.description) > 100 else self.description}")
        click.echo(f"{'Template:':<20} {self.template_description[:100] + '...' if len(self.template_description) > 100 else self.template_description}")
        
        # URLs section
        click.secho("\nURLs:", fg='bright_yellow', bold=True)
        click.echo(f"{'Image:':<20} {click.style(self.remote_image, fg='bright_blue', underline=True)}")
        click.echo(f"{'Product:':<20} {click.style(self.link, fg='bright_blue', underline=True)}")
        
        # Parameters section - matches the editing view format
        click.secho("\nParameters:", fg='bright_yellow', bold=True)
        self.__display_parameters_table()
        
        click.secho("\n" + "="*60, fg='bright_cyan')


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
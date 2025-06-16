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
    parameters: list[Parameter]  # List of technical parameters (e.g., resistance, tolerance)
    template_description: str    # Description to use when creating part templates
    remote_image: str            # URL to the part's main image
    link: str                    # URL to the part's product page on supplier website
    unit_price: float            # Price per single unit in supplier's currency
    package: str                 # Physical package type (e.g., "0805", "SOT-23")

    def edit_parameters(self):
        """Interactive parameter editing"""
        # Store original parameters in case of reset
        original_parameters = self.parameters.copy()
        
        while True:
            os.system(CLR)
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
        click.secho(f"\nEditing Parameters for {self.supplier_pn}", fg='bright_cyan', bold=True)
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
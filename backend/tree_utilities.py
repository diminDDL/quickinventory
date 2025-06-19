import click
from inventree.api import InvenTreeAPI
from anytree import Node, search
from inventree.part import PartCategory
from inventree.stock import StockLocation

from backend.utilities import Tools

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
            choice = click.prompt(
                f"Please select the {tree_type} for the new part (1-{len(tree_ids)-1})",
                type=click.IntRange(1, len(tree_ids)-1),
                show_choices=False
            )
            selected_id = tree_ids[int(choice)][1][0]  # User selects by index
            item_pk = [item.pk for item in items if str(item.pk) == str(selected_id)][0]
            item_name = [item.name for item in items if item.pk == item_pk][0]
            print(f"Selected {tree_type}: {item_name} (pk: {item_pk})")
            return item_pk
        except (ValueError, IndexError):
            # clear_screen()
            print(f"Invalid selection. Please enter a number corresponding to a {tree_type}.")

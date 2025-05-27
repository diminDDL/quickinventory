import os
import sys
import traceback
import cv2
from anytree import Node, RenderTree, search
from inventree.api import InvenTreeAPI
from inventree.part import PartCategory, Part
from inventree.stock import StockLocation, StockItem
from backend.file import fileHandler
from backend.utilities import Tools
from backend.lcsc import LCSC
from backend.utilities import Tools


utils = Tools()
lcsc = LCSC(utils=utils)

ret = lcsc.query("C456924")

print(ret)
from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules

from .patcher import PmhRecordPatcher, CrossrefDoiPatcher

# iterate through the modules in the current package
package_dir = Path(__file__).resolve().parent
for (_, module_name, _) in iter_modules([str(package_dir)]):
    # import the module
    module = import_module(f"{__name__}.{module_name}")


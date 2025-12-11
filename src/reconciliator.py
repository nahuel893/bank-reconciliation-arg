import pandas as pd
from config import settings, get_bank_config, PROJECT_ROOT
import os

# Tasks
"""
* Leer el excel del banco,
    * Normalizar excel del banco
* Leer la bd del 
* comparar Fecha/Cuit/Monto
"""

class Reconciliator:
    def __init__(self):
        """
        Inicializar objeto de conciliacion
        """
        self.config = get_bank_config()
        self.path   = settings.BANK_ASSETS_DIR

    def load_bank_excel(self):
        default_name = self.config.get("default_name")
        options = self.config.get("excel_options")
        sheet_name = options.get("sheet_name")
        headers = options.get("header_row")
        path_bank_excel =  os.path.join(self.path, default_name)

        if os.path.exists(path_bank_excel):
            bank_excel = pd.read_excel(
                path_bank_excel,
                header=headers,
                sheet_name=sheet_name,
            )
        else:
            raise FileNotFoundError(f"Error al encontrar el archivo:{path_bank_excel}") 

        return bank_excel

    def _normalize_cuit(self, cuit: str):
        """
        Metodo que normaliza los cuits del banco macro.
        Si un cuit tiene "-" se toma la 2da parte y se extraen los digitos
        Caso contrario se extraen los digitos de todo el string
        """
        cuit_norm = ''
        
        if "-" in cuit:
            cuit_norm = cuit.split("-")[1]
            cuit_norm = [char for char in cuit_norm if char.isdigit()]
        else:  
            cuit_norm = [char for char in cuit if char.isdigit()]

        cuit_norm = "".join(cuit_norm)
        if cuit_norm.isdigit():
            cuit_norm = int(cuit_norm)


        return cuit_norm


    def load_comp_bd(self):
        pass
        
if __name__ == '__main__':
    r = Reconciliator()
    r.load_bank_excel()
    # test normalize cuit
    print(PROJECT_ROOT)
    cuit_examples = pd.read_excel(os.path.join(PROJECT_ROOT, "tests/cuit_tests_data_set.xlsx"))
    results = []
    for idx, row in cuit_examples.iterrows():
        print("="*60)
        cuit = str(row["Concepto"])

        print(f"Testing cuit: index:{idx} cuit:{cuit}")

        cuit_norm = r._normalize_cuit(cuit)

        print(f"norm: {cuit_norm}")
         
        results.append({"real": cuit, "norm:": cuit_norm})
        
        print("="*60)

    df = pd.DataFrame(results)
    df.to_excel(os.path.join(PROJECT_ROOT,'tests/cuit_tests_results.xlsx'))



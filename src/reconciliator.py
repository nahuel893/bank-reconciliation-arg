import pandas as pd
from config import settings, get_bank_config, PROJECT_ROOT
from logger import get_logger
import os
from datetime import date

# Tasks
"""
* Leer el excel del banco,
    * Normalizar excel del banco
* Leer la bd del
* comparar Fecha/Cuit/Monto
"""

logger = get_logger("reconciliator")

class Reconciliator:
    def __init__(self):
        """
        Inicializar objeto de conciliacion
        """
        self.config = get_bank_config()
        self.path   = settings.BANK_ASSETS_DIR

    def load_bank_excel(self, path_bank_excel="assets/bank/bank_excel.xls") -> pd.DataFrame:
        """
        Carga el excel del banco macro y normaliza la variables utilizables.
        """ 
        default_name = self.config.get("default_name")
        options = self.config.get("excel_options")
        sheet_name = options.get("sheet_name")
        headers = options.get("header_row")
        columns = self.config.get("column_mapping")
        logger.debug(f"Columnas configuradas: {columns}")

        path_bank_excel =  os.path.join(self.path, default_name)
        # Extract
        if os.path.exists(path_bank_excel):
            bank_excel = pd.read_excel(
                path_bank_excel,
                header=headers,
                sheet_name=sheet_name,
            )
        else:
            raise FileNotFoundError(f"Error al encontrar el archivo:{path_bank_excel}") 

        # Transform
        bank_excel['cuit_norm'] = bank_excel[columns['cuit']].apply(self._extract_cuit_bank_excel)
        bank_excel = bank_excel[bank_excel[columns['cuit']].notna()]

        return bank_excel

    def _normalize_date(self, date: str):
        pass
    
    def _normalize_cuit(self, cuit: str):
        return int(cuit.replace("-", "").replace(".", ""))
        

    def _extract_cuit_bank_excel(self, cuit) -> int:
        """
        Metodo que extrae los cuits de la columna "Concepto" del excel del banco macro
        Si una fila de "Concepto" tiene "-" se toma la 2da parte y se extraen los digitos
        Caso contrario se extraen los digitos de todo el string
        *Depende de que el df no tenga valores NA. Fixear esta dependencia para mantener 
        *patron de independencia
        """
        logger.debug(f"Normilize cuit:{cuit}")
        cuit_norm = ''

        if isinstance(cuit, str): 
            # Buscamos el cuit en la segunda parte del string
            if "-" in cuit:
                cuit_norm = cuit.split("-")[1]
                # Extraemos los digitos pero del nuevo string 
                cuit_norm = [char for char in cuit_norm if char.isdigit()]

            # Caso contrario, extraemos los numeros del string original
            else:  
                cuit_norm = [char for char in cuit if char.isdigit()]

            cuit_norm = "".join(cuit_norm)
            if cuit_norm.isdigit():
                cuit_norm = int(cuit_norm)
            else:
                return 0
            logger.debug(f"Result:{cuit_norm}")
        else:
            return 


    def load_comp_bd(self):
        pass 

def test_load_bank(r: Reconciliator):
    logger.debug("="*60)
    # test load bank
    bank_excel = r.load_bank_excel()
    logger.debug("EXCEL BANK")
    logger.debug(f"\n{bank_excel}")
    bank_excel.to_excel(os.path.join(PROJECT_ROOT, "assets/bank/bank_output.xlsx"))

    # test normalize cuit 
    # cuit_examples = pd.read_excel(os.path.join(PROJECT_ROOT, "tests/cuit_tests_data_set.xlsx"))
    # results = []
    #
    # for idx, row in cuit_examples.iterrows():
    #     cuit = str(row["Concepto"])
    #     cuit_norm = r._normalize_cuit_bank_excel(cuit)
    #
    # df = pd.DataFrame(results)
    # df.to_excel(os.path.join(PROJECT_ROOT,'tests/cuit_tests_results.xlsx'))

    logger.debug("="*60)
if __name__ == '__main__':
    r = Reconciliator()
    test_load_bank(r)
   



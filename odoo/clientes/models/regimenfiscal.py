from odoo import fields, models, api
import csv, os

class regimenfiscal(models.Model):
    _name = 'c_regimenfiscal'
    _rec_name = 'descripcion'

    code = fields.Char(string = "Código", required = True)
    descripcion = fields.Char(string = "Descripción", required = True)
    tipo = fields.Char(string = "Tipo de Persona", required = True)

    @api.model
    def _load_csv_data(self):
        module_path = os.path.dirname(os.path.dirname(__file__))
        csv_path = os.path.join(module_path, 'data', 'c_regimenfiscal.csv')
        
        with open(csv_path, 'r') as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if not row['id'].isdigit():  # Asume que id debe ser numérico
                    continue
                
                self.create({
                    'code': row['code'],
                    'descripcion': row['descripcion'],
                    'tipo': row['tipo']
                })
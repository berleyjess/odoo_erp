from odoo import fields, models, api
import csv
import os

class cultivo(models.Model):
    _name='cultivos.cultivo'
    _rec_name='nombre'

    nombre=fields.Char(string="Nombre del cultivo", required=True)

    @api.model
    def _load_csv_data(self):
        module_path = os.path.dirname(os.path.dirname(__file__))
        csv_path = os.path.join(module_path, 'data', 'cultivos.cultivo.csv')
        
        with open(csv_path, 'r') as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if not row['id'].isdigit():  # Asume que id debe ser numérico
                    continue
                
                self.create({
                    'nombre': row['nombre']
                })



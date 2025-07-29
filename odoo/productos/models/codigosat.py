#producto-models-codigosat.py
from odoo import models, fields, api
import csv, os

class codigoproductosat(models.Model):
    _name = 'productos.codigoproductosat'
    _rec_name = 'display_name'
    _rec_names_search = ['code', 'descripcion']
    
    code = fields.Char(string = "Código", required = True, indexed = True)
    descripcion = fields.Char(string = "Descripción", required = True, inexed = True)
    similar = fields.Char(string = "Conicidencias")

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('code', 'descripcion')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.code} - {record.descripcion}"

    def name_get(self):
        return [(record.id, record.display_name) for record in self]

    @api.model
    def _load_csv_data(self):
        module_path = os.path.dirname(os.path.dirname(__file__))
        csv_path = os.path.join(module_path, 'data', 'codigoproductosat.csv')
        
        with open(csv_path, 'r') as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if not row['id'].isdigit():  # Asume que id debe ser numérico
                    continue
                
                self.create({
                    'code': row['code'],
                    'descripcion': row['descripcion'],
                    'similar': row.get('similar', False),
                })
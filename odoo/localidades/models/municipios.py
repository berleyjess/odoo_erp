from odoo import models, fields, api
import csv
import os

class municipio(models.Model):
    _name = 'localidades.municipio'
    _rec_name = 'nombre'
    
    estado = fields.Selection(
        selection = [
            ("AGU", "Aguascalientes"),
            ("BCN", "Baja California Norte"),
            ("BCS", "Baja California Sur"),
            ("CAM", "Campeche"),
            ("CHH", "Chihuahua"),
            ("CHP", "Chiapas"),
            ("COA", "Coahuila"),
            ("COL", "Colima"),
            ("DIF", "Ciudad de México"),
            ("DUR", "Durango"),
            ("GRO", "Guerrero"),
            ("GUA", "Guanajuato"),
            ("HID", "Hidalgo"),
            ("JAL", "Jalisco"),
            ("MEX", "Estado de México"),
            ("MIC", "Michoacán"),
            ("MOR", "Morelos"),
            ("NAY", "Nayarit"),
            ("NLE", "Nuevo León"),
            ("OAX", "Oaxaca"),
            ("PUE", "Puebla"),
            ("QUE", "Queretaro"),
            ("ROO", "Quintana Roo"),
            ("SIN", "Sinaloa"),
            ("SLP", "San Luis Potosí"),
            ("SON", "Sonora"),
            ("TAM", "Tamaulipas"),
            ("TAB", "Tabasco"),
            ("TLA", "Tlaxcala"),
            ("VER", "Veracruz"),
            ("YUC", "Yucatán"),
            ("ZAC", "Zacatecas")
        ], string="Estado", required=True
    )
    nombre = fields.Char(string = "Municipio", required = True)

    @api.model
    def _load_csv_data(self):
        module_path = os.path.dirname(os.path.dirname(__file__))
        csv_path = os.path.join(module_path, 'data', 'localidades.municipio.csv')
        
        with open(csv_path, 'r') as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if not row['id'].isdigit():  # Asume que id debe ser numérico
                    continue
                
                self.create({
                    'estado': row['estado'],
                    'nombre': row['nombre']
                })
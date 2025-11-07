#bodegas/models/bodega.py
from odoo import models, fields
class Bodega(models.Model):
    _name= 'bodegas.bodega'
    _description= "Modelo de Bodega, almacena el catálogo de bodegas."
    _order = "id desc"
    
    empresa_id = fields.Many2one(
        'empresas.empresa', string='Empresa',
        required=True, ondelete='restrict', index=True)
    
    nombre = fields.Char(string="Nombre", required=True, index=True)
    activa = fields.Boolean (string="Activa", required = True, default = True)




# proveedores/models/contacto_ext.py
# Extiende contactos.contacto para colgarlo al rol Proveedor
# Enlaza cada contacto con un proveedor y evita duplicados persona↔proveedor.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ProveedorContactoExt(models.Model):
    """Extensión de contactos: añade proveedor_id y unicidad por persona en ese proveedor."""
    _inherit = 'contactos.contacto'

    proveedor_id = fields.Many2one(
        'proveedores.proveedor', string="Proveedor", ondelete='cascade', index=True
    )
    
# Un contacto (persona) no puede repetirse dentro del mismo proveedor.
    _sql_constraints = [
        ('uniq_proveedor_persona',
         'unique(proveedor_id, persona_id)',
         'Esta persona ya está agregada como contacto de este Proveedor.'),
    ]

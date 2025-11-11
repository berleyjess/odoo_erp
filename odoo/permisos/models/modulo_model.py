# permisos/models/modulo_model.py
from odoo import models, fields

class PermModuloModel(models.Model):
    _name = 'permisos.modulo.model'
    _description = 'Config de modelos por módulo (reglas y access)'

    modulo_id = fields.Many2one('permisos.modulo', required=True, ondelete='cascade')
    model_id  = fields.Many2one('ir.model', required=True, index=True, ondelete='cascade')

    scope = fields.Selection([
        ('global', 'Global'),
        ('empresa', 'Empresa'),
        ('empresa_sucursal', 'Empresa + Sucursal'),
        ('empresa_sucursal_bodega', 'Empresa + Sucursal + Bodega'),
    ], default='empresa', required=True)

    # permisos agregados a nivel grupo del módulo
    perm_read   = fields.Boolean(default=True)
    perm_write  = fields.Boolean(default=False)
    perm_create = fields.Boolean(default=False)
    perm_unlink = fields.Boolean(default=False)

    # mapeo de campos en los modelos de negocio
    empresa_field  = fields.Char(default='empresa')
    sucursal_field = fields.Char(default='sucursal')
    bodega_field   = fields.Char(default='bodega')

# mx_cfdi_engine/models/document.py
from odoo import models, fields
"""
Modelo de relación entre un CFDI y el documento/origen que lo generó.
    - Guarda la empresa emisora, el modelo/ID de origen (account.move, etc.), el tipo de CFDI (I/E/P), el UUID, el estado del ciclo (stamped/canceled) y el XML timbrado.
    - Este registro lo crea el engine en generate_and_stamp() y puede usarse para auditoría, búsquedas por UUID y para recuperar/descargar el XML.
"""
class CfdiDocument(models.Model):
    _name = "mx.cfdi.document"
    _description = "Relación CFDI ↔ Origen"

    empresa_id   = fields.Many2one('empresas.empresa', required=True, index=True)
    origin_model = fields.Char(required=True)
    origin_id    = fields.Integer(required=True)
    tipo         = fields.Selection([('I','Ingreso'),('E','Egreso'),('P','Pago')], required=True)
    uuid         = fields.Char(index=True, copy=False)
    state        = fields.Selection([
        ('to_stamp','Por timbrar'),('stamped','Timbrado'),
        ('to_cancel','Por cancelar'),('canceled','Cancelado')
    ], default='stamped')
    xml          = fields.Binary(attachment=True)
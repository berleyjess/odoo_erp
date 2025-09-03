# mx_cfdi_engine/models/document.py
from odoo import models, fields

class CfdiDocument(models.Model):
    _name = "mx.cfdi.document"
    _description = "Relación CFDI ↔ Origen"

    origin_model = fields.Char(required=True)
    origin_id    = fields.Integer(required=True)
    tipo         = fields.Selection([('I','Ingreso'),('E','Egreso'),('P','Pago')], required=True)
    uuid         = fields.Char(index=True, copy=False)
    state        = fields.Selection([
        ('to_stamp','Por timbrar'),('stamped','Timbrado'),
        ('to_cancel','Por cancelar'),('canceled','Cancelado')
    ], default='stamped')
    xml          = fields.Binary(attachment=True)

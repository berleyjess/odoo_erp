# permisos/models/audit.py
# -*- coding: utf-8 -*-
import json
from odoo import models, fields

class PermAuditLog(models.Model):
    _name = 'permisos.audit.log'
    _description = 'Log de auditoría de seguridad'
    _order = 'id desc'

    when = fields.Datetime(default=lambda self: fields.Datetime.now(), readonly=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)

    # CAMBIA ESTO: de fields.Char(...) -> a fields.Selection(...)
    action = fields.Selection(
        selection=[
            ('create', 'Crear'),
            ('write', 'Escribir'),
            ('unlink', 'Eliminar'),
            ('apply_security', 'Aplicar seguridad'),
        ],
        readonly=True
    )
    model = fields.Char(readonly=True)
    res_id = fields.Integer(readonly=True)
    vals_before = fields.Text()
    vals_after = fields.Text()
    origin = fields.Char()

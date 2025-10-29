from odoo import models, fields

class entry(models.Model):
    _name = 'creditos.entry'

    tipo = fields.Selection(string="Tipo de Registro", selection=[
        ('tech', 'Dictamen técnico'),
        ('check', 'Enviar a Comité'),
        ('confirmed', 'Contrato Aprobado'),
        ('discard', 'Contrato Rechazado'),
        ('draft', 'Enviar a borrador'),
        ('bloked', 'Bloquear contrato'),
        ('open', 'Abrir contrato')
    ], readonly=True)

    msg = fields.Char(string="Observaciones", required = True)

    contrato_id = fields.Many2one('creditos.credito', string="Contrato")

    usuario = fields.Char(string = "Usuario", default = "User")

    fecha = fields.Date(string = "Fecha", readonly = True, default=fields.Date.context_today)
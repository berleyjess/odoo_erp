from odoo import models, fields, api
from datetime import date

class contrato(models.Model):
    _name='Contrato'
    _description='Contratos agrícolas a clientes'

    name = fields.Char(string="Nombre", required=True)
    ciclo = fields.Many2one('ciclo', string="Ciclo", required=True)    
    cultivo = fields.Many2one('cultivo', string="Cultivo")
    aporte = fields.Integer(string="Aporte",required=True)
    f_inicial = fields.Date(string="Fecha de Inicio", required=True)
    f_final = fields.Date(string="Fecha Final", required=True)
    auto = fields.Boolean(string="Cierre automático", required=True, default=True)
    usr_activo = fields.Boolean(string="Ciclo Activo", required=True, default=True)
    activo = fields.Boolean(compute='_ch_activo', stored=False)
    
    @api.depends('f_inicial', 'f_final', 'usr_activo')
    def _ch_activo(self):
        hoy = date.today()
        for record in self:
            if record.f_inicial and record.f_final:
                en_rango = record.f_inicial <= hoy <= record.f_final
            else:
                en_rango = False
            record.activo = en_rango or record.usr_activo


    @api.onchange('ciclo')
    def _onchange_ciclo(self):
        for record in self:
            if record.ciclo:
                record.f_inicial = record.ciclo.f_inicio
                record.f_final = record.ciclo.f_final

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date

class contrato(models.Model):
    _name='contratos.contrato'
    _description='Contratos agrícolas a clientes'
    _rec_name = 'display_name'

    tipocredito = fields.Selection(
        selection = [
            ("0", "AVIO"),
            ("1", "Comercial"),
            ("2", "A días")
        ], string = "Tipo de crédito", default = "0", required = True
    )
    ciclo = fields.Many2one('ciclos.ciclo', string="Ciclo", required=True)    
    cultivo = fields.Many2one('cultivos.cultivo', string="Cultivo")
    aporte = fields.Integer(string="Aporte por Hectárea", required=True)

    limiteinsumos = fields.One2many(
        'contratos.limiteinsumo_ext', 'contrato_id', string="Límites de Insumos")
    
    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super(contrato, self).fields_get(allfields=allfields, attributes=attributes)
        context = self.env.context
        tipocredito = context.get('default_tipocredito') or context.get('tipocredito')
        if 'aporte' in res:
            if tipocredito == "2":
                res['aporte']['string'] = "Aporte Total"
            else:
                res['aporte']['string'] = "Aporte por Hectárea"
        return res

    @api.constrains('tipocredito', 'cultivo')
    def _check_cultivo_required(self):
        for record in self:
            if record.tipocredito != "2" and not record.cultivo:
                raise ValidationError("El campo 'Cultivo' es obligatorio.")

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('ciclo', 'cultivo')
    def _compute_display_name(self):
        for record in self:
            tipocredito_label = dict(self._fields['estado'].selection).get(record.estado)
            record.display_name = f"{tipocredito_label} {record.ciclo} {record.cultivo}"


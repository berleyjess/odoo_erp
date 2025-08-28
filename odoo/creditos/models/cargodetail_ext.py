from odoo import models, fields, api
from datetime import date

class cargodetail_ext(models.Model):
    _inherit = 'cargosdetail.cargodetail'

    fecha = fields.Date(string = "Fecha", default = date.today(), store = True)
    credito_id = fields.Many2one('creditos.credito', "Crédito", store = True)
    importe = fields.Float(string = "Importe", readonly = True, compute = '_compute_importe', store = True)

    @api.depends('cargo', 'costo', 'porcentaje')#, 'credito_id.saldoejercido')
    def _compute_importe(self):
        for record in self:
            if record.cargo.tipo == '0':  # Costo por superficie
                record.importe = record.costo * record.credito_id.superficie
           # elif record.cargo.tipo == '1':  # Porcentaje x Saldo Ejercido
           #     record.importe = record.porcentaje * record.saldoejercido
            elif record.cargo.tipo == '2':  # Monto Único
                record.importe = record.costo
            
            record.importe = record.importe + (record.importe * record.iva) + (record.importe * record.ieps)
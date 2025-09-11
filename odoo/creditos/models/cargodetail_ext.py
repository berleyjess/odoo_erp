from odoo import models, fields, api
from datetime import date
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

class cargodetail_ext(models.Model):
    _inherit = 'cargosdetail.cargodetail'

    fecha = fields.Date(string = "Fecha", default = date.today(), store = True)
    credito_id = fields.Many2one('creditos.credito', "Crédito", store = True)
    importe = fields.Float(string = "Importe", readonly = True, compute = '_compute_importe', store = True)

    montocredito = fields.Float(string = "Monto del crédito", related='credito_id.monto', store = True)

    @api.depends('cargo', 'costo', 'porcentaje', 'credito_id.monto')#, 'credito_id.saldoejercido')
    def _compute_importe(self):
        for record in self:
            if record.tipocargo == '0':  # Costo por superficie
                record.importe = record.costo * record.credito_id.superficie
            elif record.tipocargo == '1':  # Porcentaje x Monto del Crédito
                record.importe = record.montocredito * record.porcentaje
                _logger.info(f"*-*-*-* CÁLCULO DE IMPORTE PORCENTAJE X MONTO DEL CRÉDITO: {record.importe} = {record.montocredito} * {record.porcentaje} *-*-*-*")
            elif record.tipocargo == '2':  # Monto Único
                record.importe = record.costo

            # elif record.cargo.tipo == '3':  # Porcentaje x Saldo Ejercido
            #     record.importe = record.porcentaje * record.saldoejercido

            record.importe = record.importe + (record.importe * record.iva) + (record.importe * record.ieps)

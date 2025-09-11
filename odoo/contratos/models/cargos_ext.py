from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class cargos_ext(models.Model):
    _inherit = 'cargosdetail.cargodetail'

    contrato_id = fields.Many2one('contratos.contrato', string = "Contrato")
    cargocontrato = fields.Boolean(string = "Cargo del contrato", default = False, store = True)

    @api.constrains('cargo')
    def _check_superficie_required(self):
        for record in self:
            if record.contrato_id:
                if record.cargo.tipo == '0': # Costo por superficie
                    if not record.costo:
                        raise ValidationError("Debe capturar un costo por Hectárea.")
                elif record.cargo.tipo == '1':  # Saldo del crédito
                    if not record.porcentaje or not (record.porcentaje > 0 and record.porcentaje <= 1):
                        raise ValidationError("Debe capturar un porcentaje válido para el cálculo del cargo.")
                elif record.cargo.tipo == '2':  # Monto único
                    if not record.costo:
                        raise ValidationError("Debe capturar el monto del cargo.")
                elif record.cargo.tipo == '3':  # Saldo ejercido
                    if not record.porcentaje or not (record.porcentaje > 0 and record.porcentaje <= 1):
                        raise ValidationError("Debe capturar un porcentaje válido para el cálculo del cargo.")

    def _calc_importe(self, saldoejercito):    
        for record in self:
            if record.tipo == '3':
                record.importe = record.porcentaje * saldoejercito

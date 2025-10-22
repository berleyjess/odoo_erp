from odoo import models, fields, api
from datetime import date
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

class cargodetail_ext(models.Model):
    _inherit = 'cargosdetail.cargodetail'

    fecha = fields.Date(string = "Fecha", default = date.today(), store = True)
    importe = fields.Float(string = "Importe", readonly = True, compute = '_compute_importe', store = True)
    saldo = fields.Float(string = "Saldo", readonly = True, compute = '_compute_saldo', store = True, default = 0.0)
    pagos = fields.Float(string = "Pagos", readonly = True, compute = '_compute_importe', store = True, default = 0.0)
    credito_id = fields.Many2one('creditos.credito', string = "Crédito", store = True)
    total = fields.Float(string = "Total", readonly = True, compute = '_compute_total', store = True)
    
    @api.depends('cargo', 'costo', 'porcentaje', 'credito_id.monto')#, 'credito_id.saldoejercido')
    def _compute_total(self):
        for record in self:
            if record.tipocargo == '0':  # Costo por superficie
                record.total = record.costo * record.credito_id.superficie
            elif record.tipocargo == '1':  # Porcentaje x Monto del Crédito
                record.total = record.credito_id.monto * record.porcentaje
            elif record.tipocargo == '2':  # Monto Único
                record.total = record.costo

            # elif record.cargo.tipo == '3':  # Porcentaje x Saldo Ejercido
            #     record.importe = record.porcentaje * record.saldoejercido

    @api.depends('total', 'iva', 'ieps')
    def _compute_importe(self):
        for record in self:
            record.importe = record.total + (record.total * record.iva) + (record.total * record.ieps)
            record.credito_id.recalc_cargos()

    @api.depends('importe', 'pagos')
    def _compute_saldo(self):
        for record in self:
            record.saldo = record.importe - record.pagos

    @api.model
    def create(self, vals):
        if 'folio' not in vals or vals['folio'] == 'Nuevo':
            count = self.env['cargosdetail.cargodetail'].search_count([
                ('credito_id', '=', vals.get('credito_id')),
                ('cargocontrato', '=', False)
            ])

            vals['folio'] = 'CA#' + str(10000 + count + 1)[-4:]
        return super(cargodetail_ext, self).create(vals)
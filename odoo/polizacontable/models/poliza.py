from odoo import models, fields, api

class poliza(models.Model):
    _name = 'polizacontable.poliza'
    _rec_name = 'descripcion'

    folio = fields.Char(string = "Folio", required = True, store = True)
    fecha = fields.Date(string = "Fecha", default = fields.Date.today, store = True)
    descripcion = fields.Char(string = "Descripción", required = True)
    referencia = fields.Char(string = "Referencia", store = True)

    movimientos = fields.One2many('movcuentas.movimientos', 'poliza_id', string = "Movimientos", store = True)

    saldo = fields.Float(string = "Saldo", readonly = True, default = 0, store = True)

    activa = fields.Boolean(string = "Activo", required = True, default = True, store = True)

    @api.depends('movimientos')
    def calc_saldo(self):
        for record in self:
            cargos = sum(m.cargo for m in record.movimientos)
            abonos = sum(m.abono for m in record.movimientos)
            record.saldo = cargos - abonos
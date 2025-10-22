from odoo import models, fields, api

class movcuentas(models.Model):
    _name = 'movcuentas.movimientos'
    _rec_name = 'descripcion'

    fecha = fields.Date(string = "Fecha", default = fields.Date.today, store = True)
    descripcion = fields.Char(string = "Descripción", required = True)
    cargo = fields.Float(string = "Cargo", store = True)
    abono = fields.Float(string = "Abono", store = True)

    cuenta_id = fields.Many2one('contabilidad.contabilidad', string = "Cuenta Contable", store = True)
    poliza_id = fields.Many2one('polizacontable.poliza', string = "Póliza", store = True)

    activo = fields.Boolean(string = "Activo", required = True, default = True, store = True)

    def toggle_active(self):
        for record in self:
            #record.activo = not record.activo
            if record.cuenta_id:
                record.cuenta_id.calc_movs()

    
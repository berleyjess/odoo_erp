from odoo import models, fields, api

class contabilidad(models.Model):
    _name = 'contabilidad.contabilidad'
    _rec_name = 'descripcion'

    saldo = fields.Float(string = "Saldo", readonly = True, default = 0.0, store = True)
    descripcion = fields.Char(string = "Descripción", required = True)
    naturaleza = fields.Selection(string = "Naturaleza", selection = [
        ('0', "Deudora"),
        ('1', "Acreedora")
    ], default='0', required=True, store = True)

    codigo = fields.Char(string="Código", required = True, store = True)

    abierta = fields.Boolean(string = "Cuenta Abierta", required = True, default = True, store = True)
    cuenta_padre = fields.Many2one('contabilidad.contabilidad', string = "Cuenta Padre", store = True)
    cuenta_hija = fields.One2many('contabilidad.contabilidad', 'cuenta_padre', string = "Cuentas Hija", store = True)

    movimientos = fields.One2many('movcuentas.movimientos', 'cuenta_id', string = "Movimientos", store = True)

    def calc_movs(self):
        for record in self:
            cargos = sum(m.cargo for m in record.movimientos)
            abonos = sum(m.abono for m in record.movimientos)
            if record.naturaleza == '0':  # Deudora
                record.saldo = cargos - abonos
            else:  # Acreedora
                record.saldo = abonos - cargos
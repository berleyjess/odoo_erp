from odoo import models, fields, api

class cargodetail(models.Model):
    _name = 'cargosdetail.cargodetail'

    fecha = fields.Date(string = "Fecha", default=fields.Date.context_today, readonly = True)
    cargo = fields.Many2one('cargos.cargo', string = "Concepto", required = True, ondelete='cascade')
    contrato_id = fields.Many2one('contratos.contrato', string = "Contrato")
    costo = fields.Float(string = "Costo", default = 0.0)
    porcentaje = fields.Float(string ="Porcentaje", default = 0.0)
    cargocontrato = fields.Boolean(string = "Cargo de contrato", default = False, readonly = True)
    tipocargo = fields.Selection(
        selection = [
            ('0', "Costo x superficie"),
            ('1', "Porcentaje x el monto del crédito"),
            ('2', "Monto único"),
            ('3', "Porcentaje x el saldo ejercido")
        ],
        store = True, related='cargo.tipo', string="Tipo", readonly = True
    )

    descripcion = fields.Char(string = "Descripción", related='cargo.descripcion')

    iva = fields.Float(string = "Iva %", related='cargo.iva')
    ieps = fields.Float(string = "Ieps %", related='cargo.ieps')
    importe = fields.Float(string = "Importe", readonly = True, store = True)
    total = fields.Float(string = "Total", readonly = True, store = True)
    saldo = fields.Float(string= "Saldo", readonly = True, store = True)
    
    def action_eliminar_cargo(self):
        for rec in self:
            cargos_a_eliminar = rec.filtered(lambda c: not c.cargocontrato)
            if cargos_a_eliminar:
                cargos_a_eliminar.unlink()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    




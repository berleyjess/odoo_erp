# wizards/add_from_charges.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class WizAddCharges(models.TransientModel):
    _name = 'facturas.wiz.add.charges'
    _description = 'Agregar cargos facturables'

    factura_id = fields.Many2one('facturas.factura', required=True)
    charge_ids = fields.Many2many('cargosdetail.cargodetail', string='Cargos facturables')

    def action_add(self):
        self.ensure_one()
        fac = self.factura_id

        for c in self.charge_ids:
            if not c.cargo or not c.cargo.facturable:
                continue

            fac.line_ids.create({
                'factura_id': fac.id,
                'empresa_id': fac.empresa_id.id,
                'cliente_id': fac.cliente_id.id if fac.cliente_id else False,
                'line_type': 'charge',
                'source_model': 'cargosdetail.cargodetail',
                'source_id': c.id,
                'producto_id': c.cargo.producto_id.id,
                'descripcion': c.descripcion or c.cargo.concepto,
                'cantidad': 1.0,
                'precio': c.importe or c.costo or 0.0,
                'iva_ratio': c.iva or 0.0,
                'ieps_ratio': c.ieps or 0.0,
            })

        return {'type': 'ir.actions.act_window_close'}

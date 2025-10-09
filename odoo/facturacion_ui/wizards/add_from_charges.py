# wizards/add_from_charges.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class WizAddCharges(models.TransientModel):
    _name = 'facturas.wiz.add.charges'
    _description = 'Agregar cargos facturables'

    factura_id = fields.Many2one('facturas.factura', required=True)
    charge_ids = fields.Many2many('cargosdetail.cargodetail', string='Cargos facturables')

    @api.onchange('factura_id')
    def _onchange_factura_id(self):
        if not self.factura_id:
            return

        # cargos ya facturados (aparecen como source en alguna línea)
        used_charge_ids = self.env['facturas.factura.line'].sudo().search([
            ('source_model', '=', 'cargosdetail.cargodetail'),
        ]).mapped('source_id')

        domain = [
            ('id', 'not in', used_charge_ids),   # ⬅️ oculta los ya facturados
            ('cargo.facturable', '=', True),
        ]
        # (opcional) si tus cargos tienen empresa/sucursal, puedes agregar:
        # if self.factura_id.empresa_id:
        #     domain.append(('empresa_id', '=', self.factura_id.empresa_id.id))
        # if self.factura_id.sucursal_id:
        #     domain.append(('sucursal_id', '=', self.factura_id.sucursal_id.id))

        return {'domain': {'charge_ids': domain}}


    def action_add(self):
        self.ensure_one()
        fac = self.factura_id

        created_lines, bloqueados = [], []

        for c in self.charge_ids:
            # Considera “bloqueado” si no es facturable o si el cargo (o su detalle) reporta full
            ya_full = (getattr(c, 'invoice_status', '') == 'full' or
                       getattr(getattr(c, 'cargo', False), 'invoice_status', '') == 'full')
            if not (c.cargo and c.cargo.facturable) or ya_full:
                bloqueados.append(c)
                continue

            new_line = fac.line_ids.create({
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
            created_lines.append(new_line)
        
        if not created_lines:
            if bloqueados:
                nombres = [ (r.display_name or _("Cargo #%s") % r.id) for r in bloqueados ]
                detalle = "\n- " + "\n- ".join(map(str, nombres))
                raise UserError(_("No puedes agregar cargos ya facturados o no facturables:%s") % detalle)
            raise ValidationError(_('No se agregó ningún cargo.'))

        return {'type': 'ir.actions.act_window_close'}
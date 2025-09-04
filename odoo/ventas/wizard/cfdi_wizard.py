from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ..services.invoicing_bridge import create_invoice_from_sale


class VentasCfdiWizard(models.TransientModel):
    _name = 'ventas.cfdi.wizard'
    _description = 'Wizard CFDI desde Venta'

    # Contexto
    sale_id = fields.Many2one('ventas.venta', string="Venta", required=True)

    # Datos fiscales
    tipo_comprobante = fields.Selection([
        ('I', 'Ingreso'), ('E', 'Egreso'), ('P', 'Pago')
    ], string="Tipo de CFDI", required=True, default='I')

    uso_cfdi = fields.Selection([
        ('G01', 'Adquisición de mercancías'),
        ('G03', 'Gastos en general'),
        ('CP01', 'Pagos'),
    ], string="Uso CFDI", required=True)

    metodo_pago = fields.Selection([('PUE', 'Pago en una sola exhibición'),
                                    ('PPD', 'Pago en parcialidades o diferido')],
                                   string="Método de Pago")
    forma_pago = fields.Selection([
        ('01', 'Efectivo'), ('02', 'Cheque nominativo'), ('03', 'Transferencia'),
        ('04', 'Tarjeta de crédito'), ('28', 'Tarjeta de débito'), ('30', 'Aplicación de anticipos'),
        ('99', 'Por definir')
    ], string="Forma de Pago")

    relacion_tipo = fields.Selection([
        ('01', 'Nota de crédito de los documentos relacionados'),
        ('02', 'Nota de débito de los documentos relacionados'),
        ('03', 'Devolución de mercancía sobre facturas o traslados previos'),
        ('04', 'Sustitución de los CFDI previos'),
        ('05', 'Traslados de mercancias facturados previamente'),
        ('06', 'Factura generada por los traslados previos'),
        ('07', 'CFDI por aplicación de anticipo'),
    ], string="Tipo de relación")

    relacion_ventas_ids = fields.Many2many(
        'ventas.venta', 'wiz_cfdi_rel_m2m', 'wiz_id', 'venta_id',
        string="CFDIs/ventas a relacionar",
        help="Para Egreso (notas de crédito/devoluciones) o Pago (PPD)."
    )

    # Helpers visuales
    show_pago = fields.Boolean(compute='_compute_visibility')
    show_rel = fields.Boolean(compute='_compute_visibility')

    @api.depends('tipo_comprobante')
    def _compute_visibility(self):
        for w in self:
            w.show_pago = (w.tipo_comprobante == 'I')
            w.show_rel = (w.tipo_comprobante in ('E', 'P'))

    @api.onchange('tipo_comprobante')
    def _onchange_tipo(self):
        if self.tipo_comprobante == 'P':
            self.uso_cfdi = 'CP01'
            self.metodo_pago = False
            self.forma_pago = False
            self.relacion_tipo = False
        elif self.tipo_comprobante == 'I':
            self.uso_cfdi = self.uso_cfdi or 'G03'
            self.metodo_pago = self.metodo_pago or self._context.get('default_metodo_pago') or 'PPD'
            self.forma_pago = (self.metodo_pago == 'PUE') and (self.forma_pago or '01') or False
            self.relacion_tipo = False
            self.relacion_ventas_ids = [(5, 0, 0)]
        elif self.tipo_comprobante == 'E':
            self.uso_cfdi = self.uso_cfdi or 'G03'
            self.metodo_pago = self._context.get('default_metodo_pago') or 'PPD'
            self.forma_pago = (self.metodo_pago == 'PUE') and (self.forma_pago or '01') or False
            self.relacion_tipo = self.relacion_tipo or '01'

    @api.onchange('metodo_pago')
    def _onchange_metodo(self):
        if self.tipo_comprobante in ('I', 'E'):
            self.forma_pago = False if self.metodo_pago == 'PPD' else (self.forma_pago or '01')

    def _validate_business(self):
        self.ensure_one()
        if self.tipo_comprobante == 'E':
            if not self.relacion_tipo or not self.relacion_ventas_ids:
                raise ValidationError(_("Para Egreso debes escoger Tipo de relación y al menos un CFDI/venta a relacionar."))
        if self.tipo_comprobante == 'P':
            if not self.relacion_ventas_ids:
                raise ValidationError(_("Para el Recibo de pago (P) selecciona la(s) venta(s)/factura(s) PPD a pagar."))
            bad = self.relacion_ventas_ids.filtered(lambda v: v.metododepago != 'PPD')
            if bad:
                raise ValidationError(_("Solo puedes relacionar comprobantes PPD en el Recibo de pago (P)."))

    def action_confirm(self):
        self.ensure_one()
        self._validate_business()

        sale = self.sale_id.sudo()
        sale.write({
            'cfdi_tipo': self.tipo_comprobante,
            'cfdi_relacion_tipo': self.relacion_tipo or False,
            'cfdi_relacion_ventas_ids': [(6, 0, self.relacion_ventas_ids.ids)] if self.relacion_ventas_ids else [(5, 0, 0)],
            'cfdi_state': 'to_stamp',
        })

        if self.tipo_comprobante in ('I', 'E'):
            # Para E (nota) relacionamos los UUID de las facturas de ventas seleccionadas
            related_moves = self.relacion_ventas_ids.mapped('move_id') if self.tipo_comprobante == 'E' else None
            move = create_invoice_from_sale(
                sale,
                tipo=self.tipo_comprobante,
                uso_cfdi=self.uso_cfdi,
                metodo=self.metodo_pago,
                forma=self.forma_pago,
                relacion_tipo=self.relacion_tipo,
                relacion_moves=related_moves,
            )
            move.action_post()
            vals = {'state': 'invoiced'}
            if hasattr(sale, 'move_id'):
                vals['move_id'] = move.id
            uuid_val = getattr(move, 'l10n_mx_edi_cfdi_uuid', False) or False
            if uuid_val:
                vals.update({'cfdi_uuid': uuid_val, 'cfdi_state': 'stamped'})
            sale.write(vals)

            # Timbrar vía engine/proveedor seleccionado (SW u otro)
            conceptos = sale._to_cfdi_conceptos()
            partner_id = move.partner_id.id
            stamped = self.env['mx.cfdi.engine'].generate_and_stamp(
                origin_model='ventas.venta',
                origin_id=sale.id,
                tipo=self.tipo_comprobante,
                receptor_id=partner_id,
                uso_cfdi=self.uso_cfdi,
                metodo=self.metodo_pago,
                forma=self.forma_pago,
                relacion_tipo=self.relacion_tipo,
                conceptos=conceptos,
            )
            if stamped and stamped.get('uuid'):
                sale.write({'cfdi_uuid': stamped['uuid'], 'cfdi_state': 'stamped'})
                # duplicar adjunto a la factura para visibilidad
                att = self.env['ir.attachment'].browse(stamped.get('attachment_id'))
                if att and move:
                    self.env['ir.attachment'].sudo().create({
                        'name': att.name,
                        'res_model': 'account.move',
                        'res_id': move.id,
                        'type': 'binary',
                        'datas': att.datas,
                        'mimetype': att.mimetype,
                        'description': att.description,
                    })
            return {'type': 'ir.actions.act_window_close'}

        if self.tipo_comprobante == 'P':
            invoices = self.relacion_ventas_ids.mapped('move_id').filtered(lambda m: m and m.state == 'posted')
            if not invoices:
                raise ValidationError(_("No hay facturas posteadas vinculadas a las ventas seleccionadas."))
            journal = self.env['account.journal'].search([('type', 'in', ('bank', 'cash')), ('company_id', '=', self.env.company.id)], limit=1)
            if not journal:
                raise UserError(_("Configura un diario de Banco o Caja para registrar pagos."))
            for inv in invoices:
                ctx = {'active_model': 'account.move', 'active_ids': [inv.id], 'active_id': inv.id}
                reg = self.env['account.payment.register'].with_context(ctx).create({
                    'payment_date': fields.Date.context_today(self),
                    'journal_id': journal.id,
                    'amount': inv.amount_residual,
                })
                reg.action_create_payments()
            # Generar CFDI tipo P (complemento) vía engine SW
            doctos = []
            for inv in invoices:
                uuid = getattr(inv, 'l10n_mx_edi_cfdi_uuid', False) or ''
                if uuid:
                    total = inv.amount_total
                    doctos.append({
                        'uuid': uuid,
                        'moneda_dr': inv.currency_id.name or 'MXN',
                        'num_parcialidad': '1',
                        'imp_saldo_ant': f"{total:.2f}",
                        'imp_pagado': f"{total:.2f}",
                        'imp_saldo_insoluto': '0.00',
                    })
            extras = {
                'pagos': {
                    'fecha_pago': fields.Datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                    'forma_pago_p': self.forma_pago or '03',
                    'moneda_p': 'MXN',
                    'monto': sum(inv.amount_total for inv in invoices),
                    'doctos': doctos,
                }
            }
            stamped = self.env['mx.cfdi.engine'].generate_and_stamp(
                origin_model='ventas.venta',
                origin_id=sale.id,
                tipo='P',
                receptor_id=invoices[0].partner_id.id,
                uso_cfdi='CP01',
                metodo=False,
                forma=False,
                extras=extras,
            )
            if stamped and stamped.get('uuid'):
                sale.write({'cfdi_uuid': stamped['uuid'], 'cfdi_state': 'stamped'})
            sale.write({'state': 'invoiced'})
            return {'type': 'ir.actions.act_window_close'}

        return {'type': 'ir.actions.act_window_close'}

# ventas/wizard/cfdi_wizard.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class VentasCfdiWizard(models.TransientModel):
    _name = 'ventas.cfdi.wizard'
    _description = 'Wizard CFDI desde Venta'

    # Contexto
    sale_id = fields.Many2one('ventas.venta', string="Venta", required=True)

    # Datos fiscales
    tipo_comprobante = fields.Selection([
        ('I','Ingreso'), ('E','Egreso'), ('P','Pago')
    ], string="Tipo de CFDI", required=True, default='I')

    uso_cfdi = fields.Selection([
        # pon aquí las claves que uses; idealmente cargadas de catálogo SAT:
        ('G01', 'Adquisición de mercancías'),
        ('G03', 'Gastos en general'),
        ('CP01','Pagos'),
        # ...
    ], string="Uso CFDI", required=True)

    metodo_pago = fields.Selection([('PUE','Pago en una sola exhibición'),
                                    ('PPD','Pago en parcialidades o diferido')],
                                   string="Método de Pago")
    forma_pago = fields.Selection([
        ('01','Efectivo'), ('02','Cheque nominativo'), ('03','Transferencia'),
        ('04','Tarjeta de crédito'), ('28','Tarjeta de débito'), ('30','Aplicación de anticipos'),
        ('99','Por definir')
    ], string="Forma de Pago")

    relacion_tipo = fields.Selection([
        ('01','Nota de crédito de los documentos relacionados'),
        ('02','Nota de débito de los documentos relacionados'),
        ('03','Devolución de mercancía sobre facturas o traslados previos'),
        ('04','Sustitución de los CFDI previos'),
        ('05','Traslados de mercancias facturados previamente'),
        ('06','Factura generada por los traslados previos'),
        ('07','CFDI por aplicación de anticipo'),
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
            w.show_rel = (w.tipo_comprobante in ('E','P'))

    @api.onchange('tipo_comprobante')
    def _onchange_tipo(self):
        # Defaults por tipo
        if self.tipo_comprobante == 'P':
            self.uso_cfdi = 'CP01'         # obligatorio en recibos de pago
            self.metodo_pago = False       # no aplica en "P"
            self.forma_pago = False        # no aplica en "P"
            self.relacion_tipo = False     # relación va en complemento, aquí solo referenciaremos facturas
        elif self.tipo_comprobante == 'I':
            self.uso_cfdi = self.uso_cfdi or 'G03'
            self.metodo_pago = self.metodo_pago or self._context.get('default_metodo_pago') or 'PPD'
            self.forma_pago = (self.metodo_pago == 'PUE') and (self.forma_pago or '01') or False
            self.relacion_tipo = False
            self.relacion_ventas_ids = [(5,0,0)]
        elif self.tipo_comprobante == 'E':
            self.uso_cfdi = self.uso_cfdi or 'G03'
            self.metodo_pago = self._context.get('default_metodo_pago') or 'PPD'
            self.forma_pago = (self.metodo_pago == 'PUE') and (self.forma_pago or '01') or False
            self.relacion_tipo = self.relacion_tipo or '01'  # común: nota de crédito

    @api.onchange('metodo_pago')
    def _onchange_metodo(self):
        if self.tipo_comprobante in ('I','E'):
            self.forma_pago = False if self.metodo_pago == 'PPD' else (self.forma_pago or '01')

    # Validaciones de negocio (SAT)
    def _validate_business(self):
        self.ensure_one()
        if self.tipo_comprobante == 'E':
            if not self.relacion_tipo or not self.relacion_ventas_ids:
                raise ValidationError(_("Para Egreso debes escoger Tipo de relación y al menos un CFDI/venta a relacionar."))
        if self.tipo_comprobante == 'P':
            # Solo permite relacionar ventas con método PPD (y normalmente ya timbradas)
            if not self.relacion_ventas_ids:
                raise ValidationError(_("Para el Recibo de pago (P) selecciona la(s) venta(s)/factura(s) PPD a pagar."))
            bad = self.relacion_ventas_ids.filtered(lambda v: v.metododepago != 'PPD')
            if bad:
                raise ValidationError(_("Solo puedes relacionar comprobantes PPD en el Recibo de pago (P)."))

    # Click en "Continuar"
    def action_confirm(self):
        self.ensure_one()
        self._validate_business()

        sale = self.sale_id.sudo()

        # Guarda metadatos mínimos en la venta
        sale.write({
            'cfdi_tipo': self.tipo_comprobante,
            'cfdi_relacion_tipo': self.relacion_tipo or False,
            'cfdi_relacion_ventas_ids': [(6, 0, self.relacion_ventas_ids.ids)] if self.relacion_ventas_ids else [(5,0,0)],
            'cfdi_state': 'to_stamp',
        })

    # *** NUEVO: preparar conceptos e info de receptor ***
        conceptos = sale._to_cfdi_conceptos()  # añadir método abajo
    # Ideal: tu modelo clientes.cliente tenga partner_id (res.partner)
        partner_id = getattr(sale.cliente, 'partner_id', False) and sale.cliente.partner_id.id or False

    # Relacionados (para E y P). Aquí solo pasamos los UUID si existen.
        rel_moves = []
        if self.tipo_comprobante in ('E', 'P'):
            for v in self.relacion_ventas_ids:
                if v.cfdi_uuid:
                    rel_moves.append({'uuid': v.cfdi_uuid})

        stamped = self.env['mx.cfdi.engine'].with_context(wizard=True).generate_and_stamp(
            origin_model='ventas.venta',
            origin_id=sale.id,
            tipo=self.tipo_comprobante,
            receptor_id=self.sale_id.cliente.id,   # ajusta al id correcto (tu modelo de clientes)
            uso_cfdi=self.uso_cfdi,
            metodo=self.metodo_pago,
            forma=self.forma_pago,
            relacion_tipo=self.relacion_tipo,
            relacion_moves=None,
            conceptos=[{"name": "Venta", "qty": 1, "price": sale.total}],  # demo
        )



        if stamped and stamped.get('uuid'):
            sale.write({'cfdi_uuid': stamped['uuid'], 'cfdi_state': 'stamped', 'state': 'invoiced'})
        return {'type': 'ir.actions.act_window_close'}


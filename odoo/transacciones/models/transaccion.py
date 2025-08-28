#transacciones/models/transaccion.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date

class Transaccion(models.Model):
    _name = 'transacciones.transaccion'
    _description = 'Detalles/Conceptos de Compra/Venta/Traspasos/Devoluciones'

    fecha = fields.Date(string="Fecha", default=lambda self: fields.Date.context_today(self), store=True)


    # Para ventas: origen = sucursal de la venta; destino se usa en traspasos
    sucursal_id = fields.Many2one('sucursales.sucursal', string="Origen")
    sucursal_d_id = fields.Many2one('sucursales.sucursal', string="Destino")

    producto_id = fields.Many2one('productos.producto', string="Producto", required=True, index=True)
    referencia = fields.Char(string="Referencia", store=True)
    cantidad = fields.Float(string="Cantidad", default=0.0)
    precio = fields.Float(string="Precio", default=0.0, required=True)

    iva = fields.Float(string="Iva %", readonly=True, store=True, compute='_calc_montos')
    ieps = fields.Float(string="Ieps %", readonly=True, store=True, compute='_calc_montos')
    iva_amount = fields.Float(string="Iva", readonly=True, store=True, compute='_calc_montos')
    ieps_amount = fields.Float(string="Ieps", readonly=True, store=True, compute='_calc_montos')
    subtotal = fields.Float(string="Subtotal", readonly=True, store=True, compute='_calc_montos')
    importe = fields.Float(string="Importe", readonly=True, store=True, compute='_calc_montos')

    stock = fields.Selection(string="Tipo", default='0', readonly=True, selection=[
        ('0', "Sin efecto"),
        ('1', "Entrada"),
        ('2', "Salida"),
    ], compute='_stock_tipo', store=True)

    tipo = fields.Selection(string="Tipo de Transacción", selection=[
        ('0', "Compra"),         # Entrada
        ('1', "Venta"),          # Salida
        ('2', "Recepción"),      # Entrada
        ('3', "Envío"),          # Salida
        ('4', "Producción"),     # Entrada
        ('5', "Costo"),          # Salida
        ('6', "Dev de Cliente"), # Entrada
        ('7', "Dev a Proveedor"),# Salida
        ('8', "Excedente"),      # Entrada
        ('9', "Pérdida"),        # Salida
        ('10', "Preventa"),      # Sin efecto
    ], default='1', store=True)

    # Enlace con venta (One2many en ventas.venta -> venta_id aquí)
    venta_id = fields.Many2one('ventas.venta', string="Venta", ondelete='cascade', index=True)

    @api.depends('producto_id', 'cantidad', 'precio')
    def _calc_montos(self):
        for i in self:
            if i.producto_id:
                i.iva = i.producto_id.iva
                i.ieps = i.producto_id.ieps
            sub = (i.cantidad or 0.0) * (i.precio or 0.0)
            iva_amt = (i.iva or 0.0) * sub
            ieps_amt = (i.ieps or 0.0) * sub
            i.subtotal = sub
            i.iva_amount = iva_amt
            i.ieps_amount = ieps_amt
            i.importe = sub + iva_amt + ieps_amt

    @api.depends('tipo')
    def _stock_tipo(self):
        ENTRADA = {'0', '2', '4', '6', '8'}
        for i in self:
            if i.tipo == '10':
                i.stock = '0'
            elif i.tipo in ENTRADA:
                i.stock = '1'
            else:
                i.stock = '2'

    @api.onchange('venta_id')
    def _onchange_venta_id(self):
        for i in self:
            if i.venta_id and i.venta_id.sucursal_id:
                i.sucursal_id = i.venta_id.sucursal_id

    @api.constrains('venta_id', 'sucursal_id')
    def _constrain_sucursal_venta(self):
        for i in self:
            if i.venta_id and i.venta_id.sucursal_id and i.sucursal_id and i.venta_id.sucursal_id != i.sucursal_id:
                raise ValidationError(_("La sucursal de la línea debe coincidir con la sucursal de la venta."))

    @api.onchange('producto_id', 'venta_id', 'venta_id.metododepago')
    def _onchange_precio_por_metodo(self):
        for line in self:
            if not line.producto_id:
                continue
            metodo = (line.venta_id.metododepago or 'PPD') if line.venta_id else 'PPD'
            line.precio = line.producto_id.contado if metodo == 'PUE' else line.producto_id.credito

    @api.model
    def create(self, vals):
        # set precio por defecto si viene vacío
        if not vals.get('precio') and vals.get('producto_id'):
            venta = self.env['ventas.venta'].browse(vals.get('venta_id')) if vals.get('venta_id') else False
            metodo = venta.metododepago if venta and venta.metododepago else 'PPD'
            prod = self.env['productos.producto'].browse(vals['producto_id'])
            vals['precio'] = prod.contado if metodo == 'PUE' else prod.credito
        return super().create(vals)

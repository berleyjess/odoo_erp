from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date

class venta(models.Model):
    _name = 'venta'
    _description = 'Venta de artículos'
    
    codigo = fields.Char(string="Código", required = True)
    cliente = fields.Many2one('cliente', string="Cliente", required = True)
    contrato = fields.Many2one('contrato', string="Contrato")
    observaciones = fields.Char(string = "Observaciones", size=32)
    fecha = fields.Date(string="Fecha", default=lambda self: date.today())
    detalle = fields.One2many('ventadetalle', 'ventaf', string="Ventas")
    #vendedor = fields.Many2one('vendedor', string="Vendedor", required = True)
    #sucursal = fields.Many2one('sucursal', string="Sucursal", required = True)
    #empresa = fields.Many2one('empresa', string="Empresa", readonly = True)
    solicita = fields.Char(max_length=30, string="Solicita", required=True)
    importe = fields.Float(string="Importe", readonly=True)
    iva = fields.Float(string="iva", readonly=True)
    ieps = fields.Float(string="ieps", readonly=True)
    total = fields.Float(string="Total", readonly=True)
    activa = fields.Boolean(string="Activa", default = True)
    #folio = fields.Char(string="Folio", readonly=True, copy=False, default=lambda self: self.env['ir.sequence'].next_by_code('mi.modelo.folio'))

    metododepago = fields.Selection(
        selection = [
            ("PPD", "Pago por parcialidades/Crédíto"),
            ("PUE", "Pago en una sola exhibición/Contado")
        ], string="Método de Pago", required=True, default="PPD"
    )

    formadepago = fields.Selection(
        selection = [
            ("01", "Efectivo"),
            ("02", "Cheque Nominativo"),
            ("03", "Transferencia"),
            ("04", "Tarjeta de Crédito"),
            ("15", "Condonación"),
            ("17", "Compensación"),
            ("28", "Tarjeta de Débito"),
            ("30", "Aplicación de Anticipos"),
            ("99", "Por Definir")
        ], string="Forma de Pago", default="01"
    )

    @api.onchange('metododepago')
    def _chgmpago(self):
        for record in self:
            if record.metododepago == 'PPD':
                record.formadepago = '99'

    @api.onchange('detalle')
    def _onchange_detalles(self):
        self.importe = sum(line.importeb for line in self.detalle)
        self.iva = sum(line.iva for line in self.detalle)
        self.ieps = sum(line.ieps for line in self.detalle)
        self.total = sum(line.importe for line in self.detalle)

    @api.constrains('detalle')
    def _check_detalle_venta(self):
        for record in self:
            if not record.detalle:
                raise ValidationError(_('No se puede guardar una venta sin al menos un producto.'))
        for linea in record.detalle:
            if linea.cantidad <= 0 or linea.precio <= 0:
                raise ValidationError(_('La Cantidad/Precio no pueden ser 0'))
            if not linea.detalle.producto:
                raise ValidationError(_('Debe seleccionar un producto'))
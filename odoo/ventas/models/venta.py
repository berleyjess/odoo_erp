#ventas/models/venta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date
# Modelo de ventas que gestiona información de cliente, productos, impuestos y flujo a cuentas por cobrar

class venta(models.Model):
    _name = 'ventas.venta'
    _description = 'Venta de artículos'
    
    codigo = fields.Char(string="Código", required = False)
    cliente = fields.Many2one('clientes.cliente', string="Cliente", required = True)
    contrato = fields.Many2one('solcreditos.solcredito', string="Contrato", domain="['&',('cliente', '=', cliente), ('contratoactivo','=',True), ('vencimiento', '>', hoy)]" if cliente else "[('id', '=', 0)]")

    # Calcula siempre la fecha actual sin depender de otros campos
    hoy = fields.Date(compute='_compute_hoy')
    @api.depends()  # Sin dependencias, se calcula siempre
    def _compute_hoy(self):
        for record in self:
            record.hoy = date.today()
    #contrato = fields.Many2one('solcreditos.solcredito', string="Contrato")#, domain="['&',('cliente', '=', cliente), ('contratoactivo','=',True), ('vencimiento' > context_today())]" if cliente else "[('id', '=', 0)]")

    observaciones = fields.Char(string = "Observaciones", size=48)
    fecha = fields.Date(string="Fecha", default=lambda self: date.today())
    #vendedor = fields.Many2one('vendedor', string="Vendedor", required = True)
    #sucursal = fields.Many2one('sucursal', string="Sucursal", required = True)
    #empresa = fields.Many2one('empresa', string="Empresa", readonly = True)
    importe = fields.Float(string="Importe", readonly=True, store = True, compute='_add_detalles')
    iva = fields.Float(string="iva", readonly=True, store = True, compute='_add_detalles')
    ieps = fields.Float(string="ieps", readonly=True, store = True, compute='_add_detalles')
    total = fields.Float(string="Total", readonly=True, store = True, compute='_add_detalles')
    activa = fields.Boolean(string="Activa", default = True)
    #folio = fields.Char(string="Folio", readonly=True, copy=False, default=lambda self: self.env['ir.sequence'].next_by_code('mi.modelo.folio'))

    #detalle = fields.One2many('ventas.detalleventa_ext', 'venta_id', string="Ventas")
    detalle = fields.One2many('transacciones.transaccion', 'venta_id', string="Venta")

        # Relación con Sucursal (obligatoria para prefijar el código)
    sucursal_id = fields.Many2one(
        'sucursales.sucursal', string="Sucursal",
        required=True, ondelete='restrict', index=True
    )

    # Código único de la venta (SERIE-000001)
    codigo = fields.Char(string="Código", readonly=True, copy=False, index=True)

    state = fields.Selection(
    [('draft', 'Borrador'), ('confirmed', 'Confirmada'), ('cancelled', 'Cancelada'), ('invoiced', 'Facturada')],
    string="Estado", default='draft', required=True, index=True
    )

    is_editing = fields.Boolean(default=False, store = True)

    _sql_constraints = [
        ('venta_codigo_uniq', 'unique(codigo)', 'El código de la venta debe ser único.'),
    ]

# Limpia el contrato y filtra contratos válidos del cliente con base en vigencia y estado
    @api.onchange('cliente')
    def _onchange_cliente(self):
        self.contrato = False
        self.env.context = {}
        if self.cliente:
            # Filtramos en el servidor para que use Python y no dependa de campos no stored
            contratos_validos = self.env['solcreditos.solcredito'].search([
                ('cliente', '=', self.cliente.id),
                ('contratoactivo', '=', True),  # Aunque sea compute, aquí sí lo evalúa en Python
                ('vencimiento', '>', fields.Date.today())
            ])
            return {
                'domain': {
                    'contrato': [('id', 'in', contratos_validos.ids)]
                }
            }
        else:
            return {
                'domain': {
                    'contrato': [('id', '=', 0)]
                }
            }

# Método de pago: PPD (Crédito) o PUE (Contado)
    metododepago = fields.Selection(
        selection = [
            ("PPD", "Crédíto"),
            ("PUE", "Contado")
        ], string="Método de Pago", required=True, default="PPD", store = True
    )

# Forma de pago según catálogo SAT
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

# Si es PPD, se asigna forma de pago "Por definir" (99)
    @api.onchange('metododepago')
    def _chgmpago(self):
        for record in self:
            if record.metododepago == 'PPD':
                record.formadepago = '99'
        self._apply_prices_by_method()
        #self._onchange_detalles()

    """
    Qué hace: Si el método es PPD (crédito), asigna automáticamente formadepago = '99' (“Por definir”).
    Cuándo corre: Solo en UI (formulario) cuando cambias metododepago. No se ejecuta en importaciones, create RPC, tests sin UI, etc.
    Efecto: Cambia el valor en el registro en memoria del formulario; se persiste al Guardar.
    """

    def _apply_prices_by_method(self):
        """Forzar precio de líneas según PUE (contado) / PPD (crédito)."""
        for v in self:
            metodo = v.metododepago or 'PPD'
            for line in v.detalle:
                #if line.producto:
                #    line.precio = line.producto.contado if metodo == 'PUE' else line.producto.credito
                if line.producto_id:
                    line.precio = line.producto_id.contado if metodo == 'PUE' else line.producto_id.credito



# Recalcula importes, IVA, IEPS y total a partir de las líneas de detalle
    @api.depends('detalle')
    def _add_detalles(self):
        self.importe = sum(line.subtotal for line in self.detalle)#importeb -> subtotal
        self.iva = sum(line.iva for line in self.detalle)
        self.ieps = sum(line.ieps for line in self.detalle)
        self.total = sum(line.importe for line in self.detalle)
    """
    Qué hace: Recalcula importe, iva, ieps, total sumando los campos calculados de cada línea (line.importeb, line.iva, line.ieps, line.importe).
    Cuándo corre: UI al agregar/editar/borrar líneas en detalle.
    Efecto: Actualiza los totales del encabezado antes de guardar.
        Nota: al ser readonly=True, los totales no se editan manualmente; este onchange les da valor.
    """

# Valida que haya al menos un producto y que cantidad y precio sean mayores a cero
    @api.constrains('detalle')
    def _check_detalle_venta(self):
        for record in self:
            if not record.detalle:
                raise ValidationError(_('No se puede guardar una venta sin al menos un producto.'))
        for linea in record.detalle:
            if linea.cantidad <= 0 or linea.precio <= 0:
                raise ValidationError(_('La Cantidad/Precio no pueden ser 0'))
            if not linea.producto_id:
                raise ValidationError(_('Debe seleccionar un producto'))
            
    def action_open_edit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Editar Venta',
            'res_model': 'ventas.venta',
            'view_mode': 'form',
            'view_id': self.env.ref('ventas.view_venta_form').id,
            'res_id': self.id,
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }
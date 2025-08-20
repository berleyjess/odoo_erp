# ventas/models/cxcs_from_sales.py
from odoo import api, fields, models

# Extiende cuentasxcobrar.cuentaxcobrar para vincular ventas y sus detalles
class CxCVentas(models.Model):
    _inherit = 'cuentasxcobrar.cuentaxcobrar'

    venta_id = fields.Many2one('ventas.venta', string="Venta", index=True)
    detalle_venta_id = fields.Many2one('ventas.detalleventa_ext', string="Detalle de venta", index=True)

# Evita que una misma línea de venta se registre dos veces en el mismo contrato
    _sql_constraints = [
        # Evita duplicar la misma línea de venta en el mismo contrato
        ('uniq_contrato_detalle',
         'unique(contrato_id, detalle_venta_id)',
         'Este renglón de venta ya está en el estado de cuenta.')
    ]

# Crea una línea en CxC a partir de un detalle de venta, calculando importes e impuestos
    @api.model
    def create_from_sale_line(self, contrato, venta, line):
        """Crea una línea de estado a partir de un renglón de venta."""
        concepto = line.producto_id.display_name if getattr(line, 'producto_id', False) else (getattr(line, 'descripcion', '') or '')
        cantidad = float(getattr(line, 'c_entrada', 0.0))
        precio   = float(getattr(line, 'precio', 0.0))
        iva      = float(getattr(line, 'iva', 0.0))
        ieps     = float(getattr(line, 'ieps', 0.0))
        importe  = cantidad * precio
        cargo    = importe + iva + ieps

        vals = {
            'contrato_id': contrato.id,
            'venta_id': venta.id,
            'detalle_venta_id': line.id,
            'fecha': venta.fecha or fields.Date.today(),
            'referencia': venta.codigo or venta.display_name or str(venta.id),
            'concepto': concepto,
            'cantidad': cantidad,
            'precio': precio,
            'importe': importe,
            'iva': iva,
            'ieps': ieps,
            'cargo': cargo,
            'abono': 0.0,
            'saldo': cargo,  # si luego registras pagos, aquí se va disminuyendo
        }
        return self.create(vals)

        """
        Qué hace: Construye y crea una línea en cuentasxcobrar.cuentaxcobrar con:
        Vinculaciones: contrato_id, venta_id, detalle_venta_id.
        Datos económicos: cantidad, precio, importe (= cantidad*precio), iva, ieps, cargo (= importe+iva+ieps), abono=0, saldo=cargo.
        Metadatos: fecha (de la venta), referencia (código o nombre de venta), concepto (nombre del producto o descripción).
        Cuándo corre: Llamado por _post_to_statement_if_needed() por cada línea de venta que no esté ya en CxC.
        Efecto: Crea el renglón de estado de cuenta que luego podrá ser abonado con pagos (que disminuirán saldo).
        """
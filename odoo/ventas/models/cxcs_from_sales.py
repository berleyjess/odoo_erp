# ventas/models/cxcs_from_sales.py
from odoo import api, fields, models

class CxCVentas(models.Model):
    _inherit = 'cuentasxcobrar.cuentaxcobrar'

    venta_id = fields.Many2one('ventas.venta', string="Venta", index=True)
    detalle_venta_id = fields.Many2one('ventas.detalleventa_ext', string="Detalle de venta", index=True)

    _sql_constraints = [
        # Evita duplicar la misma línea de venta en el mismo contrato
        ('uniq_contrato_detalle',
         'unique(contrato_id, detalle_venta_id)',
         'Este renglón de venta ya está en el estado de cuenta.')
    ]

    @api.model
    def create_from_sale_line(self, contrato, venta, line):
        """Crea una línea de estado a partir de un renglón de venta."""
        concepto = line.producto.display_name if getattr(line, 'producto', False) else (getattr(line, 'descripcion', '') or '')
        cantidad = float(getattr(line, 'cantidad', 0.0))
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

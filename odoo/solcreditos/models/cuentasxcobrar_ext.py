# solcreditos/models/cuentasxcobrar_ext.py
from odoo import fields, models

class CxCContrato(models.Model):
    _inherit = 'cuentasxcobrar.cuentaxcobrar'
    #_name = 'solcredito.cuentaxcobrar_ext'

    contrato_id = fields.Many2one(
        'solcreditos.solcredito',
        string="Solicitud/Contrato",
        index=True,
        ondelete='cascade'
    )

    
    """@api.model
    def create(self, vals):
        # 1. Primero creamos el registro principal
        record = super().create(vals)
        
        # 2. Accedemos al modelo relacionado si es necesario
        if 'detalle_id' in vals:
            detalle_model = self.env['detalleventas.detalleventa']
            detalle = detalle_model.browse(vals['detalle_id'])
            
            # Calculamos todos los valores necesarios
            importe = detalle.cantidad * detalle.precio
            cargo = importe + detalle.iva + detalle.ieps
            abono = 0  # Valor por defecto
            saldo = abono - cargo  # Cálculo del saldo
            
            # Actualizamos campos basados en el detalle
            record.write({
                'concepto': detalle.producto,
                'cantidad': detalle.cantidad,
                'precio': detalle.precio,
                'importe': importe,
                'iva': detalle.iva,
                'ieps': detalle.ieps,
                'cargo': cargo,
                'abono': abono,
                'saldo': saldo  # Campo saldo incluido
            })
        
        return record
                

    def write(self, vals):
        if 'detalle_id' in vals or any(field in vals for field in ['cantidad', 'precio', 'iva', 'ieps']):
            detalle = self.env['detalledeventas.detalleventa'].browse(vals.get('detalle_id', self.detalle_id.id))
            if detalle:
                vals.update({
                    'concepto': vals.get('concepto', detalle.producto),
                    'cantidad': vals.get('cantidad', detalle.cantidad),
                    'precio': vals.get('precio', detalle.precio),
                    'importe': float(vals.get('cantidad', detalle.cantidad)) * 
                            float(vals.get('precio', detalle.precio)),
                    'iva': vals.get('iva', detalle.iva),
                    'ieps': vals.get('ieps', detalle.ieps),
                    'cargo': (float(vals.get('cantidad', detalle.cantidad)) * 
                            float(vals.get('precio', detalle.precio))) + 
                            float(vals.get('iva', detalle.iva)) + 
                            float(vals.get('ieps', detalle.ieps)),
                    'abono': 0,
                    'saldo': 0 - (float(vals.get('cantidad', detalle.cantidad)) * 
                            float(vals.get('precio', detalle.precio))) + 
                            float(vals.get('iva', detalle.iva)) + 
                            float(vals.get('ieps', detalle.ieps))

                })
            
            elif record.cargo_id:
                record.referencia = record.cargo_id.folio
                record.concepto = record.cargo_id.detalle
                record.cantidad = 1
                record.precio = record.cargo_id.importe
                record.importe = record.cargo_id.importe
                record.iva = record.cargo_id.iva
                record.ieps = record.cargo_id.ieps
                record.cargo = record.importe + record.iva + record.ieps
                record.abono = 0
            elif record.pago_id:
                record.referencia = record.pago_id.folio
                record.concepto = record.pago_id.detalle
                record.cantidad = 1
                record.precio = record.pago_id.importe
                record.importe = record.pago_id.importe
                record.iva = 0
                record.ieps = 0
                record.cargo = 0
                record.abono = record.importe + record.iva + record.ieps
            return super().write(vals)"""
from odoo import models, fields, api
from datetime import date, timedelta

class TransientEdocta(models.TransientModel):
    _name = 'transient.edocta'
    _description = 'Estado de Cuenta Transitorio'

    lines = fields.One2many('tmpline', 'edocta_id', string="Líneas")
    contrato_id = fields.Many2one('creditos.credito', string="Crédito")
    desde = fields.Date(string='Desde', default=fields.Date.today)
    hasta = fields.Date(string='Hasta', default=fields.Date.today)

    justcalc = fields.Boolean(string ="Sólo calcular", default = False)

    generado_automaticamente = fields.Boolean(default=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Establecer fechas por defecto (últimos 30 días)
        hoy = fields.Date.today()
        res['desde'] = hoy - timedelta(days=30)
        res['hasta'] = hoy
        return res

    @api.onchange('contrato_id', 'desde', 'hasta')
    def _onchange_generar_automatico(self):
        if self.contrato_id and not self.generado_automaticamente:
            # Marcar como generado para evitar loops
            self.generado_automaticamente = True
            # Llamar al método generar
            self.generar()

    def generar(self):
        self.ensure_one()
        self.lines.unlink()

        # Buscar transacciones con filtro de fechas
        cxcs = self.env['transacciones.transaccion'].search([
            ('contrato_id', '=', self.contrato_id.id),
            ('fecha', '>=', self.desde),
            ('fecha', '<=', self.hasta),
        ], order='fecha asc')  # Ordenar por fecha

        lineas = []
        balance = 0.0

        for linea in cxcs:
            balance += linea.importe
            lineas.append((0, 0, {
                'edocta_id': self.id,
                'fecha': linea.fecha,
                'referencia': linea.referencia or '',
                'concepto': linea.producto_id.name if linea.producto_id else '',
                'cantidad': linea.cantidad,
                'precio': linea.precio,
                'iva': linea.iva_amount,
                'ieps': linea.ieps_amount,
                'importe': linea.importe,
                'cargo': linea.importe if linea.importe > 0 else 0.0,
                'abono': abs(linea.importe) if linea.importe < 0 else 0.0,
                'balance': balance,
            }))

        cargo = self.env['cargosdetail.cargodetail'].search([
            ('contrato_id', '=', self.contrato_id.id),
            ('fecha', '>=', self.desde),
            ('fecha', '<=', self.hasta),
        ], order='fecha asc')  # Ordenar por fecha

        for linea in cargo:
            tmpcantidad =  linea.contrato_id.superficie if linea.tipocargo == '0' else 1
            tmpprecio = linea.costo

            if linea.tipocargo == '0':
                tmpprecio = linea.costo * tmpcantidad
            #elif linea.tipocargo == '1': <---- Cuando genere montoejercido en el Crédito
            #    tmpprecio = linea.contrato_id.montoejercido * linea.porcentaje

            tmpiva = tmpprecio * tmpcantidad * linea.iva
            tmpieps = tmpprecio * tmpcantidad * linea.ieps

            tmpimporte = tmpiva + tmpieps + tmpcantidad * tmpprecio

            balance += tmpimporte
            lineas.append((0, 0, {
                'edocta_id': self.id,
                'fecha': linea.fecha,
                'referencia': linea.referencia or '',
                'concepto': linea.cargo.concepto if linea.cargo else '',
                'cantidad': tmpcantidad,
                'precio': tmpprecio,
                'iva': tmpiva,
                'ieps': tmpieps,
                'importe': tmpimporte,
                'cargo': tmpimporte,
                'abono': 0.0,
                'balance': balance,
            }))

        # Escribir las líneas
        self.write({'lines': lineas})

        if not self.justcalc:
            return self._show_results()
    
    def _show_results(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Simulación de Estado de Cuenta',
            'res_model': self._name,  # ✅ CORREGIDO: usar self._name
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
            'views': [(False, 'form')]
        }
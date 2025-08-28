from odoo import models, fields, api
from odoo.exceptions import ValidationError

class cargodetail(models.Model):
    _name = 'cargosdetail.cargodetail'

    fecha = fields.Date(string = "Fecha", default=fields.Date.context_today, required = True)
    cargo = fields.Many2one('cargos.cargo', string = "Cargo", required = True)
    contrato_id = fields.Many2one('contratos.contrato', string = "Contrato")
    #credito_id = fields.Many2one('creditos.credito', string = "Crédito")
    costo = fields.Float(string = "Costo", default = 0.0)
    porcentaje = fields.Float(string ="Porcentaje", default = 0.0)
    tipocargo = fields.Selection(
        selection = [
            ('0', "Costo x Superficie"),
            ('1', "Porcentaje x Saldo Ejercido"),
            ('2', "Monto Único")
        ],
        store = True, related='cargo.tipo', string="Tipo de Cargo"
    )

    descripcion = fields.Char(string = "Descripción", related='cargo.descripcion')

    iva = fields.Float(string = "Iva %", related='cargo.iva')
    ieps = fields.Float(string = "Ieps %", related='cargo.ieps')

    cargocontrato = fields.Boolean(string = "Cargo del contrato", default = False, compute = '_cargo_contrato')

    @api.depends('contrato_id')
    def _cargo_contrato(self):
        for i in self:
            i.cargocontrato =  bool(i.contrato_id)



    @api.constrains('cargo')
    def _check_superficie_required(self):
        for record in self:
            if record.contrato_id:
                if record.cargo.tipo == '0': # Costo por superficie
                    if not record.costo:
                        raise ValidationError("Debe capturar un costo por Hectárea.")
                elif record.cargo.tipo == '1':  # Saldo ejercido
                   if not record.porcentaje or not (record.porcentaje > 0 and record.porcentaje <= 1):
                        raise ValidationError("Ingrese un porcentaje válido para el cálculo del cargo.")
                elif record.cargo.tipo == '2':  # Monto único
                    if not record.costo:
                        raise ValidationError("Debe capturar el monto del cargo.")
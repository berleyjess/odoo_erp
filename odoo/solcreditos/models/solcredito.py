# solcreditos/models/solcredito.py
from odoo import models, fields, api

class solcredito(models.Model):
    _name = 'solcreditos.solcredito'
    _description = 'Asignacion de contratos a clientes'

    cliente = fields.Many2one('clientes.cliente', string="Nombre", required=True)
    ciclo = fields.Many2one('ciclos.ciclo', string="Ciclo", required=True)
    contrato = fields.Many2one('contratos.contrato', string="Contrato", required=True)
    titularr = fields.Selection(
        selection=[
            ("0", "Sí"),
            ("1", "No")
        ], required = True, string="El cliente es responsable del crédito?", default="0"
    )

    predios = fields.One2many('solcreditos.predio_ext', 'solcredito_id', string = "Predios")
    garantias = fields.One2many('solcreditos.garantia_ext', 'solcredito_id', string = "Garantías")
    #titularr = fields.Char(string="Titular de la garantía", required=True)
    # Datos variables dependiendo del tipo de crédito
    # monto y vencimiento son manuales si el tipodecredito es "Especial", si es "Parcial" o "AVIO" se toman del contrato
    # superficie es manual si es "Parcial". Si es "AVIO" se calcula en base a los predios. Si es "Especial" no se usa.
    monto = fields.Float(string="Monto solicitado", digits=(12, 4), 
                         compute="_compute_monto", store=True, required=True)
    vencimiento = fields.Date(string="Fecha de vencimiento", required=True)
    superficie = fields.Float(string="Superficie (Hectáreas)", digits=(12, 4), required=True)

    obligado = fields.Char(string="Titular del crédito", size=100, required=True)
    obligadodomicilio = fields.Many2one('localidades.localidad', string="Domicilio", required=True)
    obligadoRFC = fields.Char(string = "RFC", required=True)

    @api.depends('contrato.tipocredito', 'contrato.aporte', 'superficie')
    def _compute_monto(self):
        for record in self:
            if record.contrato and record.contrato.tipocredito == "2":
                record.monto = record.monto
            elif record.contrato:
                record.monto = record.contrato.aporte * record.superficie
            else:
                record.monto = 0.0

    @api.onchange('ciclo', 'contrato')
    def _onchange_ciclo(self):
        if self.contrato:
            self.vencimiento = self.ciclo.fechafinal

        if self.ciclo:
            self.contrato = False
            return {
                'domain': {'contrato': [('ciclo', '=', self.ciclo.id)]}
            }
        else:
            return {'domain': {'contrato': []}}

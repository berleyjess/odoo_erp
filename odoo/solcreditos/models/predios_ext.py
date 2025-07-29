from odoo import models,fields, api
from odoo.exceptions import ValidationError

class predio_ext(models.Model):
    _name = 'solcreditos.predio_ext'
    _description = 'Extensión de Predios para solicitudes de créditos'
    _inherit = 'predios.predio'

    solcredito_id = fields.Many2one('solcreditos.solcredito', string="Solicitud de Crédito",
                                    ondelete='cascade')
    superficiecultivable = fields.Float(
        string="Superficie cultivable (Hectáreas)", required=True, digits=(12, 4),
        help="Superficie cultivable del predio en hectáreas.", default=lambda self: self.superficie)
    
    @api.constrains('superficiecultivable')
    def _check_superficiecultivable(self):
        for record in self:
            if record.superficiecultivable <= 0:
                raise ValidationError("La superficie cultivable debe ser mayor a 0.")
            if record.superficiecultivable > record.superficie:
                raise ValidationError("La superficie cultivable no puede ser mayor que la superficie total del predio.")
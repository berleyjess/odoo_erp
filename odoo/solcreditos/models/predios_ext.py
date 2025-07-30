#solcreditos/models/predios_ext.py
from odoo import models,fields, api
from odoo.exceptions import ValidationError

class predio_ext(models.Model):
    _name = 'solcreditos.predio_ext'
    _description = 'Extensión de Predios para solicitudes de créditos'
    _inherit = 'predios.predio'

    #nombres de atributos de la clase padre garantías.garantia para referenciarlos correctamente.
    #localidad=Many2one ("localidades.localidad")
    #titular=Char
    #superficie=Float
    #nocertificado=Char
    #colnorte=Char
    #colsur=Char
    #coleste=Char
    #coloeste=Char
    #georeferencias=One2many ("predios.georeferencia_ext")
    
    es_dueno_predio = fields.Selection(
        selection=[('si', 'Sí'), ('no', 'No')],
        string="¿Es dueño del predio?",
        required=True,
        default='si'
    )

    @api.onchange('es_dueno_predio', 'solcredito_id')
    def _onchange_es_dueno_predio(self):
        """Autollenar titular/localidad si es dueño"""
        if self.es_dueno_predio == 'si' and self.solcredito_id and self.solcredito_id.cliente:
            self.titular = self.solcredito_id.cliente.nombre
            # Si el cliente tiene localidad, lo autollenamos (solo si existe el campo en cliente)
            if hasattr(self.solcredito_id.cliente, 'localidad') and self.solcredito_id.cliente.localidad:
                self.localidad = self.solcredito_id.cliente.localidad.id
        elif self.es_dueno_predio == 'no':
            self.titular = ''
            self.localidad = False
            return {
                'warning': {
                    'title': "Aviso",
                    'message': "Debes escribir el nombre del titular cuando no es dueño.",
                }
            }

    solcredito_id = fields.Many2one('solcreditos.solcredito', string="Solicitud de Crédito",
                                    ondelete='cascade')
    superficiecultivable = fields.Float(
        string="Superficie cultivable (Hectáreas)", required=True, digits=(12, 4),
        help="Superficie cultivable del predio en hectáreas.", default=lambda self: self.superficie)
    
    localidad_nombre = fields.Char(
        string="Nombre de Localidad",
        compute="_compute_localidad_nombre",
        store=False
    )

    @api.depends('localidad')
    def _compute_localidad_nombre(self):
        for rec in self:
            rec.localidad_nombre = rec.localidad.nombre if rec.localidad else ''

    @api.constrains('superficiecultivable')
    def _check_superficiecultivable(self):
        for record in self:
            if record.superficiecultivable <= 0:
                raise ValidationError("La superficie cultivable debe ser mayor a 0.")
            if record.superficiecultivable > record.superficie:
                raise ValidationError("La superficie cultivable no puede ser mayor que la superficie total del predio.")
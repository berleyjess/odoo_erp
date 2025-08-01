# solcreditos/models/predios_ext.py
from odoo import models, fields, api
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

    FIELDS_TO_UPPER = ['RFC', 'titular']  # Aquí pones los fields que quieres en mayúscula

    @staticmethod
    def _fields_to_upper(vals, fields):
        for fname in fields:
            if fname in vals and isinstance(vals[fname], str):
                vals[fname] = vals[fname].upper()
        return vals

    @api.model
    def create(self, vals):
        vals = self._fields_to_upper(vals, self.FIELDS_TO_UPPER)
        return super(predio_ext, self).create(vals)

    def write(self, vals):
        vals = self._fields_to_upper(vals, self.FIELDS_TO_UPPER)
        return super(predio_ext, self).write(vals)

    @api.depends('localidad')
    def _compute_localidad_nombre(self):
        for rec in self:
            rec.localidad_nombre = rec.localidad.nombre if rec.localidad else ''

    # CORREGIDO: Quitar el @api.depends que causaba problemas de guardado

    @api.onchange('es_dueno_predio', 'solcredito_id')
    def _onchange_es_dueno_predio(self):
        """Autollenar titular/localidad si es dueño"""
        if self.es_dueno_predio == 'si' and self.solcredito_id and self.solcredito_id.cliente:
            self.titular = self.solcredito_id.cliente.nombre
            self.RFC = self.solcredito_id.cliente.rfc if hasattr(self.solcredito_id.cliente, 'rfc') else ''
            self.localidad = self.solcredito_id.cliente.localidad.id if hasattr(self.solcredito_id.cliente, 'localidad') and self.solcredito_id.cliente.localidad else False
        elif self.es_dueno_predio == 'no':
            self.titular = ''
            self.RFC = ''
            self.localidad = False
            return {
                'warning': {
                    'title': "Aviso",
                    'message': "Debes escribir el nombre del titular cuando no es dueño.",
                }
            }

    @api.model
    def create(self, vals):
        """Override create para asegurar que se llene el titular si es dueño"""
        if vals.get('es_dueno_predio') == 'si' and vals.get('solcredito_id'):
            solcredito = self.env['solcreditos.solcredito'].browse(vals['solcredito_id'])
            if solcredito and solcredito.cliente:
                vals['titular'] = solcredito.cliente.nombre
                if hasattr(solcredito.cliente, 'localidad') and solcredito.cliente.localidad:
                    vals['localidad'] = solcredito.cliente.localidad.id
        # --- Luego mayúsculas ---
        vals = self._fields_to_upper(vals, self.FIELDS_TO_UPPER)
        return super(predio_ext, self).create(vals)
    
    def write(self, vals):
        """Override write para asegurar que se llene el titular si es dueño"""
        if 'es_dueno_predio' in vals and vals['es_dueno_predio'] == 'si':
            for record in self:
                if record.solcredito_id and record.solcredito_id.cliente:
                    vals['titular'] = record.solcredito_id.cliente.nombre
                    if hasattr(record.solcredito_id.cliente, 'localidad') and record.solcredito_id.cliente.localidad:
                        vals['localidad'] = record.solcredito_id.cliente.localidad.id
        elif 'es_dueno_predio' in vals and vals['es_dueno_predio'] == 'no':
            vals['titular'] = ''
            vals['localidad'] = False
        # --- Luego mayúsculas ---
        vals = self._fields_to_upper(vals, self.FIELDS_TO_UPPER)
        return super(predio_ext, self).write(vals)

    @api.constrains('superficiecultivable')
    def _check_superficiecultivable(self):
        for record in self:
            if record.superficiecultivable <= 0:
                raise ValidationError("La superficie cultivable debe ser mayor a 0.")
            if record.superficiecultivable > record.superficie:
                raise ValidationError("La superficie cultivable no puede ser mayor que la superficie total del predio.")

    @api.constrains('titular')
    def _check_titular_required(self):
        """Validar que el titular sea obligatorio"""
        for record in self:
            if not record.titular or not record.titular.strip():
                raise ValidationError("El campo Titular es obligatorio para el predio.")
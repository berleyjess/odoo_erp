# solcreditos/models/garantia_ext.py
from odoo import fields, models, api

class garantia_ext(models.Model):
    _name = 'solcreditos.garantia_ext'
    _description = 'Extensión del modelo de Garantías'
    _inherit = 'garantias.garantia'  # Hereda del modelo de garantías existente

    #nombres de atributos de la clase padre garantías.garantia para referenciarlos correctamente.
    #tipo=selection
    #titular=char
    #descripcion=text
    #valor=float
    #fecha_entrega=date
    #persona_entrega=char
    #persona_recibe=char
    
    solcredito_id = fields.Many2one('solcreditos.solcredito', string="Solicitud")
    
    # Campo para seleccionar si es dueño de la garantía
    es_dueno_garantia = fields.Selection(
        selection=[
            ("si", "Sí"),
            ("no", "No")
        ], 
        string="¿Es dueño de la garantía?", 
        required=True,
        default="si"
    )

    FIELDS_TO_UPPER = ['RFC', 'titular']

    @staticmethod
    def _fields_to_upper(vals, fields):
        for fname in fields:
            if fname in vals and isinstance(vals[fname], str):
                vals[fname] = vals[fname].upper()
        return vals



    # CORREGIDO: Quitar el @api.depends que causaba problemas de guardado

    @api.onchange('es_dueno_garantia', 'solcredito_id')
    def _onchange_es_dueno_garantia(self):
        """Auto-rellena el titular si es dueño de la garantía"""
        if self.es_dueno_garantia == 'si' and self.solcredito_id and self.solcredito_id.cliente:
            self.titular = self.solcredito_id.cliente.nombre
            self.RFC = self.solcredito_id.cliente.rfc if hasattr(self.solcredito_id.cliente, 'rfc') else ''
            self.localidad = self.solcredito_id.cliente.localidad.id if hasattr(self.solcredito_id.cliente, 'localidad') and self.solcredito_id.cliente.localidad else False
        elif self.es_dueno_garantia == 'no':
            self.titular = ''
            self.RFC = ''
            self.localidad = False

    @api.model
    def create(self, vals):
        """Override create para asegurar que se llene el titular si es dueño"""
        if vals.get('es_dueno_garantia') == 'si' and vals.get('solcredito_id'):
            solcredito = self.env['solcreditos.solcredito'].browse(vals['solcredito_id'])
            if solcredito and solcredito.cliente:
                vals['titular'] = solcredito.cliente.nombre
        # Luego, forzar mayúsculas
        vals = self._fields_to_upper(vals, self.FIELDS_TO_UPPER)
        return super(garantia_ext, self).create(vals)

    def write(self, vals):
        """Override write para asegurar que se llene el titular si es dueño"""
        if 'es_dueno_garantia' in vals and vals['es_dueno_garantia'] == 'si':
            for record in self:
                if record.solcredito_id and record.solcredito_id.cliente:
                    vals['titular'] = record.solcredito_id.cliente.nombre
        elif 'es_dueno_garantia' in vals and vals['es_dueno_garantia'] == 'no':
            vals['titular'] = ''
        vals = self._fields_to_upper(vals, self.FIELDS_TO_UPPER)
        return super(garantia_ext, self).write(vals)
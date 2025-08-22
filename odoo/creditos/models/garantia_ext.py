
# creditos/models/garantia_ext.py


from odoo import fields, models

# garantia_ext.py

from odoo import fields, models, api
class garantia_ext(models.Model):
    _name = 'creditos.garantia_ext'
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
    
    credito_id = fields.Many2one('creditos.credito', string="Solicitud")
    
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

    @api.onchange('es_dueno_garantia', 'credito_id')
    def _onchange_es_dueno_garantia(self):
        """Auto-rellena el titular si es dueño de la garantía"""
        if self.es_dueno_garantia == 'si' and self.credito_id and self.credito_id.cliente:
            self.titular = self.credito_id.cliente.nombre
            self.RFC = self.credito_id.cliente.rfc if hasattr(self.credito_id.cliente, 'rfc') else ''
            self.localidad = self.credito_id.cliente.localidad.id if hasattr(self.credito_id.cliente, 'localidad') and self.credito_id.cliente.localidad else False
        elif self.es_dueno_garantia == 'no':
            self.titular = ''
            self.RFC = ''
            self.localidad = False

    @api.model
    def create(self, vals):
        """Override create para asegurar que se llene el titular si es dueño"""
        if vals.get('es_dueno_garantia') == 'si' and vals.get('credito_id'):
            credito = self.env['creditos.credito'].browse(vals['credito_id'])
            if credito and credito.cliente:
                vals['titular'] = credito.cliente.nombre
        # Luego, forzar mayúsculas
        vals = self._fields_to_upper(vals, self.FIELDS_TO_UPPER)
        return super(garantia_ext, self).create(vals)

    def write(self, vals):
        """Override write para asegurar que se llene el titular si es dueño"""
        if 'es_dueno_garantia' in vals and vals['es_dueno_garantia'] == 'si':
            for record in self:
                if record.credito_id and record.credito_id.cliente:
                    vals['titular'] = record.credito_id.cliente.nombre
        elif 'es_dueno_garantia' in vals and vals['es_dueno_garantia'] == 'no':
            vals['titular'] = ''
        vals = self._fields_to_upper(vals, self.FIELDS_TO_UPPER)
        return super(garantia_ext, self).write(vals)
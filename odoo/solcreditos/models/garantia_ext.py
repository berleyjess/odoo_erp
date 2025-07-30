# garantia_ext.py
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
    #es_dueno_garantia=selection
    
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
    
    @api.onchange('es_dueno_garantia', 'solcredito_id')
    def _onchange_es_dueno_garantia(self):
        """Auto-rellena el titular si es dueño de la garantía"""
        if self.es_dueno_garantia == 'si' and self.solcredito_id and self.solcredito_id.cliente:
            self.titular = self.solcredito_id.cliente.nombre
        elif self.es_dueno_garantia == 'no':
            self.titular = ''
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class predios(models.Model):
    _name = 'creditos.predio'

    credito_id = fields.Many2one('creditos.credito', string = "Crédito relacionado", store=True, readonly=True)

    empresa = fields.Many2one(
        'empresas.empresa',
        string="Empresa",
        related='credito_id.empresa',
        store=True,
        readonly=True,
    )
    sucursal = fields.Many2one(
        'sucursales.sucursal',
        string="Sucursal",
        related='credito_id.sucursal',
        store=True,
        readonly=True,
    )
    
    #DATOS PARA PERSONA
    titular = fields.Char(string = "Titular", required=True)
    RFC = fields.Char(string = "RFC del titular")
    ######################

    localidad = fields.Many2one('localidades.localidad', string = "Localidad", required = True, store=True)
    
    superficie = fields.Float(string = "Superficie", required = True, store=True)
    superficiecultivable = fields.Float(string = "Sup/Habilitada", required = True, store=True)
    nocertificado = fields.Char(string = "No. de Certificado", required = True, store=True)
    colnorte = fields.Char(string = "Colindancia Norte", store=True)
    colsur = fields.Char(string = "Colindancia Sur", store=True)
    coleste = fields.Char(string = "Colindancia Este", store=True)
    coloeste = fields.Char(string = "Colindancia Oeste", store=True)

    @api.depends('superficie', 'superficiecultivable')
    def _compute_area(self):
        for record in self:
            if record.superficie < record.superficiecultivable:
                raise ValueError("La superficie cultivable no puede ser mayor a la superficie total del predio.")
            if record.superficie <= 0:
                raise ValueError("La superficie total del predio debe ser mayor a cero.")
            if record.superficiecultivable <=0:
                raise ValueError("La superficie cultivable debe ser mayor a cero.")
            
    """georeferencias = fields.One2many(
        'predios.georeferencia_ext',
        'predio_id',
        string="Georeferencias",
        help="Georeferencias asociadas al predio")"""
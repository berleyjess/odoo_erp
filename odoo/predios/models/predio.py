from odoo import models, fields

class predios(models.Model):
    _name = 'predios.predio'

    localidad = fields.Many2one('localidades.localidad', string = "Localidad", required = True)
    titular = fields.Char(string = "Titular")
    RFC = fields.Char(string = "RFC del titular")
    superficie = fields.Float(string = "Superficie", required = True)
    nocertificado = fields.Char(string = "No. de Certificado", required = True)
    colnorte = fields.Char(string = "Colindancia Norte")
    colsur = fields.Char(string = "Colindancia Sur")
    coleste = fields.Char(string = "Colindancia Este")
    coloeste = fields.Char(string = "Colindancia Oeste")

    georeferencias = fields.One2many(
        'predios.georeferencia_ext',
        'predio_id',
        string="Georeferencias",
        help="Georeferencias asociadas al predio")
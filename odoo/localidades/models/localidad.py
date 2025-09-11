#localidades/models/localidad.py
from odoo import fields, models, api, _

class localidad(models.Model):
    _name = 'localidades.localidad'
    _rec_name = 'display_name'

    estado = fields.Selection(
        selection = [
            ("AGU", "Aguascalientes"),
            ("BCN", "Baja California Norte"),
            ("BCS", "Baja California Sur"),
            ("CAM", "Campeche"),
            ("CHH", "Chihuahua"),
            ("CHP", "Chiapas"),
            ("COA", "Coahuila"),
            ("COL", "Colima"),
            ("DIF", "Ciudad de México"),
            ("DUR", "Durango"),
            ("GRO", "Guerrero"),
            ("GUA", "Guanajuato"),
            ("HID", "Hidalgo"),
            ("JAL", "Jalisco"),
            ("MEX", "Estado de México"),
            ("MIC", "Michoacán"),
            ("MOR", "Morelos"),
            ("NAY", "Nayarit"),
            ("NLE", "Nuevo León"),
            ("OAX", "Oaxaca"),
            ("PUE", "Puebla"),
            ("QUE", "Queretaro"),
            ("ROO", "Quintana Roo"),
            ("SIN", "Sinaloa"),
            ("SLP", "San Luis Potosí"),
            ("SON", "Sonora"),
            ("TAM", "Tamaulipas"),
            ("TAB", "Tabasco"),
            ("TLA", "Tlaxcala"),
            ("VER", "Veracruz"),
            ("YUC", "Yucatán"),
            ("ZAC", "Zacatecas")
        ], string="Estado", required=True
    )
    municipio = fields.Many2one('localidades.municipio', string = "Municipio", required = True,
                                domain="[('estado', '=', estado)]")
    nombre = fields.Char(string = "Ciudad/Localidad", required = True, size = 32)

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.onchange('estado')
    def _onchange_estado(self):
        if self.estado:
            return {
                'domain': {
                    'municipio': [('estado', '=', self.estado)]
                },
                'value': {'municipio': False}  # Limpia el municipio al cambiar estado
            }
        return {'domain': {'municipio': []}}

    @api.depends('estado', 'nombre', 'municipio')
    def _compute_display_name(self):
        for record in self:
            
            estado_label = dict(self._fields['estado'].selection).get(record.estado)
            record.display_name = f"{record.nombre}, {record.municipio.nombre}, {estado_label}"

    def name_get(self):
        return [(record.id, record.display_name) for record in self]

    @api.model
    def create(self, vals):
        # Convertir a mayúsculas antes de crear
        if 'nombre' in vals:
            vals['nombre'] = vals['nombre'].capitalize() if vals['nombre'] else False
        return super().create(vals)
    
    def write(self, vals):
        # Convertir a mayúsculas antes de actualizar
        if 'nombre' in vals:
            vals['nombre'] = vals['nombre'].capitalize() if vals['nombre'] else False
        return super().write(vals)
    
    def action_back_to_list(self):
        """Regresa al listado de localidades."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Localidades'),
            'res_model': 'localidades.localidad',
            'view_mode': 'list,form',
            'target': 'current',
        }
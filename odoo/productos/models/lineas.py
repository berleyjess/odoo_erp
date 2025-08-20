#producto-models-lineas.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class lineas(models.Model):
    _name = 'lineasdeproducto'
    _description = 'Lineas de productos'
    _rec_name = 'display_name'

    name = fields.Char(string="Nombre", required=True)
    description = fields.Char(string="Descripción", size=30)

    parent = fields.Many2one('lineasdeproducto', string = "Linea Padre", domain="[('id', '!=', id)]")

    isparent = fields.Boolean(string = "Linea padre", default = False, required = True)

    display_name = fields.Char(string = "Label", store = True, compute='_gen_label')

    _sql_constraints = [
        ('unique_display_name', 'unique(display_name)', 'Ya existe una linea registrada.')
    ]

    @api.constrains('isparent', 'parent')
    def _checkparent(self):
        for i in self:
            if not i.isparent and not i.parent:
                raise ValidationError("Es necesario definir una Linea Padre!")
            else:
                padrename = ""
                if i.parent:
                    padrename = f"{i.parent.display_name}/"
                i.display_name = f"{padrename}{i.name}"

    @api.depends('isparent', 'parent')
    def _gen_label(self):
        for i in self:
            padrename = ""
            if i.parent:
                padrename = f"{i.parent.display_name}/"
            i.display_name = f"{padrename}{i.name}"

    @api.model
    def create(self, vals):
        # Convertir a mayúsculas antes de crear
        if 'name' in vals:
            vals['name'] = vals['name'].upper() if vals['name'] else False
        if 'description' in vals:
            vals['description'] = vals['description'].upper() if vals['description'] else False
        if 'display_name' in vals:
            vals['display_name'] = vals['display_name'].upper() if vals['display_name'] else False
        return super().create(vals)

    def write(self, vals):
        # Convertir a mayúsculas antes de actualizar
        if 'name' in vals:
            vals['name'] = vals['name'].upper() if vals['name'] else False
        if 'description' in vals:
            vals['description'] = vals['description'].upper() if vals['description'] else False
        if 'display_name' in vals:
            vals['display_name'] = vals['display_name'].upper() if vals['display_name'] else False
        return super().write(vals)


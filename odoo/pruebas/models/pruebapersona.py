from odoo import models, fields, api

class PruebaPersona(models.Model):
    _name = 'prueba.persona'
    _description = 'Persona de Prueba'

    nombre = fields.Char("Nombre")
    ine = fields.Char("Ine")
    rfc = fields.Char("RFC")
    superficie = fields.Char("Superfice")
    cultivo = fields.Char ("Cultivo")
    fechayhora = fields.Char ("Fecha y hora")
    ubicacion = fields.Char ("Ubicación")
    monto = fields.Char ("Monto")
    montoletra = fields.Char("Monto en letra")
    documento = fields.Char ("Documento")
    direccion = fields.Char ("Direccion")
    correo = fields.Char("Correo")
    activo = fields.Boolean("Activo")
    genero = fields.Selection([('masculino','Masculino'),('femenino','Femenino')], string="Género")
    salario = fields.Float("Salario")
    fecha_nacimiento = fields.Date("Fecha de Nacimiento")
    edad = fields.Integer("Edad", compute='_compute_edad', store=False)
    
    # Campo para controlar el modo de edición - AHORA CON STORE=TRUE
    is_editing = fields.Boolean("Modo Edición", default=False, store=True)

    @api.depends('fecha_nacimiento')
    def _compute_edad(self):
        for rec in self:
            if rec.fecha_nacimiento:
                rec.edad = fields.Date.today().year - rec.fecha_nacimiento.year
            else:
                rec.edad = 0

    @api.model
    def create(self, vals):
        """Al crear un nuevo registro, empezar en modo edición"""
        vals['is_editing'] = True
        return super().create(vals)

    def action_editar(self):
        """Activa el modo de edición"""
        self.ensure_one()
        self.write({'is_editing': True})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_save(self):
        """Guarda y sale del modo de edición"""
        self.ensure_one()
        self.write({'is_editing': False})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        """Cancela la edición y recarga el registro"""
        self.ensure_one()
        # Recargar desde la base de datos para descartar cambios
        self.invalidate_recordset()
        self.write({'is_editing': False})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_imprimir_pdf(self):
        """Genera el PDF del registro"""
        return self.env.ref('pruebas.action_report_persona_pdf').report_action(self)
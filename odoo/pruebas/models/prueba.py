from odoo import models, fields, api
from odoo.exceptions import UserError

class PruebaCliente(models.Model):
    _name = 'pruebas.prueba'
    _description = 'Cliente de Pruebas'

    name = fields.Char(string='Nombre', required=True)
    email = fields.Char(string='Correo Electrónico')
    phone = fields.Char(string='Teléfono')
    active = fields.Boolean(string='Activo', default=True)

    fecha_nacimiento = fields.Date(string="Fecha de Nacimiento")
    salario = fields.Monetary(string="Salario", currency_field="currency_id")
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id.id)
    rating = fields.Float(string="Calificación", digits=(2, 1))
    genero = fields.Selection([
        ('hombre', 'Hombre'),
        ('mujer', 'Mujer'),
        ('otro', 'Otro'),
    ], string="Género")
    foto = fields.Binary(string="Foto", attachment=True)
    notas_html = fields.Html(string="Notas HTML")
    tags = fields.Many2many('pruebas.tag', string='Etiquetas')
    parent_id = fields.Many2one('pruebas.prueba', string="Relacionado a")
    hijos_ids = fields.One2many('pruebas.prueba', 'parent_id', string='Contactos Relacionados')
    total_hijos = fields.Integer(string="Total de Relacionados", compute="_compute_total_hijos")
    edad = fields.Integer(string="Edad", compute='_compute_edad', store=True)
    documento = fields.Binary(string="Documento", filename="nombre_documento")
    nombre_documento = fields.Char(string="Nombre del Archivo")

    # Campo computado para verificar permisos
    puede_ver_salario = fields.Boolean(
        string='Puede ver salario',
        compute='_compute_puede_ver_salario',
        store=False
    )

    @api.depends()
    def _compute_puede_ver_salario(self):
        for rec in self:
            user = self.env.user
            rec.puede_ver_salario = user.has_group('security_roles.role_editor') or user.has_group('security_roles.role_manager')

    @api.depends('fecha_nacimiento')
    def _compute_edad(self):
        from datetime import date
        for rec in self:
            if rec.fecha_nacimiento:
                today = date.today()
                rec.edad = today.year - rec.fecha_nacimiento.year - (
                    (today.month, today.day) < (rec.fecha_nacimiento.month, rec.fecha_nacimiento.day)
                )
            else:
                rec.edad = 0

    @api.depends('hijos_ids')
    def _compute_total_hijos(self):
        for rec in self:
            rec.total_hijos = len(rec.hijos_ids)

    def action_mostrar_mensaje(self):
        """Acción disponible para todos los roles"""
        for rec in self:
            user_role = "Desconocido"
            if self.env.user.has_group('security_roles.role_manager'):
                user_role = "Administrador"
            elif self.env.user.has_group('security_roles.role_editor'):
                user_role = "Editor"
            elif self.env.user.has_group('security_roles.role_viewer'):
                user_role = "Solo Vista"
            
            raise UserError(f"¡Hola {user_role}! Registro: {rec.name}")

    def action_editar(self):
        """Acción disponible para Editor y Administrador"""
        if not (self.env.user.has_group('security_roles.role_editor') or 
                self.env.user.has_group('security_roles.role_manager')):
            raise UserError("No tienes permisos para editar este registro")
        
        for rec in self:
            raise UserError(f"Función editar ejecutada en: {rec.name}")

    def action_borrar(self):
        """Acción disponible solo para Administrador"""
        if not self.env.user.has_group('security_roles.role_manager'):
            raise UserError("Solo los administradores pueden borrar registros")
        
        for rec in self:
            # Aquí podrías implementar la lógica real de borrado
            raise UserError(f"Función borrar ejecutada en: {rec.name}")
    
    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        """
        Forzar la vista correcta según el grupo del usuario
        """
        if view_type == 'form' and not view_id:
            user = self.env.user
            
            # Determinar qué vista debe cargar según el grupo más específico
            if user.has_group('security_roles.role_manager'):
                # Manager ve la vista más completa
                view_id = self.env.ref('pruebas.view_prueba_form_manager').id
            elif user.has_group('security_roles.role_editor'):
                # Editor ve la vista intermedia
                view_id = self.env.ref('pruebas.view_prueba_form_editor').id
            elif user.has_group('security_roles.role_viewer'):
                # Viewer ve solo lectura
                view_id = self.env.ref('pruebas.view_prueba_form_readonly').id
        
        return super().get_view(view_id, view_type, **options)
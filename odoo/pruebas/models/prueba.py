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
    rating = fields.Selection(
        [
            ('0', 'Baja'),
            ('1', 'Media'),
            ('2', 'Alta')
        ],
        string="Calificación",
        default='1'
    )

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
            
            # PRIORIDAD: Primero revisar categorías especiales
            if user.has_group('security_roles.role_categoria_admin'):
                # Administrador del Sistema - Vista más completa
                view_id = self.env.ref('pruebas.view_prueba_form_categoria_admin').id
            elif user.has_group('security_roles.role_categoria_usuario'):
                # Usuario Final - Vista simplificada
                view_id = self.env.ref('pruebas.view_prueba_form_categoria_usuario').id
            # Si no tiene categorías especiales, usar roles normales
            elif user.has_group('security_roles.role_manager'):
                # Manager normal
                view_id = self.env.ref('pruebas.view_prueba_form_manager').id
            elif user.has_group('security_roles.role_editor'):
                # Editor normal
                view_id = self.env.ref('pruebas.view_prueba_form_editor').id
            elif user.has_group('security_roles.role_viewer'):
                # Viewer - solo lectura
                view_id = self.env.ref('pruebas.view_prueba_form_readonly').id
        
        return super().get_view(view_id, view_type, **options)
    
    def action_borrar(self):
        """Acción disponible solo para Administrador"""
        if not self.env.user.has_group('security_roles.role_manager'):
            raise UserError("Solo los administradores pueden borrar registros")
        
        for rec in self:
            # Aquí podrías implementar la lógica real de borrado
            raise UserError(f"Función borrar ejecutada en: {rec.name}")

    # ========== NUEVAS ACCIONES PARA FUNCIONES ESPECÍFICAS ==========
    
    def action_solicitar_acceso(self):
        """Acción para usuarios viewer - solicitar más permisos"""
        for rec in self:
            raise UserError(f"Solicitud de acceso enviada para el registro: {rec.name}")
    
    def action_solicitar_ayuda(self):
        """Acción para categoría usuario"""
        for rec in self:
            raise UserError(f"Solicitud de ayuda enviada para: {rec.name}")
    
    def action_duplicar(self):
        """Acción para editores - duplicar registro"""
        if not self.env.user.has_group('security_roles.role_editor'):
            raise UserError("No tienes permisos para duplicar registros")
        
        for rec in self:
            raise UserError(f"Registro duplicado: {rec.name}")
    
    def action_imprimir(self):
        """Acción para editores - imprimir registro"""
        for rec in self:
            raise UserError(f"Imprimiendo registro: {rec.name}")
    
    def action_cambiar_propietario(self):
        """Acción para managers - cambiar propietario"""
        if not self.env.user.has_group('security_roles.role_manager'):
            raise UserError("Solo los administradores pueden cambiar propietarios")
        
        for rec in self:
            raise UserError(f"Cambiando propietario de: {rec.name}")
    
    def action_historial_cambios(self):
        """Acción para managers - ver historial"""
        for rec in self:
            raise UserError(f"Mostrando historial de: {rec.name}")
    
    def action_backup(self):
        """Acción para managers - crear backup"""
        if not self.env.user.has_group('security_roles.group_funciones_criticas'):
            raise UserError("No tienes permisos para crear backups")
        
        for rec in self:
            raise UserError(f"Backup creado para: {rec.name}")
    
    def action_exportar_datos(self):
        """Acción para administradores de categoría"""
        if not self.env.user.has_group('security_roles.role_categoria_admin'):
            raise UserError("Solo administradores del sistema pueden exportar datos")
        
        for rec in self:
            raise UserError(f"Exportando datos de: {rec.name}")
    
    def action_auditoria(self):
        """Acción para administradores de categoría"""
        if not self.env.user.has_group('security_roles.role_categoria_admin'):
            raise UserError("Solo administradores del sistema pueden ver auditorías")
        
        for rec in self:
            raise UserError(f"Mostrando auditoría de: {rec.name}")

    # ========== NUEVAS ACCIONES PARA FUNCIONES ESPECÍFICAS ==========
    
    def action_solicitar_acceso(self):
        """Acción para usuarios viewer - solicitar más permisos"""
        for rec in self:
            raise UserError(f"Solicitud de acceso enviada para el registro: {rec.name}")
    
    def action_solicitar_ayuda(self):
        """Acción para categoría usuario"""
        for rec in self:
            raise UserError(f"Solicitud de ayuda enviada para: {rec.name}")
    
    def action_duplicar(self):
        """Acción para editores - duplicar registro"""
        if not self.env.user.has_group('security_roles.role_editor'):
            raise UserError("No tienes permisos para duplicar registros")
        
        for rec in self:
            raise UserError(f"Registro duplicado: {rec.name}")
    
    def action_imprimir(self):
        """Acción para editores - imprimir registro"""
        for rec in self:
            raise UserError(f"Imprimiendo registro: {rec.name}")
    
    def action_cambiar_propietario(self):
        """Acción para managers - cambiar propietario"""
        if not self.env.user.has_group('security_roles.role_manager'):
            raise UserError("Solo los administradores pueden cambiar propietarios")
        
        for rec in self:
            raise UserError(f"Cambiando propietario de: {rec.name}")
    
    def action_historial_cambios(self):
        """Acción para managers - ver historial"""
        for rec in self:
            raise UserError(f"Mostrando historial de: {rec.name}")
    
    def action_backup(self):
        """Acción para managers - crear backup"""
        if not self.env.user.has_group('security_roles.group_funciones_criticas'):
            raise UserError("No tienes permisos para crear backups")
        
        for rec in self:
            raise UserError(f"Backup creado para: {rec.name}")
    
    def action_exportar_datos(self):
        """Acción para administradores de categoría"""
        if not self.env.user.has_group('security_roles.role_categoria_admin'):
            raise UserError("Solo administradores del sistema pueden exportar datos")
        
        for rec in self:
            raise UserError(f"Exportando datos de: {rec.name}")
    
    def action_auditoria(self):
        """Acción para administradores de categoría"""
        if not self.env.user.has_group('security_roles.role_categoria_admin'):
            raise UserError("Solo administradores del sistema pueden ver auditorías")
        
        for rec in self:
            raise UserError(f"Mostrando auditoría de: {rec.name}")
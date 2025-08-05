from odoo import models, fields, api, _
from odoo.exceptions import ValidationError  

class ciclo(models.Model):
    _name = 'ciclos.ciclo'
    _description = 'Ciclos Agrícolas'
    _rec_name = 'label'

    periodo = fields.Selection(selection=
                               [
                                  ("OI", "Otoño-Invierno"),
                                  ("PV", "Primavera-Verano")
                               ], string="Periodo", required=True)
    finicio = fields.Date(string="Fecha de Inicio", required=True)
    ffinal = fields.Date(string="Fecha Final", required=True)

    label = fields.Char(compute='_deflabel', store = True, string="Ciclo")
    
    @api.depends('periodo', 'finicio', 'ffinal')
    def _deflabel(self):
        for record in self:
            periodo = record.periodo or ''
            anio_inicio = record.finicio.year if record.finicio else ''
            anio_final = record.ffinal.year if record.ffinal else ''
            if periodo and anio_inicio and anio_final:
                record.label = f"{periodo} {anio_inicio}-{anio_final}"
            else:
                record.label = ''

    @api.constrains('finicio', 'ffinal')
    def _check_dates(self):
        for rec in self:
            # Permite igualdad; cambia < por <= si quieres obligar que sea estrictamente mayor
            if rec.finicio and rec.ffinal and rec.ffinal < rec.finicio:
                raise ValidationError(
                    #El "_" sirve para traducir el mensaje, simplemente se puede poner la cadena sin el "_" si no se quiere traducir.
                    _("La Fecha Final (%s) no puede ser menor que la Fecha de Inicio (%s).") %
                    (rec.ffinal, rec.finicio)
                )
            
    _sql_constraints = [
        ('unique_label', 'unique(label)', 'Ya existe un ciclo con ese periodo y rango de años.')
    ]



    #PRUEBAS PERMISOS USUARIOS.

    

    

    usuario_editor_id = fields.Many2one(
        'res.users',
        string="Editor Responsable",
        domain=lambda self: [
            ('groups_id', 'in', self.env.ref('security_roles.role_editor').ids)
        ],
        default=lambda self: self.env.user.id,
        required=True,
    )

    usuario_lector_id = fields.Many2one(
        'res.users',
        string="Usuario solo vista",
        domain=lambda self: [
            ('groups_id', 'in', self.env.ref('security_roles.role_viewer').ids)
        ],
        default=lambda self: self.env.user.id,
        required=True,
    )

    

    editoresYManagers = fields.Many2one(
        'res.users',
        string="Administrador Responsable",
        domain=lambda self: [
            ('groups_id', 'in', (
                self.env.ref('security_roles.role_editor').ids +
                self.env.ref('security_roles.role_manager').ids
            ))
        ],
        default=lambda self: self.env.user.id,
        required=True,
    )


    current_user = fields.Char(string='Usuario actual', compute='_compute_current_user', store=False)

    

    @api.depends()
    def _compute_current_user(self):
        for rec in self:
            rec.current_user = self.env.user.name






    #TODOS LOS USUARIOS DE GRUPOS ADMINISTRADORES

    usuario_admin_id = fields.Many2one(
        'res.users',
        string="Responsable administrador",
        domain=lambda self: [
            ('groups_id', 'in', self._get_admin_groups_ids())
        ],
        default=lambda self: self.env.user.id,
        required=True,
    )

    @api.model
    def _get_admin_groups_ids(self):
        # Busca todos los grupos que pertenecen a la categoría "Administrador"
        categoria_admin = self.env.ref('security_roles.module_category_admin')
        admin_groups = self.env['res.groups'].search([
            ('category_id', '=', categoria_admin.id)
        ])
        return admin_groups.ids
    
    #TODOS LOS USUARIOS DE GRUPOS ADMINISTRADORES Y EDITORES

    usuario_admin_edit_id = fields.Many2one(
        'res.users',
        string="Responsable admin/editor",
        domain=lambda self: [('groups_id', 'in', self._get_admin_user_groups_ids())],
        default=lambda self: self.env.user.id,
        required=True,
    )

    @api.model
    def _get_admin_user_groups_ids(self):
        # Obtener las categorías de admin y usuario
        categoria_admin = self.env.ref('security_roles.module_category_admin')
        categoria_user = self.env.ref('security_roles.module_category_user')
        # Buscar todos los grupos que pertenezcan a esas categorías
        grupos = self.env['res.groups'].search([
            ('category_id', 'in', [categoria_admin.id, categoria_user.id])
        ])
        # Retornar todos los IDs de los grupos encontrados
        return grupos.ids

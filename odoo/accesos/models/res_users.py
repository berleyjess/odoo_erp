# -*- coding: utf-8 -*-
#models/res_users.py
from odoo import models, fields, api

class ResUsersAccesos(models.Model):
    _inherit = 'res.users'

    # Campo One2many para ver todos los accesos del usuario
    acceso_ids = fields.One2many(
        'accesos.acceso',
        'usuario_id',
        string='Accesos a Módulos',
        domain=[('active', '=', True)]
    )

    # Campo computado: cantidad de módulos accesibles
    accesos_count = fields.Integer(
        string='Módulos Accesibles',
        compute='_compute_accesos_count',
        store=True
    )

    # Campo computado: resumen de módulos
    modulos_accesibles = fields.Text(
        string='Resumen de Módulos',
        compute='_compute_modulos_accesibles'
    )

    @api.depends('acceso_ids', 'acceso_ids.active')
    def _compute_accesos_count(self):
        for user in self:
            user.accesos_count = len(user.acceso_ids.filtered('active'))

    @api.depends('acceso_ids', 'acceso_ids.modulo_id', 'acceso_ids.permisos_resumen')
    def _compute_modulos_accesibles(self):
        for user in self:
            lines = []
            for acc in user.acceso_ids.filtered('active'):
                lines.append(f"• {acc.modulo_id.name}: {acc.permisos_resumen}")
            user.modulos_accesibles = '\n'.join(lines) if lines else 'Sin accesos configurados'

    def action_view_accesos(self):
        """Abre la vista de accesos filtrada por el usuario"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Accesos de {self.name}',
            'res_model': 'accesos.acceso',
            'view_mode': 'list,form,kanban',
            'domain': [('usuario_id', '=', self.id)],
            'context': {'default_usuario_id': self.id},
        }
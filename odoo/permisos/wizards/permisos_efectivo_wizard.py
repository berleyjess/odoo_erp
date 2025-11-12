# -*- coding: utf-8 -*-
#permisos/wizards/permisos_efectivo_wizard.py
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class PermisosEfectivoWiz(models.TransientModel):
    _name = 'permisos.efectivo.wiz'
    _description = 'Wizard de permisos efectivos por usuario/contexto'
    _check_company_auto = False

    usuario_id = fields.Many2one('res.users', string='Usuario', required=True, ondelete='cascade')
    empresa_id = fields.Many2one('empresas.empresa', string='Empresa')
    sucursal_id = fields.Many2one('sucursales.sucursal', string='Sucursal',
                                  domain="[('empresa','=',empresa_id)]")
    line_ids = fields.One2many('permisos.efectivo.wiz.line', 'wiz_id', string='Permisos')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Defaults desde contexto (botón en usuarios)
        usuario = self.env['res.users'].browse(self.env.context.get('default_usuario_id'))
        if usuario and usuario.exists():
            res.setdefault('usuario_id', usuario.id)
        # No seteamos empresa/sucursal por defecto; el usuario las elige en el wizard.

        return res

    @api.onchange('usuario_id', 'empresa_id', 'sucursal_id')
    def _onchange_rebuild_lines(self):
        for wiz in self:
            wiz._rebuild_lines()

    def _rebuild_lines(self):
        for wiz in self:
            commands = [(5, 0, 0)]  # limpiar
            if not wiz.usuario_id:
                wiz.line_ids = commands
                continue

            Perm = self.env['permisos.permiso'].sudo()
            perms = Perm.search([('active', '=', True)], order='modulo_id, code')

            #Acceso = self.env['accesos.acceso'].sudo()

            for p in perms:
                allowed = wiz.usuario_id.has_perm(
                    p.modulo_id.code, p.code,
                    empresa_id=wiz.empresa_id.id if wiz.empresa_id else None,
                    sucursal_id=wiz.sucursal_id.id if wiz.sucursal_id else None,
                )
            
                # Helpers del usuario (gate/admin por MÓDULO, sin empresa)
                u = wiz.usuario_id
                # if not u._perm__has_gate(p.modulo_id.code):
                #     continue   # <- opcional si quieres ocultar módulos sin gate
                is_admin = u._perm__is_admin_gate(p.modulo_id.code)
            
                # override más específico
                dom_o = [
                    ('usuario_id', '=', wiz.usuario_id.id),
                    ('permiso_id', '=', p.id),
                    ('active', '=', True),
                ]
                if wiz.empresa_id:
                    dom_o += ['|', ('empresa_id', '=', False), ('empresa_id', '=', wiz.empresa_id.id)]
                else:
                    dom_o += [('empresa_id', '=', False)]
                if wiz.sucursal_id:
                    dom_o += ['|', ('sucursal_id', '=', False), ('sucursal_id', '=', wiz.sucursal_id.id)]
                else:
                    dom_o += [('sucursal_id', '=', False)]
                override = self.env['permisos.asignacion.permiso'].sudo().search(dom_o, limit=1)
                override_state = 'none'
                if override:
                    override_state = 'allow' if override.allow else 'deny'
            
                commands.append((0, 0, {
                    'wiz_id': wiz.id,
                    'seleccionar': False,
                    'permiso_id': p.id,
                    'modulo_code': p.modulo_id.code,
                    'permiso_code': p.code,
                    'permiso_name': p.name,
                    'allowed': bool(allowed or is_admin),
                    'override_state': override_state,
                }))


            wiz.line_ids = commands
        return True

    def action_rebuild_lines(self):
        """Método público para botón; reabre el wizard actualizado."""
        self._rebuild_lines()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'permisos.efectivo.wiz',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


    def _apply_override(self, allow=None, clear=False):
        self.ensure_one()
        if not self.usuario_id:
            raise ValidationError(_('Selecciona un usuario.'))
        selected = self.line_ids.filtered('seleccionar')
        if not selected:
            raise ValidationError(_('Marca al menos un permiso en la columna "✓".'))
    
        # Solo líneas válidas (con permiso_id); evita errores por filas vacías o manuales
        selected_valid = selected.filtered(lambda l: l.permiso_id)
        if not selected_valid:
            raise ValidationError(_('No hay permisos válidos seleccionados. Evita crear filas nuevas en la tabla.'))
    
        Asig = self.env['permisos.asignacion.permiso'].sudo()
        for ln in selected_valid:
            dom = [('usuario_id', '=', self.usuario_id.id), ('permiso_id', '=', ln.permiso_id.id)]
            dom += [('empresa_id', '=', self.empresa_id.id)] if self.empresa_id else [('empresa_id', '=', False)]
            dom += [('sucursal_id', '=', self.sucursal_id.id)] if self.sucursal_id else [('sucursal_id', '=', False)]
            existing = Asig.search(dom, limit=1)
            if clear:
                if existing:
                    existing.unlink()
            else:
                vals = {
                    'usuario_id': self.usuario_id.id,
                    'permiso_id': ln.permiso_id.id,
                    'allow': bool(allow),
                    'empresa_id': self.empresa_id.id if self.empresa_id else False,
                    'sucursal_id': self.sucursal_id.id if self.sucursal_id else False,
                }
                if existing:
                    existing.write({'allow': bool(allow), 'active': True})
                else:
                    Asig.create(vals)

        # Refrescar lista
        self._rebuild_lines()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'permisos.efectivo.wiz',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_allow_selected(self):
        return self._apply_override(allow=True, clear=False)

    def action_deny_selected(self):
        return self._apply_override(allow=False, clear=False)

    def action_clear_selected(self):
        return self._apply_override(clear=True)

class PermisosEfectivoWizLine(models.TransientModel):
    _name = 'permisos.efectivo.wiz.line'
    _description = 'Línea de permisos efectivos (wizard)'
    _check_company_auto = False

    wiz_id = fields.Many2one('permisos.efectivo.wiz', required=True, ondelete='cascade')
    seleccionar = fields.Boolean(string='✓')
    permiso_id = fields.Many2one('permisos.permiso', string='Permiso', readonly=True)
    modulo_code = fields.Char(string='Módulo', readonly=True)
    permiso_code = fields.Char(string='Código', readonly=True)
    permiso_name = fields.Char(string='Nombre', readonly=True)
    allowed = fields.Boolean(string='Permitido', readonly=True)
    override_state = fields.Selection(
        [('none', 'Sin override'), ('allow', 'Override: permitir'), ('deny', 'Override: denegar')],
        string='Override', readonly=True
    )

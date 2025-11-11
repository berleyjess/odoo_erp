# permisos/wizard/apply_security.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class PermApplySecurityWiz(models.TransientModel):
    _name = 'permisos.apply.security.wiz'
    _description = 'Aplicar seguridad (reconstruir grupos, menús, access y rules)'

    include_all_modules = fields.Boolean(default=True, string="Incluir todos los módulos pendientes")

    def action_apply(self):
        Mod = self.env['permisos.modulo'].sudo()
        mods = Mod.search([('dirty','=', True)]) if self.include_all_modules else Mod.browse()
        if not mods:
            return self._notify(_("No hay módulos pendientes"))

        for m in mods:
            self._sync_module(m)
            m.write({'dirty': False})

        return self._notify(_("Seguridad aplicada."))

    def _notify(self, msg):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Seguridad'), 'message': msg, 'type': 'success', 'sticky': False}
        }

    # --- Rutina principal por módulo ---
    def _sync_module(self, modulo):
        self._ensure_group(modulo)
        self._sync_menus(modulo)
        self._sync_model_access_and_rules(modulo)
        self._sync_group_members(modulo)

    def _ensure_group(self, modulo):
        Groups = self.env['res.groups'].sudo()
        xmlid = f"permisos.group_mod_{modulo.code}"
        if not modulo.group_id:
            grp = Groups.create({'name': f"[{modulo.code}] {modulo.name}"})
            modulo.group_id = grp.id
        # no gestiono xmlid aquí por simplicidad

    def _sync_menus(self, modulo):
        if not modulo.menu_ids:
            return
        for menu in modulo.menu_ids:
            menu.write({'groups_id': [(4, modulo.group_id.id)]})

    def _sync_model_access_and_rules(self, modulo):
        PermModModel = self.env['permisos.modulo.model'].sudo()
        Imodel  = self.env['ir.model'].sudo()
        IAccess = self.env['ir.model.access'].sudo()
        IRule   = self.env['ir.rule'].sudo()

        confs = PermModModel.search([('modulo_id','=', modulo.id)])
        # 1) ACCESS: máximos por grupo del módulo
        by_model = {}
        for c in confs:
            by_model.setdefault(c.model_id.id, {'read':False,'write':False,'create':False,'unlink':False})
            agg = by_model[c.model_id.id]
            agg['read']   = agg['read']   or c.perm_read
            agg['write']  = agg['write']  or c.perm_write
            agg['create'] = agg['create'] or c.perm_create
            agg['unlink'] = agg['unlink'] or c.perm_unlink

        for model_id, flags in by_model.items():
            model = Imodel.browse(model_id)
            # Borramos access previos de este grupo+modelo creados por este sincronizador (por simplicidad: match por group_id/model_id)
            old = IAccess.search([('group_id','=', modulo.group_id.id), ('model_id','=', model_id)])
            old.unlink()
            IAccess.create({
                'name': f"{modulo.code}:{model.model}",
                'model_id': model_id,
                'group_id': modulo.group_id.id,
                'perm_read':  1 if flags['read']   else 0,
                'perm_write': 1 if flags['write']  else 0,
                'perm_create':1 if flags['create'] else 0,
                'perm_unlink':1 if flags['unlink'] else 0,
            })

        # 2) RULES: por combinación módulo+modelo+operación con campos mapeados
        # Limpiamos reglas viejas de este módulo
        old_rules = IRule.search([('groups','in', modulo.group_id.id), ('active','=', True)])
        old_rules.unlink()

        for c in confs:
            model = c.model_id
            ef = c.empresa_field or 'empresa'
            sf = c.sucursal_field or 'sucursal'
            bf = c.bodega_field or 'bodega'

            # Record rule domain strings (se evalúan con 'user' disponible)
            base = "[(1,'=',1)]"  # sin filtro si global o si no hay campos
            if c.scope == 'empresa':
                base = f"[('{ef}','in', user.empresas_ids.ids)]"
            elif c.scope == 'empresa_sucursal':
                base = f"[('{ef}','in', user.empresas_ids.ids), ('{sf}','in', user.sucursales_ids.ids)]"
            elif c.scope == 'empresa_sucursal_bodega':
                base = f"[('{ef}','in', user.empresas_ids.ids), ('{sf}','in', user.sucursales_ids.ids), ('{bf}','in', user.bodegas_ids.ids)]"

            ops = []
            if c.perm_read:   ops.append(('Leer',   base))
            if c.perm_write:  ops.append(('Escribir', base))
            if c.perm_create: ops.append(('Crear',  base))
            if c.perm_unlink: ops.append(('Eliminar',base))

            for label, dom in ops:
                IRule.create({
                    'name': f"[{modulo.code}] {model.model} :: {label}",
                    'model_id': model.id,
                    'domain_force': dom,
                    'groups': [(4, modulo.group_id.id)],
                    'active': True,
                })

    def _sync_group_members(self, modulo):
        try:
            Acc = self.env['accesos.acceso'].sudo()
        except KeyError:
            return  # si 'accesos' no está instalado, omite este paso
        users = Acc.search([('modulo_id','=', modulo.id), ('active','=', True)]).mapped('usuario_id')
        modulo.group_id.users = [(6, 0, users.ids)]



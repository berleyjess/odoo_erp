#permisos/wizards/apply_security.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging, json
_logger = logging.getLogger(__name__)

class PermApplySecurityWiz(models.TransientModel):
    _name = 'permisos.apply.security.wiz'
    _description = 'Aplicar seguridad (reconstruir grupos, menús, access y rules)'

    include_all_modules = fields.Boolean(default=True, string="Incluir todos los módulos pendientes")

    def action_apply(self):
        Mod = self.env['permisos.modulo'].sudo()
        if self.include_all_modules:
            mods = Mod.search([('dirty', '=', True)])
        else:
            active_ids = self.env.context.get('active_ids') or []
            mods = active_ids and Mod.browse(active_ids) or Mod.browse()

        if not mods:
            return self._notify(_("No hay módulos pendientes"))

        results = []
        for m in mods:
            try:
                res = self._sync_module(m)   # dict con contadores
                self._log_apply(m, res)
                m.write({'dirty': False})
                line = "[{code}] menus={menus} acl={acl} rules={rules} users={users}".format(
                    code=m.code,
                    menus=res.get('menus_updated', 0),
                    acl=res.get('acl_replaced', 0),
                    rules=res.get('rules_created', 0),
                    users=res.get('users_in_group', 0),
                )
                results.append(line)
                _logger.info("Apply security %s -> %s", m.code, res)
            except Exception as e:
                _logger.exception("Apply security FAILED for %s", m.code)
                results.append(f"[{m.code}] ERROR: {e}")

        msg = _("Seguridad aplicada. Revisa el log técnico para detalle.\n") + "\n".join(results)
        return self._notify(msg)

    # ---------- helpers ----------
    def _notify(self, msg):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Seguridad'), 'message': msg, 'type': 'success', 'sticky': False}
        }

    def _sync_module(self, modulo):
        self._ensure_group(modulo)
        menus = self._sync_menus(modulo)
        acl, rules = self._sync_model_access_and_rules(modulo)
        users = self._sync_group_members(modulo)
        return {
            'module': modulo.code,
            'menus_updated': menus,
            'acl_replaced': acl,
            'rules_created': rules,
            'users_in_group': users,
        }

    def _ensure_group(self, modulo):
        Groups = self.env['res.groups'].sudo()
        if not modulo.group_id:
            grp = Groups.create({'name': f"[{modulo.code}] {modulo.name}"})
            modulo.group_id = grp.id
            _logger.info("[%-s] Grupo creado: %s (%s)", modulo.code, grp.name, grp.id)
        else:
            _logger.debug("[%-s] Grupo existente: %s (%s)", modulo.code, modulo.group_id.name, modulo.group_id.id)

    def _auto_discover_and_attach_menus(self, modulo):
        """Ligar menús automáticamente:
           1) por acciones (ir.actions.act_window.res_model) de los modelos configurados;
           2) si no hay, por nombre/código.
        """
        Menu = self.env['ir.ui.menu'].sudo()
        Act  = self.env['ir.actions.act_window'].sudo()
        Conf = self.env['permisos.modulo.model'].sudo()
    
        name = (modulo.name or '').strip()
        code = (modulo.code or '').strip()
    
        # 1) Por acciones de modelos configurados en permisos.modulo.model
        models = Conf.search([('modulo_id', '=', modulo.id)]).mapped('model_id.model')
        menu_ids = set()
        if models:
            acts = Act.search([('res_model', 'in', models)])
            if acts:
                menus = Menu.search([('action', 'in', acts.ids)])
                for root in menus:
                    menu_ids.update(Menu.search([('id', 'child_of', root.id)]).ids)
        if menu_ids:
            modulo.write({'menu_ids': [(6, 0, list(menu_ids))]})
            _logger.info("[%-s] %d menús ligados por acciones/res_model.", modulo.code, len(menu_ids))
            return len(menu_ids)
    
        # 2) Fallback por nombre/código
        candidates = Menu.search(['|', ('name', 'ilike', name), ('name', 'ilike', code)])
        if not candidates:
            _logger.warning("[%-s] No se encontraron menús para ligar (ni por acción ni por nombre/código).", modulo.code)
            return 0
    
        root = Menu.search([('name', 'ilike', name)], limit=1) or Menu.search([('name', 'ilike', code)], limit=1)
        if root:
            all_menus = Menu.search([('id', 'child_of', root.id)])
            modulo.write({'menu_ids': [(6, 0, all_menus.ids)]})
            _logger.info("[%-s] Menú raíz '%s' -> %d menús ligados (auto).", modulo.code, root.complete_name, len(all_menus))
            return len(all_menus)
    
        modulo.write({'menu_ids': [(6, 0, candidates.ids)]})
        _logger.info("[%-s] %d menús ligados (auto, coincidencia directa).", modulo.code, len(candidates))
        return len(candidates)



    def _sync_menus(self, modulo):
        if not modulo.menu_ids:
            self._auto_discover_and_attach_menus(modulo)

        if not modulo.menu_ids:
            _logger.warning("[%-s] Sin menús ligados al módulo; no hay nada que actualizar.", modulo.code)
            return 0

        updated = 0
        for menu in modulo.menu_ids:
            if modulo.group_id and modulo.group_id not in menu.groups_id:
                menu.write({'groups_id': [(4, modulo.group_id.id)]})
                updated += 1
                _logger.debug("[%-s] Grupo agregado al menú: %s", modulo.code, menu.complete_name)
        _logger.info("[%-s] Menús actualizados: %d / total vinculados: %d",
                     modulo.code, updated, len(modulo.menu_ids))
        return updated

    def _sync_model_access_and_rules(self, modulo):
        Conf = self.env['permisos.modulo.model'].sudo()
        Imodel  = self.env['ir.model'].sudo()
        IAccess = self.env['ir.model.access'].sudo()
        IRule   = self.env['ir.rule'].sudo()

        confs = Conf.search([('modulo_id', '=', modulo.id)])
        if not confs:
            _logger.info("[%-s] Sin filas en permisos.modulo.model -> no se generan ACL/Rules.", modulo.code)
            return 0, 0

        # --- ACL por modelo (flags agregados)
        by_model = {}
        for c in confs:
            agg = by_model.setdefault(c.model_id.id, {'read': False, 'write': False, 'create': False, 'unlink': False})
            agg['read']   = agg['read']   or c.perm_read
            agg['write']  = agg['write']  or c.perm_write
            agg['create'] = agg['create'] or c.perm_create
            agg['unlink'] = agg['unlink'] or c.perm_unlink

        acl_replaced = 0
        for model_id, flags in by_model.items():
            model = Imodel.browse(model_id)
            old = IAccess.search([('group_id', '=', modulo.group_id.id), ('model_id', '=', model_id)])
            if old:
                _logger.debug("[%-s] ACL previas eliminadas para %s: %d", modulo.code, model.model, len(old))
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
            acl_replaced += 1
            _logger.debug("[%-s] ACL creada para %s -> %s", modulo.code, model.model, flags)

        # --- Rules
        old_rules = IRule.search([('groups', 'in', modulo.group_id.id), ('active', '=', True)])
        cnt_old = len(old_rules)
        if cnt_old:
            old_rules.unlink()
            _logger.debug("[%-s] Record Rules previas eliminadas: %d", modulo.code, cnt_old)

        rules_created = 0
        for c in confs:
            ef = c.empresa_field or 'empresa'
            sf = c.sucursal_field or 'sucursal'
            bf = c.bodega_field or 'bodega'

            base = "[(1,'=',1)]"
            if c.scope == 'empresa':
                base = f"[('{ef}','in', user.empresas_ids.ids)]"
            elif c.scope == 'empresa_sucursal':
                base = f"[('{ef}','in', user.empresas_ids.ids), ('{sf}','in', user.sucursales_ids.ids)]"
            elif c.scope == 'empresa_sucursal_bodega':
                base = f"[('{ef}','in', user.empresas_ids.ids), ('{sf}','in', user.sucursales_ids.ids), ('{bf}','in', user.bodegas_ids.ids)]"

            ops = []
            if c.perm_read:   ops.append(('Leer',    base))
            if c.perm_write:  ops.append(('Escribir',base))
            if c.perm_create: ops.append(('Crear',   base))
            if c.perm_unlink: ops.append(('Eliminar',base))

            for label, dom in ops:
                self.env['ir.rule'].sudo().create({
                    'name': f"[{modulo.code}] {c.model_id.model} :: {label}",
                    'model_id': c.model_id.id,
                    'domain_force': dom,
                    'groups': [(4, modulo.group_id.id)],
                    'active': True,
                })
                rules_created += 1
        _logger.info("[%-s] ACL=%d, Rules creadas=%d", modulo.code, acl_replaced, rules_created)
        return acl_replaced, rules_created

    def _sync_group_members(self, modulo):
        Acc = self.env['accesos.acceso'].sudo()
        users = Acc.search([('modulo_id', '=', modulo.id), ('active', '=', True)]).mapped('usuario_id')
        modulo.group_id.users = [(6, 0, users.ids)]
        _logger.info("[%-s] Usuarios en grupo: %d -> %s",
                     modulo.code, len(users), ', '.join(users.mapped('login')))
        return len(users)

    def _log_apply(self, modulo, payload: dict):
        try:
            self.env['permisos.audit.log'].sudo().create({
                'action': 'apply_security',
                'model': 'permisos.modulo',
                'res_id': modulo.id,
                'vals_before': "{}",
                'vals_after': json.dumps(payload, ensure_ascii=False),
                'origin': 'apply_security',
            })
        except Exception:
            _logger.info("Seguridad aplicada a %s :: %s", modulo.code, payload)


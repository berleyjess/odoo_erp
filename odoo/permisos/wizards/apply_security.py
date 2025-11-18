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
        _logger.info("APPLY_SECURITY: include_all_modules=%s context.active_ids=%s",
                     self.include_all_modules, self.env.context.get('active_ids'))
        if self.include_all_modules:
            mods = Mod.search([('dirty', '=', True)])
        else:
            active_ids = self.env.context.get('active_ids') or []
            mods = active_ids and Mod.browse(active_ids) or Mod.browse()

        if not mods:
            _logger.info("APPLY_SECURITY: no hay módulos con dirty=True; nada que hacer.")
            return self._notify(_("No hay módulos pendientes"))
        
        _logger.info(
            "APPLY_SECURITY: módulos a procesar -> %s",
            [(m.id, m.code, m.name, m.dirty, m.menu_ids.ids) for m in mods]
        )

        results = []
        for m in mods:
            try:
                _logger.info(
                    "[%s] === INICIO _sync_module === id=%s name='%s' code='%s' dirty=%s menu_ids=%s",
                    m.code, m.id, m.name, m.code, m.dirty, m.menu_ids.ids
                )
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
                _logger.info("[%s] === FIN _sync_module ===", m.code)
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
        Conf = self.env['permisos.modulo.model'].sudo()

        _logger.info(
            "[%s] _sync_module(): estado inicial -> id=%s name='%s' code='%s' menu_ids=%s group_id=%s "
            "grp_read=%s grp_write=%s grp_create=%s grp_admin=%s conf_count=%s",
            modulo.code,
            modulo.id,
            modulo.name,
            modulo.code,
            modulo.menu_ids.ids,
            modulo.group_id.id if modulo.group_id else False,
            modulo.group_read_id.id if modulo.group_read_id else False,
            modulo.group_write_id.id if modulo.group_write_id else False,
            modulo.group_create_id.id if modulo.group_create_id else False,
            modulo.group_admin_id.id if modulo.group_admin_id else False,
            Conf.search_count([('modulo_id', '=', modulo.id)]),
        )

        self._ensure_group(modulo)

        _logger.info(
            "[%s] _sync_module(): después de _ensure_group -> group_id=%s read=%s write=%s create=%s admin=%s",
            modulo.code,
            modulo.group_id.id if modulo.group_id else False,
            modulo.group_read_id.id if modulo.group_read_id else False,
            modulo.group_write_id.id if modulo.group_write_id else False,
            modulo.group_create_id.id if modulo.group_create_id else False,
            modulo.group_admin_id.id if modulo.group_admin_id else False,
        )

        menus = self._sync_menus(modulo)
        _logger.info("[%s] _sync_module(): _sync_menus devolvió menus_updated=%s", modulo.code, menus)

        acl, rules = self._sync_model_access_and_rules(modulo)
        _logger.info("[%s] _sync_module(): _sync_model_access_and_rules -> acl=%s rules=%s",
                     modulo.code, acl, rules)

        users = self._sync_group_members(modulo)
        _logger.info("[%s] _sync_module(): _sync_group_members -> users_in_group=%s",
                     modulo.code, users)

        return {
            'module': modulo.code,
            'menus_updated': menus,
            'acl_replaced': acl,
            'rules_created': rules,
            'users_in_group': users,
        }

    def _ensure_group(self, modulo):
        Groups = self.env['res.groups'].sudo()

        # Base (compat)
        if not modulo.group_id:
            modulo.group_id = Groups.create({'name': f"[{modulo.code}] {modulo.name}"}).id
        _logger.info("[%s] _ensure_group(): inicio para modulo.id=%s", modulo.code, modulo.id)


        # Niveles
        if not modulo.group_read_id:
            modulo.group_read_id = Groups.create({'name': f"[{modulo.code}] {modulo.name} :: Lectura"}).id
            _logger.info("[%s] _ensure_group(): creado group_read_id=%s", modulo.code, modulo.group_read_id.id)
        if not modulo.group_write_id:
            modulo.group_write_id = Groups.create({'name': f"[{modulo.code}] {modulo.name} :: Edición"}).id
            _logger.info("[%s] _ensure_group(): creado group_write_id=%s", modulo.code, modulo.group_write_id.id)
        if not modulo.group_create_id:
            modulo.group_create_id = Groups.create({'name': f"[{modulo.code}] {modulo.name} :: Creación"}).id
            _logger.info("[%s] _ensure_group(): creado group_create_id=%s", modulo.code, modulo.group_create_id.id)
        if not modulo.group_admin_id:
            modulo.group_admin_id = Groups.create({'name': f"[{modulo.code}] {modulo.name} :: Admin"}).id
            _logger.info("[%s] _ensure_group(): creado group_admin_id=%s", modulo.code, modulo.group_admin_id.id)

        # Herencia (Admin ⇒ Creación ⇒ Edición ⇒ Lectura ⇒ Base)
        modulo.group_admin_id.implied_ids = [(6,0,[
            modulo.group_create_id.id,
            modulo.group_write_id.id,
            modulo.group_read_id.id,
            modulo.group_id.id,
        ])]
        modulo.group_create_id.implied_ids = [(6,0,[modulo.group_write_id.id, modulo.group_read_id.id, modulo.group_id.id])]
        modulo.group_write_id.implied_ids  = [(6,0,[modulo.group_read_id.id, modulo.group_id.id])]
        modulo.group_read_id.implied_ids   = [(6,0,[modulo.group_id.id])]
        _logger.info("[%s] _ensure_group(): fin", modulo.code)

    def _all_groups(self, modulo):
        groups = [g for g in [
            modulo.group_id,
            modulo.group_read_id,
            modulo.group_write_id,
            modulo.group_create_id,
            modulo.group_admin_id,
        ] if g]
        _logger.info("[%s] _all_groups(): %s", modulo.code, [(g.id, g.name) for g in groups])
        return groups

    def _auto_discover_and_attach_menus(self, modulo):
        """
        Ligar menús automáticamente a permisos.modulo SIN depender del módulo de negocio.

        Estrategia:
            - Si ya hay menu_ids en el módulo, se usan como raíces.
            - Si no hay:
                1) Buscar menús cuyo nombre contenga el nombre o el código del módulo
                   (ej. 'Créditos', 'creditos').
                2) Si hay más de uno, se toma el primero como raíz y se arrastran
                   todos sus hijos.
        """
        Menu = self.env['ir.ui.menu'].sudo()

        name = (modulo.name or '').strip()
        code = (modulo.code or '').strip()

        _logger.info(
            "[%s] AUTO-MENU: inicio -> modulo.id=%s name='%s' code='%s' menu_ids_actuales=%s",
            modulo.code, modulo.id, name, code, modulo.menu_ids.ids
        )

        # 0) Si ya tiene menús ligados, no inventamos raíces nuevas
        if modulo.menu_ids:
            roots = modulo.menu_ids
            _logger.info(
                "[%s] AUTO-MENU: usando menu_ids ya ligados como raíces: %s",
                modulo.code, [(m.id, m.name) for m in roots]
            )
        else:
            roots = Menu.browse()

            # 1) Buscar por nombre del menú (~ nombre del módulo)
            if name:
                roots = Menu.search([('name', 'ilike', name)], limit=1)
                _logger.info(
                    "[%s] AUTO-MENU: búsqueda por name ilike '%s' -> %s",
                    modulo.code, name, [(m.id, m.name) for m in roots]
                )

            # 2) Fallback por código si no encontró por nombre
            if not roots and code:
                roots = Menu.search([('name', 'ilike', code)], limit=1)
                _logger.info(
                    "[%s] AUTO-MENU: fallback por code ilike '%s' -> %s",
                    modulo.code, code, [(m.id, m.name) for m in roots]
                )

        if not roots:
            _logger.warning(
                "[%s] _auto_discover_and_attach_menus: no se encontraron menús para nombre='%s' / código='%s'.",
                modulo.code, name, code
            )
            return 0

        # Tomar raíz(s) encontrada(s) y TODOS sus hijos
        menu_ids = set()
        for root in roots:
            _logger.info(
                "[%s] AUTO-MENU: explorando hijos de root id=%s name='%s'",
                modulo.code, root.id, root.name
            )
            for m in Menu.search([('id', 'child_of', root.id)]):
                menu_ids.add(m.id)
                _logger.debug(
                    "[%s] AUTO-MENU: hijo encontrado id=%s name='%s'",
                    modulo.code, m.id, m.name
                )

        if not menu_ids:
            _logger.warning(
                "[%s] _auto_discover_and_attach_menus: raíz encontrada pero sin hijos.",
                modulo.code
            )
            return 0

        all_menus = Menu.browse(list(menu_ids))
        modulo.write({'menu_ids': [(6, 0, all_menus.ids)]})

        _logger.info(
            "[%s] %d menús ligados por menús del módulo '%s'.",
            modulo.code, len(all_menus), modulo.name
        )
        return len(all_menus)


    def _sync_menus(self, modulo):
        """
        Asegura el enlace:
            - ir.ui.menu.groups_id  (menú -> grupos)
            - res.groups.<campo_m2m_a_menu> (grupo -> menús)

        De esta forma:
            - El app aparece en el lanzador para los usuarios de esos grupos.
            - En el formulario del grupo se rellena la pestaña "Menús".
        """
        Menu = self.env['ir.ui.menu'].sudo()

        _logger.info(
            "[%s] _sync_menus(): inicio con menu_ids=%s",
            modulo.code, modulo.menu_ids.ids
        )
        # 1) Si el módulo no tiene menús aún, intentar descubrirlos automáticamente
        if not modulo.menu_ids:
            _logger.info("[%s] _sync_menus(): sin menu_ids, llamando a _auto_discover_and_attach_menus", modulo.code)
            self._auto_discover_and_attach_menus(modulo)
            _logger.info(
                "[%s] _sync_menus(): después de auto_discover, menu_ids=%s",
                modulo.code, modulo.menu_ids.ids
            )

        if not modulo.menu_ids:
            _logger.warning(
                "[%s] Sin menús ligados al módulo; no hay nada que actualizar.",
                modulo.code
            )
            return 0

        menus = modulo.menu_ids
        _logger.info(
            "[%s] _sync_menus(): trabajando sobre %d menús -> %s",
            modulo.code, len(menus), [(m.id, m.name) for m in menus]
        )
        group_list = self._all_groups(modulo)
        if not group_list:
            _logger.warning(
                "[%s] Sin grupos definidos (group_id / read / write / create / admin).",
                modulo.code
            )
            return 0

        group_ids = [g.id for g in group_list]
        menu_ids = menus.ids
        updated_links = 0

        # 2) Desde el lado de MENÚ: asegurar groups_id (menú -> grupos)
        for menu in menus:
            to_add = [gid for gid in group_ids if gid not in menu.groups_id.ids]
            if to_add:
                _logger.info(
                    "[%s] _sync_menus(): al menú id=%s name='%s' se le agregan grupos=%s",
                    modulo.code, menu.id, menu.name, to_add
                )
                menu.write({'groups_id': [(4, gid) for gid in to_add]})
                updated_links += len(to_add)

        # 3) Desde el lado de GRUPO: asegurar el M2M hacia ir.ui.menu
        #    (puede llamarse menu_access, menu_ids, etc).
        for g in group_list:
            m2m_field_name = False

            # Busca el primer campo Many2many que apunte a ir.ui.menu
            for fname in ('menu_access', 'menu_ids'):
                field = g._fields.get(fname)
                if field and getattr(field, 'comodel_name', None) == 'ir.ui.menu':
                    m2m_field_name = fname
                    break

            if not m2m_field_name:
                # En esta instalación no hay campo M2M hacia menú en res.groups
                _logger.info(
                    "[%s] _sync_menus(): el grupo id=%s name='%s' no tiene M2M hacia ir.ui.menu",
                    modulo.code, g.id, g.name
                )
                continue

            current = getattr(g, m2m_field_name)
            missing_menu_ids = [mid for mid in menu_ids if mid not in current.ids]
            if missing_menu_ids:
                _logger.info(
                    "[%s] _sync_menus(): al grupo id=%s name='%s' se le agregan menús=%s via campo %s",
                    modulo.code, g.id, g.name, missing_menu_ids, m2m_field_name
                )
                g.write({m2m_field_name: [(4, mid) for mid in missing_menu_ids]})

        _logger.info(
            "[%s] Menús actualizados: %d / total vinculados: %d",
            modulo.code, updated_links, len(menu_ids)
        )
        return updated_links





    def _sync_model_access_and_rules(self, modulo):
        Conf   = self.env['permisos.modulo.model'].sudo()
        Imodel = self.env['ir.model'].sudo()
        IAcc   = self.env['ir.model.access'].sudo()
        IRule  = self.env['ir.rule'].sudo()

        _logger.info("[%s] _sync_model_access_and_rules(): inicio", modulo.code)

        confs = Conf.search([('modulo_id','=', modulo.id)])

        _logger.info(
            "[%s] _sync_model_access_and_rules(): confs encontrados=%s",
            modulo.code,
            [{
                'id': c.id,
                'model': c.model_id.model,
                'scope': c.scope,
                'perm_r': c.perm_read,
                'perm_w': c.perm_write,
                'perm_c': c.perm_create,
                'perm_u': c.perm_unlink,
                'empresa_field': c.empresa_field,
                'sucursal_field': c.sucursal_field,
                'bodega_field': c.bodega_field,
            } for c in confs]
        )

        if not confs:
            _logger.info("[%s] Sin filas en permisos.modulo.model -> no se generan ACL/Rules.", modulo.code)
            return 0, 0

        # --- Borrar ACL previas de TODOS los grupos de nivel
        group_ids = [g.id for g in self._all_groups(modulo)]
        old_acl = IAcc.search([('group_id','in', group_ids)])
        _logger.info(
            "[%s] _sync_model_access_and_rules(): ACL previas encontradas=%d para grupos=%s",
            modulo.code, len(old_acl), group_ids
        )
        if old_acl:
            old_acl.unlink()

        acl_created = 0
        rules_created = 0

        # Para cada modelo configurado generamos ACL por nivel y una regla por operación con los grupos adecuados
        for c in confs:
            model = c.model_id
            _logger.info(
                "[%s] Procesando config id=%s para modelo '%s' (id=%s)",
                modulo.code, c.id, model.model, model.id
            )
            # ACL por nivel:
            #   READ:   r
            #   WRITE:  r,w
            #   CREATE: r,w,c
            #   ADMIN:  r,w,c,u
            def mkacl(group, r,w,cx,u):
                nonlocal acl_created
                if not group:
                    _logger.info(
                        "[%s] mkacl(): grupo vacío, se omite ACL r=%s w=%s c=%s u=%s",
                        modulo.code, r, w, cx, u
                    )
                    return
                rec = IAcc.create({
                    'name': f"{modulo.code}:{model.model}:{group.name}",
                    'model_id': model.id,
                    'group_id': group.id,
                    'perm_read':   1 if r else 0,
                    'perm_write':  1 if w else 0,
                    'perm_create': 1 if cx else 0,
                    'perm_unlink': 1 if u else 0,
                })
                acl_created += 1
                _logger.info(
                    "[%s] mkacl(): creada ACL id=%s para grupo '%s' r=%s w=%s c=%s u=%s",
                    modulo.code, rec.id, group.name, r, w, cx, u
                )


            r  = True
            w  = c.perm_write
            cx = c.perm_create
            u  = c.perm_unlink
            
            mkacl(modulo.group_read_id,   r, False, False, False)
            mkacl(modulo.group_write_id,  r, w,     False, False)
            mkacl(modulo.group_create_id, r, w,     cx,    False)
            mkacl(modulo.group_admin_id,  r, w,     cx,    u)   # <- Admin ya respeta perm_unlink


            # Record Rules (dominio por scope). Se adjuntan a TODOS los grupos de nivel.
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

            _logger.info(
                "[%s] Record Rules para modelo '%s': scope=%s domain=%s",
                modulo.code, model.model, c.scope, base
            )

            # Borra reglas anteriores de cualquiera de los grupos
            old_rules = IRule.search([('model_id','=', model.id), ('groups','in', group_ids)])
            _logger.info(
                "[%s] _sync_model_access_and_rules(): reglas previas para modelo %s = %d",
                modulo.code, model.model, len(old_rules)
            )
            if old_rules:
                old_rules.unlink()

            groups_m2m = [(6,0, group_ids)]
            # Crea UNA regla por operación que corresponda según permisos agregados del conf
            ops = []
            if c.perm_read:   ops.append(('Leer',    dict(perm_read=True)))
            if c.perm_write:  ops.append(('Escribir',dict(perm_write=True)))
            if c.perm_create: ops.append(('Crear',   dict(perm_create=True)))
            if c.perm_unlink: ops.append(('Eliminar',dict(perm_unlink=True)))
            if not ops:
                ops = [('Leer', dict(perm_read=True))]  # mínimo lectura si no se marcó nada

            for label, flags in ops:
                vals = {
                    'name': f"[{modulo.code}] {model.model} :: {label}",
                    'model_id': model.id,
                    'domain_force': base,
                    'groups': groups_m2m,
                    'active': True,
                    'perm_read':   flags.get('perm_read',   False),
                    'perm_write':  flags.get('perm_write',  False),
                    'perm_create': flags.get('perm_create', False),
                    'perm_unlink': flags.get('perm_unlink', False),
                }
                rule = IRule.create(vals)   # ⬅️ AQUÍ CREAMOS LA REGLA Y LA GUARDAMOS
                rules_created += 1
                _logger.info(
                    "[%s] Regla creada id=%s para modelo '%s' op='%s' flags=%s",
                    modulo.code, rule.id, model.model, label, flags
                )


        _logger.info("[%s] ACL=%d, Rules creadas=%d", modulo.code, acl_created, rules_created)
        return acl_created, rules_created


    def _sync_group_members(self, modulo):
        Acc = self.env['accesos.acceso'].sudo()
        accs = Acc.search([('modulo_id','=', modulo.id), ('active','=', True)])

        _logger.info(
            "[%s] _sync_group_members(): accesos encontrados=%s",
            modulo.code,
            [{
                'id': a.id,
                'user_id': a.usuario_id.id,
                'login': a.usuario_id.login,
                'can_read': a.can_read,
                'can_write': a.can_write,
                'can_create': a.can_create,
                'can_unlink': a.can_unlink,
                'is_admin': a.is_admin,
                'active': a.active,
            } for a in accs]
        )

        def users_of(fn):
            return accs.filtered(fn).mapped('usuario_id')

        users_read   = users_of(lambda a: a.can_read or a.can_write or a.can_create or a.can_unlink or a.is_admin)
        users_write  = users_of(lambda a: a.can_write or a.can_create or a.can_unlink or a.is_admin)
        users_create = users_of(lambda a: a.can_create or a.can_unlink or a.is_admin)
        users_admin  = users_of(lambda a: a.is_admin or a.can_unlink)

        _logger.info(
            "[%s] _sync_group_members(): users_read=%s users_write=%s users_create=%s users_admin=%s",
            modulo.code,
            users_read.ids, users_write.ids, users_create.ids, users_admin.ids
        )

        # Base: todos los que tienen algún acceso
        modulo.group_id.users        = [(6,0, accs.mapped('usuario_id').ids)]
        modulo.group_read_id.users   = [(6,0, users_read.ids)]     if modulo.group_read_id   else [(5,0,0)]
        modulo.group_write_id.users  = [(6,0, users_write.ids)]    if modulo.group_write_id  else [(5,0,0)]
        modulo.group_create_id.users = [(6,0, users_create.ids)]   if modulo.group_create_id else [(5,0,0)]
        modulo.group_admin_id.users  = [(6,0, users_admin.ids)]    if modulo.group_admin_id  else [(5,0,0)]

        _logger.info(
            "[%s] Usuarios: base=%d R=%d RW=%d RWC=%d ADM=%d",
            modulo.code,
            len(accs.mapped('usuario_id')),
            len(users_read), len(users_write), len(users_create), len(users_admin)
        )
        return len(accs)


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


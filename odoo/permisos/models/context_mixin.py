# -*- coding: utf-8 -*-
# permisos/models/context_mixin.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class PermModuleContextMixin(models.AbstractModel):
    _name = 'permisos.module.context.mixin'
    _description = 'Mixin de contexto por módulo (empresa / sucursal / bodega)'

    # Cada modelo que herede este mixin DEBE definir su código de módulo
    _perm_module_code = False

    # --- Campos SOLO informativos (no guardan nada en la BD) ---
    ctx_empresa_id = fields.Many2one(
        'empresas.empresa',
        string='Empresa (contexto)',
        compute='_compute_perm_ctx',
        store=False,
    )
    ctx_sucursal_id = fields.Many2one(
        'sucursales.sucursal',
        string='Sucursal (contexto)',
        compute='_compute_perm_ctx',
        store=False,
    )
    ctx_bodega_id = fields.Many2one(
        'bodegas.bodega',
        string='Bodega (contexto)',
        compute='_compute_perm_ctx',
        store=False,
    )
    ctx_context_label = fields.Char(
        string='Contexto actual',
        compute='_compute_perm_ctx',
        store=False,
    )

    # --------- default_get GENÉRICO ----------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        code = getattr(self, '_perm_module_code', False)
        if not code:
            return res

        emp_id, suc_id, bod_id = self.env.user._resolve_ctx_from_user_module(
            code, None, None, None
        )

        def _apply(field_name, value_id):
            if not value_id:
                return
            if field_name in fields_list and field_name in self._fields:
                field = self._fields[field_name]
                if not getattr(field, 'related', False):
                    res.setdefault(field_name, value_id)

        # Solo aplica si el modelo tiene esos campos y NO son related
        _apply('empresa', emp_id)
        _apply('sucursal', suc_id)
        _apply('bodega_id', bod_id)

        _logger.info(
            "CTX.default_get(%s): modulo=%s -> empresa=%s sucursal=%s bodega=%s",
            self._name, code, emp_id, suc_id, bod_id,
        )
        return res

    # --------- Botón GENÉRICO para abrir el wizard ----------
    def action_open_perm_context(self):
        self.ensure_one()
        code = getattr(self, '_perm_module_code', False)
        if not code:
            raise ValidationError(
                _("El modelo %s hereda permisos.module.context.mixin "
                  "pero no tiene _perm_module_code definido.") % self._name
            )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contexto del módulo'),
            'res_model': 'permisos.set.context.wiz',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_modulo_code': code,
                'active_model': self._name,
                'active_id': self.id,
                'active_ids': self.ids,
            },
        }

    # --------- Hook genérico que llama el wizard ----------
    def _on_perm_context_applied(self, empresa=None, sucursal=None, bodega=None):
        """
        Implementación base reutilizable:
        - Si el modelo tiene campos Many2one normales empresa/sucursal/bodega_id
          y NO son related, los rellena.
        """
        for rec in self:
            vals = {}
            if empresa and 'empresa' in rec._fields and not rec._fields['empresa'].related:
                vals['empresa'] = empresa.id
            if sucursal and 'sucursal' in rec._fields and not rec._fields['sucursal'].related:
                vals['sucursal'] = sucursal.id
            if bodega and 'bodega_id' in rec._fields and not rec._fields['bodega_id'].related:
                vals['bodega_id'] = bodega.id

            if vals:
                _logger.info(
                    "CTX._on_perm_context_applied(%s): write(%s)", rec._name, vals
                )
                rec.write(vals)
            else:
                _logger.info(
                    "CTX._on_perm_context_applied(%s): sin cambios (campos related o inexistentes).",
                    rec._name,
                )

    # --------- Compute de los campos informativos ----------
    def _compute_perm_ctx(self):
        code = getattr(self, '_perm_module_code', False)
        if not code:
            for rec in self:
                rec.ctx_empresa_id = False
                rec.ctx_sucursal_id = False
                rec.ctx_bodega_id = False
                rec.ctx_context_label = _("Sin contexto")
            return

        emp_id, suc_id, bod_id = self.env.user._resolve_ctx_from_user_module(
            code, None, None, None
        )

        Empresa = self.env['empresas.empresa']
        Sucursal = self.env['sucursales.sucursal']
        Bodega = self.env['bodegas.bodega']

        emp = Empresa.browse(emp_id) if emp_id else Empresa.browse()
        suc = Sucursal.browse(suc_id) if suc_id else Sucursal.browse()
        bod = Bodega.browse(bod_id) if bod_id else Bodega.browse()

        parts = []
        if emp:
            parts.append(emp.display_name)
        if suc:
            parts.append(suc.display_name)
        if bod:
            parts.append(bod.display_name)
        label = " / ".join(parts) if parts else _("Sin contexto definido")

        for rec in self:
            rec.ctx_empresa_id = emp
            rec.ctx_sucursal_id = suc
            rec.ctx_bodega_id = bod
            rec.ctx_context_label = label

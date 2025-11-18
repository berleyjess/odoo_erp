# permisos/wizard/set_context.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class PermSetContextWiz(models.TransientModel):
    _name = 'permisos.set.context.wiz'
    _description = 'Definir contexto por módulo para el usuario actual'
    _check_company_auto = False

    modulo_id   = fields.Many2one('permisos.modulo', string='Módulo', required=True)
    empresa_id  = fields.Many2one('empresas.empresa', string='Empresa')
    sucursal_id = fields.Many2one('sucursales.sucursal', string='Sucursal',
                                  domain="[('empresa','=',empresa_id)]")
    bodega_id   = fields.Many2one('bodegas.bodega', string='Bodega',
                                  domain="[('empresa_id','=',empresa_id)]")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        code = self.env.context.get('default_modulo_code')
        if code and not res.get('modulo_id'):
            mod = self.env['permisos.modulo'].sudo().search([('code','=', code)], limit=1)
            if mod:
                res['modulo_id'] = mod.id
        # precargar contexto previo si existe
        if res.get('modulo_id'):
            ctx = self.env['permisos.user.context'].sudo().search([
                ('usuario_id','=', self.env.user.id),
                ('modulo_id','=', res['modulo_id'])
            ], limit=1)
            if ctx:
                res.setdefault('empresa_id',  ctx.empresa_id.id or False)
                res.setdefault('sucursal_id', ctx.sucursal_id.id or False)
                res.setdefault('bodega_id',   ctx.bodega_id.id or False)
        return res

    def action_apply(self):
        self.ensure_one()
        Ctx = self.env['permisos.user.context'].sudo()
        rec = Ctx.search([
            ('usuario_id', '=', self.env.user.id),
            ('modulo_id',  '=', self.modulo_id.id),
        ], limit=1)

        vals = {
            'usuario_id': self.env.user.id,
            'modulo_id':  self.modulo_id.id,
            'empresa_id': self.empresa_id.id or False,
            'sucursal_id': self.sucursal_id.id or False,
            'bodega_id':  self.bodega_id.id or False,
        }

        if rec:
            rec.write(vals)
        else:
            rec = Ctx.create(vals)

        _logger.info(
            "PERMISOS.SET.CONTEXT: user=%s modulo=%s -> empresa=%s sucursal=%s bodega=%s (ctx_id=%s)",
            self.env.user.id,
            self.modulo_id.code,
            self.empresa_id.id or False,
            self.sucursal_id.id or False,
            self.bodega_id.id or False,
            rec.id,
        )

        # Hook al modelo activo (opcional)
        active_model = self.env.context.get('active_model')
        active_id    = self.env.context.get('active_id')
        if active_model and active_id:
            record = self.env[active_model].browse(active_id)
            if record and record.exists():
                hook = getattr(record, '_on_perm_context_applied', None)
                if hook:
                    hook(
                        empresa=self.empresa_id,
                        sucursal=self.sucursal_id,
                        bodega=self.bodega_id,
                    )

        return {'type': 'ir.actions.act_window_close'}

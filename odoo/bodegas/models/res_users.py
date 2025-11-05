from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    # Admin del esquema de accesos (si tiene algún acceso con is_admin)
    acceso_is_admin = fields.Boolean(
        compute='_compute_acceso_bodegas', compute_sudo=True
    )
    # Bodegas que puede LEER / EDITAR (WRITE/UNLINK)
    acceso_bodega_ids_read = fields.Many2many(
        'bodegas.bodega', compute='_compute_acceso_bodegas',
        string='Bodegas permitidas (leer)', compute_sudo=True
    )
    acceso_bodega_ids_write = fields.Many2many(
        'bodegas.bodega', compute='_compute_acceso_bodegas',
        string='Bodegas permitidas (editar/borrar)', compute_sudo=True
    )

    def _compute_acceso_bodegas(self):
        Acceso = self.env['accesos.acceso'].sudo()
        Bodega = self.env['bodegas.bodega'].sudo()
        for u in self:
            accs = Acceso.search([('usuario_id', '=', u.id), ('active', '=', True)])
            is_admin = any(a.is_admin for a in accs)
            u.acceso_is_admin = is_admin
            if is_admin:
                todas = Bodega.search([])
                u.acceso_bodega_ids_read = todas
                u.acceso_bodega_ids_write = todas
            else:
                # Leer: cualquier acceso
                u.acceso_bodega_ids_read = accs.mapped('bodega_id')
                # Escribir/Borrar: requiere can_write o is_admin en el acceso
                u.acceso_bodega_ids_write = accs.filtered(
                    lambda a: a.can_write or a.is_admin
                ).mapped('bodega_id')

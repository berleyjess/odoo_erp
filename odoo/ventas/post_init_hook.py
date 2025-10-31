#ventas/post_init_hook.py
from odoo import api, SUPERUSER_ID

def post_init_hook(cr, registry):
    """Sanea create_uid/write_uid que apunten a usuarios inexistentes
    para evitar valores _unknown al leer la lista/form."""
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Toma un usuario válido (admin) por xmlid; si no existe, usa cualquier usuario
    admin = (env.ref('base.user_admin', raise_if_not_found=False)
             or env.ref('base.user_root', raise_if_not_found=False)
             or env['res.users'].sudo().search([], limit=1))
    admin_id = admin.id

    # Tablas propias que queremos sanear (agrega aquí más si hace falta)
    tablas = (
        'ventas_venta',
        'transacciones_transaccion',
    )

    for tbl in tablas:
        # create_uid colgado -> admin
        cr.execute(f"""
            UPDATE {tbl} t
               SET create_uid = %s
             WHERE create_uid IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM res_users u WHERE u.id = t.create_uid)
        """, (admin_id,))
        # write_uid colgado -> admin
        cr.execute(f"""
            UPDATE {tbl} t
               SET write_uid = %s
             WHERE write_uid IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM res_users u WHERE u.id = t.write_uid)
        """, (admin_id,))
    # se ejecuta dentro de la transacción de instalación; no hace falta commit explícito

# /facturacion_ui/services/mapper.py
from odoo import _

def map_mx_edi_fields(move, *, uso=None, metodo=None, forma=None):
    if uso and 'l10n_mx_edi_usage' in move._fields:
        try:
            move.l10n_mx_edi_usage = uso
        except Exception:
            pass

    if metodo:
        for f in ('l10n_mx_edi_payment_policy', 'l10n_mx_edi_payment_method'):
            if f in move._fields:
                try:
                    setattr(move, f, metodo)
                    break
                except Exception:
                    pass

    if forma:
        # Primero intenta M2O por code
        assigned = False
        for m2o in ('l10n_mx_edi_payment_method_id', 'l10n_mx_edi_forma_pago_id'):
            if m2o in move._fields:
                field = move._fields[m2o]
                comodel = move.env[field.comodel_name]
                pm = comodel.search([('code', '=', forma)], limit=1)
                if pm:
                    setattr(move, m2o, pm.id)
                    assigned = True
                    break
        # Fallback a selection si no hay M2O/registro
        if not assigned and 'l10n_mx_edi_forma_pago' in move._fields:
            try:
                move.l10n_mx_edi_forma_pago = forma
            except Exception:
                pass


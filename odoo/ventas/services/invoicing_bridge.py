from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


def _find_or_create_partner(env, cliente):
    """Return a res.partner for the given clientes.cliente.

    - Looks up by VAT (RFC) first, then by name.
    - If not found, creates a minimal partner with MX country.
    """
    Partner = env['res.partner']
    Country = env['res.country']
    rfc = (getattr(cliente, 'rfc', False) or '').strip().upper() or False
    name = getattr(cliente, 'nombre', False) or getattr(cliente, 'display_name', False) or 'Cliente'
    partner = False
    if rfc:
        partner = Partner.search([('vat', '=', rfc)], limit=1)
    if not partner:
        # try by exact name
        partner = Partner.search([('name', '=', name)], limit=1)
    if not partner:
        mx = Country.search([('code', '=', 'MX')], limit=1)
        partner = Partner.create({
            'name': name,
            'vat': rfc or False,
            'country_id': mx.id if mx else False,
            'type': 'invoice',
        })
    return partner


def _map_mx_edi_fields(move, *, uso_cfdi=None, metodo=None, forma=None, relacion_tipo=None, related_uuids=None):
    """Best-effort mapping of MX EDI fields for both OCA and Enterprise flavours.

    All writes are guarded by presence of the field/model to keep Community safe
    even when MX EDI modules are not present.
    """
    env = move.env

    # Uso CFDI (selection on account.move in both stacks)
    if uso_cfdi and 'l10n_mx_edi_usage' in move._fields:
        try:
            move.l10n_mx_edi_usage = uso_cfdi
        except Exception:
            # Some stacks use a Many2one to a catalog, accept selection fallback
            pass

    # Método de pago (PUE/PPD)
    for field_name in ('l10n_mx_edi_payment_policy', 'l10n_mx_edi_payment_method'):  # try common names
        if metodo and field_name in move._fields:
            try:
                setattr(move, field_name, metodo)
                break
            except Exception:
                pass

    # Forma de pago (01, 03, 99...)
    # OCA usually stores a Many2one model with code; enterprise may store selection or m2o.
    # Try model lookup if present.
    if forma:
        # M2O model attempt
        for m2o_field in ('l10n_mx_edi_payment_method_id', 'l10n_mx_edi_forma_pago_id'):
            if m2o_field in move._fields:
                field = move._fields[m2o_field]
                comodel = env[field.comodel_name] if getattr(field, 'comodel_name', False) else False
                if comodel:
                    # Find by code
                    pm = comodel.search([('code', '=', forma)], limit=1)
                    if pm:
                        setattr(move, m2o_field, pm.id)
                        break
        # Selection fallback
        for sel_field in ('l10n_mx_edi_forma_pago',):
            if sel_field in move._fields:
                try:
                    setattr(move, sel_field, forma)
                    break
                except Exception:
                    pass

    # Relaciones CFDI en OCA: field 'l10n_mx_edi_origin' e.g. "01|UUID1,UUID2"
    if relacion_tipo and related_uuids:
        join = f"{relacion_tipo}|{','.join(related_uuids)}"
        if 'l10n_mx_edi_origin' in move._fields:
            move.l10n_mx_edi_origin = join


def _find_income_account(env):
    """Find a generic income account for invoice lines when no product mapping exists."""
    Account = env['account.account']
    company = env.company
    acc = Account.search([
        ('company_id', '=', company.id),
        ('internal_group', '=', 'income'),
        ('deprecated', '=', False),
    ], limit=1)
    if not acc:
        raise ValidationError(_('No se encontró una cuenta de ingresos para la empresa. Configura el plan contable.'))
    return acc


def _tax_by_percent(env, percent):
    """Find an account.tax by percent for sales. percent is 0-100.
    Returns recordset or empty.
    """
    Tax = env['account.tax']
    taxes = Tax.search([
        ('type_tax_use', '=', 'sale'),
        ('amount_type', '=', 'percent'),
        ('amount', '=', percent),
        ('company_id', '=', env.company.id),
        ('active', '=', True),
    ], limit=1)
    return taxes


def _build_invoice_lines(env, sale):
    """Map ventas.venta.detalle (transacciones.transaccion) to account.move.invoice_line_ids commands."""
    commands = []
    income = _find_income_account(env)
    Product = env['product.product']
    for line in sale.detalle:
        if not line.producto_id or (line.cantidad or 0.0) <= 0:
            continue
        # Try to map custom product to product.product by internal code or name
        product_ref = None
        # Prefer explicit mapping field if present
        prod = line.producto_id
        ensure_method = getattr(prod, 'ensure_product_product', None)
        if ensure_method:
            try:
                product_ref = ensure_method()
            except Exception:
                product_ref = prod.product_id if hasattr(prod, 'product_id') else None
        code = getattr(line.producto_id, 'codigo', False)
        if code:
            product_ref = Product.search([('default_code', '=', str(code))], limit=1)
        if not product_ref:
            pname = getattr(line.producto_id, 'name', False)
            if pname:
                product_ref = Product.search([('name', '=', pname)], limit=1)
        taxes = []
        iva_ratio = getattr(line, 'iva', 0.0) or 0.0
        ieps_ratio = getattr(line, 'ieps', 0.0) or 0.0
        if iva_ratio:
            t = _tax_by_percent(env, round(iva_ratio * 100, 2))
            if t:
                taxes.append(t.id)
        if ieps_ratio:
            t = _tax_by_percent(env, round(ieps_ratio * 100, 2))
            if t:
                taxes.append(t.id)

        line_vals = {
            'name': line.producto_id.name,
            'quantity': line.cantidad,
            'price_unit': line.precio,
            'account_id': income.id,
            'tax_ids': [(6, 0, taxes)] if taxes else False,
        }
        if product_ref:
            line_vals['product_id'] = product_ref.id
        commands.append((0, 0, line_vals))
    if not commands:
        raise ValidationError(_('La venta no tiene líneas válidas para facturar.'))
    return commands


def create_invoice_from_sale(sale, *, tipo='I', uso_cfdi=None, metodo=None, forma=None, relacion_tipo=None, relacion_moves=None):
    """Create an account.move from ventas.venta and return it.

    - tipo: 'I' (out_invoice) or 'E' (out_refund)
    - relacion_moves: iterable of account.move records (or objects with cfdi uuids) to relate (for notes/egresos)
    """
    env = sale.env
    Move = env['account.move']

    if not env.registry.ready:
        raise UserError(_('El entorno ORM no está listo.'))

    partner = _find_or_create_partner(env, sale.cliente)
    move_type = 'out_invoice' if tipo == 'I' else 'out_refund'

    # Payment term by method (best-effort)
    payment_term_id = False
    if hasattr(sale, 'metododepago'):
        Term = env['account.payment.term']
        metodo = (sale.metododepago or '').upper()
        if metodo == 'PUE':
            pt = Term.search([('name', 'ilike', 'Contado')], limit=1) or Term.search([('name', 'ilike', 'Immediate')], limit=1)
            payment_term_id = pt.id or False
        elif metodo == 'PPD':
            pt = Term.search([('name', 'ilike', '30')], limit=1) or Term.search([('name', 'ilike', 'Credito')], limit=1)
            payment_term_id = pt.id or False

    vals = {
        'move_type': move_type,
        'partner_id': partner.id,
        'currency_id': env.company.currency_id.id,
        'invoice_origin': sale.codigo or sale.display_name,
        'invoice_date': sale.fecha or fields.Date.context_today(sale),
        'invoice_line_ids': _build_invoice_lines(env, sale),
    }
    if payment_term_id:
        vals['invoice_payment_term_id'] = payment_term_id
    # Link to original invoice for refunds when provided
    if move_type == 'out_refund' and relacion_moves:
        try:
            first = relacion_moves[0] if hasattr(relacion_moves, '__getitem__') else relacion_moves[:1]
            original = first[0] if isinstance(first, (list, tuple)) else first
            if original:
                vals['reversed_entry_id'] = original.id
        except Exception:
            pass
    move = Move.create(vals)

    # EDI fields
    related_uuids = []
    if relacion_moves:
        for rm in relacion_moves:
            # try read OCA uuid field or attachment
            uuid_val = False
            if hasattr(rm, 'l10n_mx_edi_cfdi_uuid') and rm.l10n_mx_edi_cfdi_uuid:
                uuid_val = rm.l10n_mx_edi_cfdi_uuid
            elif hasattr(rm, 'name'):
                uuid_val = False
            if uuid_val:
                related_uuids.append(uuid_val)

    _map_mx_edi_fields(move,
                       uso_cfdi=uso_cfdi,
                       metodo=metodo,
                       forma=forma,
                       relacion_tipo=relacion_tipo,
                       related_uuids=related_uuids)

    return move

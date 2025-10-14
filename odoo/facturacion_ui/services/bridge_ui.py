#facturacion_ui/services/bridge_ui.py
# Bridge para crear facturas desde UI (similar a facturacion/services/bridge.py)
from odoo import models, _
from odoo.exceptions import ValidationError


class InvoicingBridgeFromUI(models.AbstractModel):
    _name = 'ventas.invoicing.bridge'
    _description = 'Bridge para facturación desde UI'

    def create_move_from_virtual_sale(self, sale_like, *, tipo='I', uso=None, metodo=None, forma=None):
        """
        sale_like: dict con:
            - partner_id (res.partner)
            - empresa_id (empresas.empresa)
            - transacciones: iterable con objetos que tengan:
                .producto_id.name, .cantidad, .precio, .iva (0.16), .ieps (0.08) (ratios)
        """
        env = self.env
        Move = env['account.move']
        partner = env['res.partner'].browse(sale_like['partner_id'])
        empresa = env['empresas.empresa'].browse(sale_like.get('empresa_id'))
        if not empresa:
            raise ValidationError(_("Debes indicar 'empresa_id' en sale_like."))

        # Compañía técnica para contabilidad (no depende del login)
        ICP = env['ir.config_parameter'].sudo()
        tech_company_id = int(ICP.get_param('facturacion_ui.technical_company_id', '0') or 0)
        if not tech_company_id:
            raise ValidationError(_("Configura el parámetro del sistema 'facturacion_ui.technical_company_id' con la compañía contable técnica."))
        company = env['res.company'].browse(tech_company_id)



        # Cuentas / impuestos en contexto de la compañía de la venta
        Account = env['account.account'].with_company(company).with_context(allowed_company_ids=[company.id])
        Tax = env['account.tax'].with_company(company).with_context(allowed_company_ids=[company.id])

        # === Helper: buscar cuenta de ingresos ===
        def _find_income_account():
            domain = [('deprecated', '=', False)]
            if 'account_type' in Account._fields:
                domain.append(('account_type', 'in', ('income', 'income_other')))
            else:
                # fallback stacks viejos (user_type_id)
                AType = env['account.account.type']
                ats = AType.search([('type', 'in', ('income', 'other_income'))])
                if 'user_type_id' in Account._fields and ats:
                    domain.append(('user_type_id', 'in', ats.ids))
            # multiempresa: ambos esquemas (company_id / company_ids)
            if 'company_ids' in Account._fields:
                domain.append(('company_ids', 'in', [company.id]))
            elif 'company_id' in Account._fields:
                domain.append(('company_id', '=', company.id))
            acc = Account.search(domain, limit=1, order='code asc')
            if not acc:
                raise ValidationError(_("No se encontró una cuenta de ingresos para la compañía %s.") % company.display_name)
            return acc

        # === Helper: impuesto por porcentaje y compañía ===
        def _tax_by_percent(percent):
            # percent: 16.0, 8.0, etc.
            dom = [
                ('type_tax_use', '=', 'sale'),
                ('amount_type', '=', 'percent'),
                ('amount', '=', round(percent, 2)),
                ('active', '=', True),
            ]
            if 'company_id' in Tax._fields:
                dom.append(('company_id', '=', company.id))  # ⬅️ evita impuestos de otra compañía
            return Tax.search(dom, limit=1)

        income = _find_income_account()

        # === Mapear líneas ===
        lines_cmd = []
        for t in sale_like['transacciones']:
            taxes = []
            iva_ratio = float(getattr(t, 'iva', 0.0) or 0.0)
            ieps_ratio = float(getattr(t, 'ieps', 0.0) or 0.0)

            if iva_ratio:
                iva = _tax_by_percent(iva_ratio * 100.0)
                if not iva:
                    raise ValidationError(
                        _("Configura el impuesto de IVA %(rate)s%% para la compañía %(c)s.")
                        % {'rate': int(round(iva_ratio * 100)), 'c': company.display_name}
                    )
                taxes.append(iva.id)

            if ieps_ratio:
                ieps = _tax_by_percent(ieps_ratio * 100.0)
                if not ieps:
                    raise ValidationError(
                        _("Configura el impuesto de IEPS %(rate)s%% para la compañía %(c)s.")
                        % {'rate': int(round(ieps_ratio * 100)), 'c': company.display_name}
                    )
                taxes.append(ieps.id)

            lines_cmd.append((0, 0, {
                'name': getattr(t.producto_id, 'name', False) or _('Producto'),
                'quantity': getattr(t, 'cantidad', 0.0) or 0.0,
                'price_unit': getattr(t, 'precio', 0.0) or 0.0,
                'account_id': income.id,
                'tax_ids': [(6, 0, taxes)] if taxes else False,
                # Si ya tienes mapeo a product.product, puedes añadir 'product_id' aquí
            }))

        move = Move.with_company(company).create({
            'move_type': 'out_invoice' if tipo == 'I' else 'out_refund',
            'partner_id': partner.id,
            'company_id': company.id,
            'currency_id': company.currency_id.id,
            'invoice_line_ids': lines_cmd,
        })

        # === Mapear campos EDI MX (best-effort) ===
        if uso and 'l10n_mx_edi_usage' in move._fields:
            try:
                move.l10n_mx_edi_usage = uso
            except Exception:
                pass

        if metodo and 'l10n_mx_edi_payment_policy' in move._fields:
            try:
                move.l10n_mx_edi_payment_policy = metodo
            except Exception:
                pass

        if forma:
            # Preferir M2O por code
            for f in ('l10n_mx_edi_payment_method_id', 'l10n_mx_edi_forma_pago_id'):
                if f in move._fields:
                    field = move._fields[f]
                    comodel = env[field.comodel_name]
                    pm = comodel.search([('code', '=', forma)], limit=1)
                    if pm:
                        setattr(move, f, pm.id)
                        break
            # Fallback a selection si aplica
            if 'l10n_mx_edi_forma_pago' in move._fields and not getattr(move, 'l10n_mx_edi_payment_method_id', False):
                try:
                    move.l10n_mx_edi_forma_pago = forma
                except Exception:
                    pass

        return move

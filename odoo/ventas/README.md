Ventas → Facturación (CFDI) con OCA (Odoo 18 Community)

Resumen
- Este módulo crea facturas de cliente (account.move) a partir de ventas.venta y delega el timbrado en los módulos EDI de México si están instalados (OCA). Si no están, la factura se crea y queda lista para timbrar una vez que se agregue el stack EDI.

Requisitos
- Odoo 18 Community
- Instalados: account, account_edi, l10n_mx
- Para timbrar: instalar los módulos EDI de México (OCA 18.x) y configurar CSD/PAC. Los campos EDI se escriben solo si el stack los provee.

Probar el flujo
1) Confirmar una ventas.venta y pulsar “Facturar (CFDI)”.
2) Elegir Tipo (Ingreso/Egreso/Pago) y Uso/Método/Forma de pago.
3) Al confirmar:
   - Ingreso/Egreso: se crea account.move y se postea. Si EDI está activo, se timbra y se adjunta XML al move.
   - Pago: registra pago sobre las facturas relacionadas (PPD) y genera complemento 2.0 si EDI está activo.
4) “Descargar XML” busca adjuntos XML en la factura vinculada.

Notas técnicas
- El bridge está en ventas/services/invoicing_bridge.py
- Si no existe res.partner para el cliente, se crea uno mínimo (name y VAT). Puedes enlazar tus clientes a partners si lo prefieres.
- Los impuestos se asignan buscando account.tax de ventas por porcentaje. Configura al menos IVA 16% si lo usas.

Instalación OCA EDI MX (resumen)
- Añade a addons_path los repos donde tengas los módulos OCA EDI MX para v18 (o el port 17.0 si ya lo usas), típicamente:
  - l10n_mx_edi, l10n_mx_edi_invoice, l10n_mx_edi_payment, l10n_mx_edi_cancel, y un conector PAC (p. ej., finkok, sf, sw) según disponibilidad.
- Actualiza lista de Apps e instala los módulos. Carga CSD de pruebas (SAT) y configura el conector PAC en modo pruebas.

Datos de prueba CFDI (SAT)
- RFC emisor: EKU9003173C9
- Contraseña CSD: 12345678a
- CSD de pruebas: usa los .cer/.key oficiales del SAT (sitio de documentación SAT).

Paso a productivo
- Cambia RFC de la compañía al real, carga CSD de producción, configura PAC de producción y desactiva modo pruebas.


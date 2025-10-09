# __manifest__.py
{
  "name": "Interfaz de Facturación (UI)",
  "version": "1.0",
  "depends": [
    "base","mail","account",
    "ventas","cargos","cargosdetail",
    "mx_cfdi_core",
  ],
  "data": [
    "views/wizards_views.xml",      # define acciones de los wizards que usa el form
    "views/factura_views.xml",      # define la acción principal action_facturas_ui
    "views/transaccion_vista.xml", # vista de transacciones (lista y formulario)
    "views/menu.xml",               # el menú la referencia (debe ir al final)
],
  "installable": True,
  "application": True,
}

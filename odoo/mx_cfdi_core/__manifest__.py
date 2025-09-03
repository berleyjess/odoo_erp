# mx_cfdi_engine/__manifest__.py
{
    "name": "CFDI Engine (MX)",
    "version": "1.0",
    "category": "Accounting",
    "depends": [
        "base",
    ],
    "data": [
        #"security/security.xml",
        #"security/ir.model.access.csv",
        #"views/res_config_settings_views.xml",
        #"views/cfdi_document_views.xml",
        "data/ir_config_parameter.xml",
    ],
    "installable": True,
    "application": False,
}

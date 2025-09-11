{
    "name": "CFDI Provider - SW Sapien",
    "version": "1.0",
    "category": "Accounting",
    "depends": ["base", "mx_cfdi_core"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "data/ir_config_parameter.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}

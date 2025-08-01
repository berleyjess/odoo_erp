# -*- coding: utf-8 -*-
"""
Modelo: clientes.cliente
Descripción: Administra la cartera de clientes para el módulo de Crédito.
Incluye datos fiscales, de identificación (INE, CURP), domicilio, estado civil y contactos
relacionados. Implementa lógica para:
- Autogenerar un código interno incremental.
- Forzar mayúsculas al crear/editar.
- Ajustar dinámicamente el dominio del régimen fiscal según el tipo de cliente.
- Limpiar el nombre del cónyuge cuando el estado civil no lo requiere.
"""
import re
from odoo.exceptions import ValidationError
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class cliente(models.Model):
    """
    Modelo principal de cliente.

    Notas:
    - El nombre técnico del modelo es `clientes.cliente`.
    - Utiliza una secuencia `seq_client_code` para generar el campo `codigo`.
    - Implementa `@api.onchange` para actualizar dominios y limpiar campos en la vista.
    - Sobrescribe `create` y `write` para normalizar datos a mayúsculas.
    """
    
    _name='clientes.cliente'  #Modelo.Cliente ("nombre del modulo"."nombre del modelo")
    _description='Cartera de clientes'
    _rec_name='nombre'  #Nombre del campo que se mostrará en las vistas de lista y búsqueda
    _order = 'codigo'  #Orden por defecto en las vistas de lista
    
    codigo = fields.Char( #Código interno del Cliente
        string='Código',
        size=10,
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_code(),
        help="Código interno autogenerado (ej. 000001). Controlado por la secuencia 'seq_client_code'."
    )

    nombre = fields.Char(string="Nombre/Razón social", required=True,help="Nombre completo o razón social del cliente.")

    rfc = fields.Char(string="RFC",size=13, required=True, index=True, help="Registro Federal de Contribuyentes")

    # Constantes de validación de RFC
    # RFC_GENERICOS contiene RFCs genéricos que no deben ser validados estrictamente
    RFC_GENERICOS = ('XAXX010101000', 'XEXX010101000')
    # RFC_REGEX es una expresión regular que valida el formato estándar del RFC
    RFC_REGEX = re.compile(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$')  # Formato estándar SAT
    # Expresiones regulares para CURP e INE
    # CURP_REGEX valida el formato de la CURP según las reglas del SAT
    CURP_REGEX = re.compile(
    r'^[A-ZÑ][AEIOU][A-ZÑ]{2}'   # 4 letras iniciales
    r'\d{6}'                     # fecha: YYMMDD
    r'[HM]'                      # sexo
    r'[A-ZÑ]{2}'                 # entidad federativa
    r'[B-DF-HJ-NP-TV-ZÑ]{3}'     # consonantes internas
    r'[A-Z\d]\d$'                # homoclave y dígito verificador
    )

    INE_REGEX = re.compile(r'^[A-ZÑ]{6}\d{8}[A-ZÑ]\d{3}$')  # 18 caracteres
    CP_REGEX       = re.compile(r'^\d{5}$')

    tipo = fields.Selection(
        selection = [
            ("0", "Persona Física"),
            ("1", "Persona Moral")
        ], string="Tipo de Cliente", required=True, default = "0",
        help="Define si el cliente es Persona Física o Persona Moral. Afecta el dominio del campo Régimen Fiscal."
    )

    regimen = fields.Many2one('clientes.c_regimenfiscal',
                              string = "Régimen Fiscal",
                              domain="[('tipo', 'in', [tipo == '0' and '0' or '1', '2'])]",
                              help="Régimen fiscal del cliente. El dominio se recalcula dinámicamente en _onchange_tipo."
    )

    # Campos de identificación / Estado civil
    ine = fields.Char(string="INE (Clave de Lector)", size=18, help="Ingrese solo la clave de lector del INE")
    curp = fields.Char(string="CURP", size=18, help="Clave Única de Registro de Población")
    estado_civil = fields.Selection([
        ('soltero', 'Soltero(a)'),
        ('casado', 'Casado(a)'),
        ('divorciado', 'Divorciado(a)'),
        ('viudo', 'Viudo(a)'),
        ('union_libre', 'Unión Libre')
    ], string="Estado Civil",
        help="Estado civil del cliente. "
    )
    
    conyugue = fields.Char(string="Nombre del Cónyuge", size=100, help="Nombre completo del cónyuge")

    codigop = fields.Char(string="Código Postal", size=5)
    localidad = fields.Many2one('localidades.localidad', string = "Ciudad/Localidad",help="Ciudad o localidad del domicilio del cliente")
    colonia = fields.Char(string = "Colonia", size = 32)
    calle = fields.Char(string = "Calle", size = 32)
    numero = fields.Char(string = "Número", help="Número exterior del domicilio del cliente")

    #Relación con contactos



    contacto = fields.One2many('clientes.contacto_ext', 'cliente_id', string = "Contactos",help="Contactos externos relacionados con este cliente.")

    # ONCHAGE METHODS

    """
        Actualiza el dominio del campo 'regimen' dependiendo del tipo de cliente.
        Además, muestra una advertencia si hay RFC capturado para que se valide
        coherencia con el tipo seleccionado.

        Retorna:
            dict: dominio dinámico para el campo 'regimen' y un warning opcional.
    """

    @api.onchange('tipo')
    def _onchange_tipo(self):
        """Actualiza dominio del campo regimen fiscal dinámicamente"""
        if not self.tipo:
            # Resetear el campo si tipo está vacío
            self.regimen = False
            return {'domain': {'regimen': []}}
        
        # Definir dominio basado en el tipo seleccionado
        domain_map = {
            '0': ['0', '2'],  # Persona Física
            '1': ['1', '2']   # Persona Moral
        }
        return {
            'domain': {
                'regimen': [('tipo', 'in', domain_map.get(self.tipo, []))]
            },
            'warning': {
                'title': "Cambio de Régimen Fiscal",
                'message': "Verifique que el RFC coincida con el tipo seleccionado"
            } if self.rfc else None
        }

    @api.onchange('estado_civil')
    def _onchange_estado_civil(self):
        """Limpia el campo cónyuge si no está casado o en unión libre"""
        if self.estado_civil not in ['casado', 'union_libre']:
            self.conyugue = False
    
    # Logica de negocio / hooks.

    def _generate_code(self):
        """
        Genera el código interno del cliente utilizando la secuencia 'seq_client_code'.
        Formatea el número a 6 dígitos con ceros a la izquierda.

        Returns:
            str: Código formateado, ej. '000001'
        """
        sequence = self.env['ir.sequence'].next_by_code('seq_client_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(6)}"
    
    @api.model
    def create(self, vals):
        """
        Sobrescribe create para:
        - Forzar a mayúsculas los campos de texto relevantes antes de crear el registro.

        Args:
            vals (dict): Valores a crear.

        Returns:
            recordset: Registro creado.
        """
        # Convertir a mayúsculas antes de crear
        if 'nombre' in vals:
            vals['nombre'] = vals['nombre'].upper() if vals['nombre'] else False
        if 'rfc' in vals:
            vals['rfc'] = vals['rfc'].upper() if vals['rfc'] else False
        if 'ine' in vals:
            vals['ine'] = vals['ine'].upper() if vals['ine'] else False
        if 'curp' in vals:
            vals['curp'] = vals['curp'].upper() if vals['curp'] else False
        if 'conyugue' in vals:
            vals['conyugue'] = vals['conyugue'].upper() if vals['conyugue'] else False
        return super().create(vals)

    def write(self, vals):
        """
        Sobrescribe write para:
        - Forzar a mayúsculas los campos de texto relevantes antes de actualizar el registro.

        Args:
            vals (dict): Valores a escribir.

        Returns:
            bool: True si la operación fue exitosa.
        """

        blocked_keys = {'localidad', 'localidad_id', 'regimen', 'regimen_id'}
        if blocked_keys.intersection(vals):
            raise UserError(_('No se permite modificar la Localidad ni el Régimen Fiscal.'))

        # Convertir a mayúsculas antes de actualizar
        if 'nombre' in vals:
            vals['nombre'] = vals['nombre'].upper() if vals['nombre'] else False
        if 'rfc' in vals:
            vals['rfc'] = vals['rfc'].upper() if vals['rfc'] else False
        if 'ine' in vals:
            vals['ine'] = vals['ine'].upper() if vals['ine'] else False
        if 'curp' in vals:
            vals['curp'] = vals['curp'].upper() if vals['curp'] else False
        if 'conyugue' in vals:
            vals['conyugue'] = vals['conyugue'].upper() if vals['conyugue'] else False
        return super().write(vals)
    
    @api.constrains('rfc')
    def _check_unique_rfc(self):
        for rec in self:
            rfc = (rec.rfc or '').strip().upper()
        if rfc:
            es_generico = rfc in self.RFC_GENERICOS

            if not es_generico and not self.RFC_REGEX.fullmatch(rfc):
                raise ValidationError(("El RFC '%s' no cumple con el formato válido.") % rfc)

            if not es_generico and rec.search_count([('rfc', '=', rfc), ('id', '!=', rec.id)]):
                raise ValidationError(("El RFC '%s' ya está registrado en otro cliente.") % rfc)


    # ---------- CONSTRAINS ---------------------------------

    @api.constrains('rfc', 'tipo')
    def _check_rfc(self):
        for rec in self:
            rfc = (rec.rfc or '').strip().upper()
            if not rfc:
                raise ValidationError(_("El campo RFC es obligatorio."))

        # 1) Longitud según tipo
            if rec.tipo == '0' and len(rfc) != 13:
                raise ValidationError(_("Persona Física: el RFC debe tener 13 caracteres."))
            if rec.tipo == '1' and len(rfc) != 12:
                raise ValidationError(_("Persona Moral: el RFC debe tener 12 caracteres."))

        # 2) Formato y unicidad (salvo genéricos)
            es_generico = rfc in self.RFC_GENERICOS
            if not es_generico and not self.RFC_REGEX.fullmatch(rfc):
                raise ValidationError(_("El RFC '%s' no tiene un formato válido.") % rfc)

            if not es_generico and rec.search_count([('rfc', '=', rfc), ('id', '!=', rec.id)]):
                raise ValidationError(_("El RFC '%s' ya está registrado en otro cliente.") % rfc)


    #@api.constrains('curp')
    #def _check_curp(self):
    #    for rec in self:
    #        curp = (rec.curp or '').strip().upper()
    #        if curp and not self.CURP_REGEX.fullmatch(curp):
    #            raise ValidationError(_("La CURP '%s' no es válida.") % curp)


    #@api.constrains('ine')
    #def _check_ine(self):
    #    for rec in self:
    #        ine = (rec.ine or '').strip().upper()
    #        if ine and not self.INE_REGEX.fullmatch(ine):
    #            raise ValidationError(
    #                _("La clave de elector INE '%s' no es válida.") % ine
    #            )


    @api.constrains('codigop')
    def _check_cp(self):
        for rec in self:
            cp = (rec.codigop or '').strip()
            if cp and not self.CP_REGEX.fullmatch(cp):
                raise ValidationError(_("El Código Postal '%s' debe ser de 5 dígitos.") % cp)


    @api.constrains('numero')
    def _check_numero(self):
        for rec in self:
            if isinstance(rec.numero, str):                 # solo si lo dejas como Char
                if rec.numero and not rec.numero.isdigit():
                    raise ValidationError(_("El número de calle solo puede contener dígitos."))

    def action_save(self):
        """
        Acción para guardar y volver a la vista de lista.
        Útil si pones un botón 'Guardar' manual en la vista.
        """
        self.ensure_one()
        
        # Retornar a la vista lista
        return {
            'type': 'ir.actions.act_window',
            'name': 'Clientes',
            'res_model': 'clientes.cliente',
            'view_mode': 'list,form',
            'target': 'current',
        }
    
    def action_editar(self):
        """Método que retorna la acción para abrir el registro en modo edición"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Editar Cliente',
            'res_model': 'clientes.cliente',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('clientes.view_clientes_form_edit').id,
            'target': 'current',
        }

    def open_record(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Detalle',
            'res_model': 'clientes.cliente',
            'view_mode': 'form',
            'view_id': self.env.ref('clientes.view_clientes_form').id,
            'target': 'new',
            'res_id': self.id,
        }
    
    def action_save_and_return(self):
        """
        Guarda los cambios y regresa a la vista de detalle.
        """
        self.ensure_one()
    
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detalles del Cliente'),
            'res_model': 'clientes.cliente',
            'view_mode': 'form',
            'views': [(self.env.ref('clientes.view_cliente_form').id, 'form')],
            'target': 'current',
            'res_id': self.id,
        }
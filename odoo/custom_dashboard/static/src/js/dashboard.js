/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CustomDashboard extends Component {
    static template = "custom_dashboard.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        // 👇 NOTA: ya no usamos ningún servicio "user" ni this.env.services.user
        this.state = useState({
            modules: [],
            filteredModules: [],
            favorites: [],
            searchQuery: "",
            activeCategory: "all",
            loading: true,
        });

        this.categories = [
            { id: "all", name: "Todos", icon: "fa-th-large" },
            { id: "ventas", name: "Ventas", icon: "fa-shopping-cart" },
            { id: "contabilidad", name: "Contabilidad", icon: "fa-calculator" },
            { id: "inventario", name: "Inventario", icon: "fa-boxes" },
            { id: "rrhh", name: "Recursos Humanos", icon: "fa-users" },
            { id: "productividad", name: "Productividad", icon: "fa-tasks" },
            { id: "marketing", name: "Marketing", icon: "fa-bullhorn" },
            { id: "otros", name: "Otros", icon: "fa-ellipsis-h" },
        ];

        onWillStart(async () => {
            await this.loadData();
            this.state.loading = false;
        });
    }

    async loadData() {
        try {
            // El backend ahora filtra correctamente y excluye módulos de Odoo
            const modules = (await this.orm.call(
                "dashboard.module",
                "get_dashboard_modules",
                []
            )) || [];

            const favorites = (await this.orm.call(
                "dashboard.favorite",
                "get_favorites",
                []
            )) || [];

            this.state.modules = modules;
            this.state.filteredModules = modules;
            this.state.favorites = favorites;

            console.log("Dashboard modules loaded:", modules);
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            this.notification.add("Error al cargar los módulos", { type: "danger" });
            this.state.modules = [];
            this.state.filteredModules = [];
            this.state.favorites = [];
        }
    }

    filterModules() {
        let filtered = [...this.state.modules];

        // Filtrar por categoría
        if (this.state.activeCategory !== "all") {
            filtered = filtered.filter((m) => m.category === this.state.activeCategory);
        }

        // Filtrar por búsqueda
        if (this.state.searchQuery) {
            const query = this.state.searchQuery.toLowerCase();
            filtered = filtered.filter(
                (m) =>
                    m.name.toLowerCase().includes(query) ||
                    (m.description && m.description.toLowerCase().includes(query))
            );
        }

        this.state.filteredModules = filtered;
    }

    onSearchInput(event) {
        this.state.searchQuery = event.target.value;
        this.filterModules();
    }

    setCategory(categoryId) {
        this.state.activeCategory = categoryId;
        this.filterModules();
    }

    isFavorite(menuId) {
        return this.state.favorites.includes(menuId);
    }

    async toggleFavorite(event, module) {
        event.stopPropagation();

        try {
            const result = await this.orm.call(
                "dashboard.favorite",
                "toggle_favorite",
                [module.menu_id]
            );

            if (result) {
                this.state.favorites.push(module.menu_id);
                this.showToast("Añadido a favoritos");
            } else {
                this.state.favorites = this.state.favorites.filter(
                    (id) => id !== module.menu_id
                );
                this.showToast("Eliminado de favoritos");
            }
        } catch (error) {
            console.error("Error toggling favorite:", error);
        }
    }

    async openModule(module) {
        // 1) Si la tarjeta tiene acción explícita, usamos esa
        if (module.action_id) {
            await this.action.doAction(module.action_id);
            return;
        }
    
        // 2) Si no tiene acción pero tiene menú, intentamos usar el menuService
        if (module.menu_id) {
            const menuService = this.env.services.menu;
            if (menuService && menuService.getMenu) {
                const menu = menuService.getMenu(module.menu_id);
            
                // Solo llamamos selectMenu si realmente existe el menú
                // y tiene actionID; si no, NO llamamos y evitamos el error.
                if (menu && menu.actionID) {
                    await menuService.selectMenu(menu);
                    return;
                }
            }
        }
    
        // 3) Fallback: no hay acción válida → mensaje al usuario
        this.notification.add(
            "Este acceso no tiene una acción configurada. Asigna una acción en el menú o en la configuración del Dashboard.",
            { type: "warning" }
        );
    }


    showToast(message) {
        this.notification.add(message, {
            type: "success",
            sticky: false,
        });
    }

    get moduleCount() {
        const mods = this.state && this.state.filteredModules;
        return Array.isArray(mods) ? mods.length : 0;
    }

    // 👇 Ya no dependemos de ningún servicio "user"
    get userName() {
        return "Usuario";
    }
}

CustomDashboard.template = "custom_dashboard.Dashboard";

registry.category("actions").add("custom_dashboard", CustomDashboard);

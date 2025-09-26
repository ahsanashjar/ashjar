/** @odoo-module **/
/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { useService } from "@web/core/utils/hooks";

export class MrpBomListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.notification = useService("notification");

    }


    get hasSelectedRecords() {
        return this.model.root.selection.length > 0;
    }

    async onUpdateStockClick() {
        // Get selected IDs as a simple array
        const selectedIds = this.model.root.selection.map(record => record.resId);

        if (selectedIds.length === 0) {
            this.notification.add("Please select at least one record.", {
                type: "warning",
            });
            return;
        }

        try {
            await this.actionService.doAction("custom_sale_order.action_my_custom_bom_mass", {
                additionalContext: {
                    active_ids: selectedIds,
                    active_model: 'mrp.bom',
                },
            });
        } catch (error) {
            console.error("Error executing action:", error);
        }
    }
}

registry.category("views").add("mrp_bom_list", {
    ...listView,
    Controller: MrpBomListController,
});
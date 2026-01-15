#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: dag_inv_eliminator.py
Description: Eliniminates inverters in the DAG
Author: Deyuan Guo <guodeyuan@gmail.com>
Date: 2025-06-04
"""

from dag_transformer_base import DagTransformer


class InvEliminator(DagTransformer):
    """Eliminates inverters in the DAG for analog PIM with dual-contact cells (DCC) capability"""

    def apply(self, dag):
        """Apply inverter elimination in the DAG"""
        total_inv = 0
        for gate_id in dag.get_topo_sorted_gate_id_list():
            if self.is_target_gate(dag, gate_id):
                total_inv += self.run_xform_inv_elimination(dag, gate_id)
        if self.debug_level >= 1:
            print(f"DAG-Transform Summary: Total {total_inv} inverter gates eliminated")

    def is_target_gate(self, dag, gate_id):
        """Check if a gate is a target for inverter elimination"""
        gate = dag.graph.nodes[gate_id]
        return gate["gate_func"] == "inv1"

    def run_xform_inv_elimination(self, dag, inv_gate_id):
        """Transform: Eliminate an inverter gate and invert fanout gate inputs"""
        inv_gate = dag.graph.nodes[inv_gate_id]
        in_wire = inv_gate["inputs"][0]
        out_wire = inv_gate["outputs"][0]

        # Note: Skip inverters that are connected to input or output ports for now
        # It's possible that the input wire is an output port if port isolation is not applied
        if (
            dag.is_in_port(in_wire)
            or dag.is_out_port(in_wire)
            or dag.is_out_port(out_wire)
        ):
            return 0

        if self.debug_level >= 2:
            print(f"DAG-Transform: Remove INV gate: {inv_gate_id}")

        driver_gate_ids = dag.get_wire_fanin_gate_ids(in_wire)
        assert len(driver_gate_ids) == 1, "Inverter should have exactly one driver gate"
        driver_gate_id = driver_gate_ids[0]
        load_gate_ids = dag.get_wire_fanout_gate_ids(out_wire)

        # Remove the inverter gate and wires
        dag.remove_wire(driver_gate_id, inv_gate_id)
        for load_gate_id in load_gate_ids:
            dag.remove_wire(inv_gate_id, load_gate_id)
        dag.remove_gate(inv_gate_id)

        # Reconnect and invert the fanout gate inputs
        for load_gate_id in load_gate_ids:
            load_gate = dag.graph.nodes[load_gate_id]

            # Check if the destination gate already has the direct wire as an input.
            # This happens when both the direct wire (in_wire) and the inverted wire (out_wire)
            # are connected to the same destination gate. In this case, we need to rename
            # the inverted wire to avoid a naming conflict when trying to replace it.
            if in_wire in load_gate["inputs"]:
                if self.debug_level >= 2:
                    print(
                        f"DAG-Transform: Both direct and inverted versions of '{in_wire}' "
                        f"are connected to gate {load_gate_id}. Renaming inverted wire."
                    )

                # Generate a unique wire name for the inverted version
                inverted_wire_name = dag.uniqufy_wire_name(
                    f"{dag.get_wire_base_name(out_wire)}_inv"
                )

                # Replace the inverted wire output in the driver gate
                dag.replace_output_wire(driver_gate_id, out_wire, inverted_wire_name)

                # Update the edge from driver to destination with the new wire name
                dag.add_wire(inverted_wire_name, driver_gate_id, load_gate_id)
                dag.replace_input_wire(load_gate_id, out_wire, inverted_wire_name)
                dag.invert_input_wire(load_gate_id, inverted_wire_name)
            else:
                # Standard case: no conflict, proceed normally
                dag.add_wire(in_wire, driver_gate_id, load_gate_id)
                dag.replace_input_wire(load_gate_id, out_wire, in_wire)
                dag.invert_input_wire(load_gate_id, in_wire)
        return 1
